from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from browser import driver
from common import append_manifest, connect, settings, sha256, utc_now

EXTENSIONS = {".zip", ".mp4", ".mov", ".jpg", ".jpeg", ".png", ".webp"}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90]


def item_id(url: str) -> str:
    match = re.search(r"(?:-|/)(\d{5,})(?:\?|$)", url)
    return match.group(1) if match else slug(url)[-60:]


def choose_rotation(con, cfg):
    niches = cfg["niches"]
    types = cfg["rotation"]["asset_types"]
    ni = int(con.execute("SELECT value FROM state WHERE key='niche_index'").fetchone()[0]) if con.execute("SELECT 1 FROM state WHERE key='niche_index'").fetchone() else 0
    ti = int(con.execute("SELECT value FROM state WHERE key='type_index'").fetchone()[0]) if con.execute("SELECT 1 FROM state WHERE key='type_index'").fetchone() else 0
    niche, asset_type = niches[ni % len(niches)], types[ti % len(types)]
    next_ni, next_ti = ni + 1, ti
    if next_ni % len(niches) == 0:
        next_ti += 1
    con.execute("INSERT OR REPLACE INTO state(key,value) VALUES('niche_index',?),('type_index',?)", (str(next_ni), str(next_ti)))
    con.commit()
    return niche, asset_type


def relevant(title: str, niche: dict) -> tuple[bool, str]:
    low = title.lower()
    if any(term.lower() in low for term in niche.get("blocked", [])):
        return False, "blocked term"
    if not any(term.lower() in low for term in niche["required_any"]):
        return False, "missing niche term"
    return True, "matched"


def collect_results(d, asset_type: str, query: str):
    url = f"https://app.envato.com/search/{asset_type}?term={quote_plus(query)}"
    d.get(url)
    WebDriverWait(d, 25).until(lambda x: x.execute_script("return document.readyState") == "complete")
    if "sign-in" in d.current_url:
        raise RuntimeError("Envato profile is not authenticated; run auth_session.py")
    links = d.find_elements(By.CSS_SELECTOR, "a[href]")
    seen = set()
    for a in links:
        href = a.get_attribute("href") or ""
        title = (a.get_attribute("aria-label") or a.text or a.get_attribute("title") or "").strip()
        if "envato.com" not in href or not title or href in seen:
            continue
        if not re.search(r"-\d{5,}(?:\?|$)", href):
            continue
        seen.add(href)
        yield {"url": href.split("?")[0], "title": title[:240]}


def click_download(d, staging: Path, timeout=90) -> Path | None:
    before = {p.name for p in staging.glob("*")}
    candidates = d.find_elements(By.XPATH, "//button[contains(translate(., 'DOWNLOAD', 'download'),'download')] | //a[contains(translate(., 'DOWNLOAD', 'download'),'download')]")
    if not candidates:
        return None
    candidates[0].click()
    deadline = time.time() + timeout
    while time.time() < deadline:
        files = [p for p in staging.glob("*") if p.name not in before and not p.name.endswith((".crdownload", ".tmp"))]
        if files:
            return max(files, key=lambda p: p.stat().st_mtime)
        time.sleep(2)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--niche")
    ap.add_argument("--asset-type")
    args = ap.parse_args()
    s = settings()
    con = connect(s["state_db"])
    niche, asset_type = choose_rotation(con, s["config"])
    if args.niche:
        niche = next(n for n in s["config"]["niches"] if n["slug"] == args.niche)
    asset_type = args.asset_type or asset_type
    query = niche["queries"][int(datetime.now().strftime("%j")) % len(niche["queries"])]
    print(json.dumps({"niche": niche["slug"], "asset_type": asset_type, "query": query, "dry_run": args.dry_run}))
    if args.dry_run:
        return
    staging = s["download_root"].parent / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    d = driver(s["selenium_url"])
    accepted = 0
    started = time.time()
    try:
        for item in collect_results(d, asset_type, query):
            if accepted >= s["max_downloads"] or time.time() - started > s["max_runtime_minutes"] * 60:
                break
            iid = item_id(item["url"])
            if con.execute("SELECT 1 FROM assets WHERE item_id=?", (iid,)).fetchone():
                continue
            ok, reason = relevant(item["title"], niche)
            if not ok:
                con.execute("INSERT OR IGNORE INTO assets(item_id,niche,asset_type,query,title,source_url,status,reason) VALUES(?,?,?,?,?,?,?,?)", (iid,niche["slug"],asset_type,query,item["title"],item["url"],"rejected",reason))
                con.commit()
                continue
            d.get(item["url"])
            downloaded = click_download(d, staging)
            if not downloaded or downloaded.suffix.lower() not in EXTENSIONS or downloaded.stat().st_size < 50_000:
                con.execute("INSERT OR REPLACE INTO assets(item_id,niche,asset_type,query,title,source_url,status,reason) VALUES(?,?,?,?,?,?,?,?)", (iid,niche["slug"],asset_type,query,item["title"],item["url"],"needs_review","download unavailable or invalid"))
                con.commit()
                continue
            month = datetime.now().strftime("%Y-%m")
            dest_dir = s["download_root"] / niche["slug"] / month / asset_type
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{iid}-{slug(item['title'])}{downloaded.suffix.lower()}"
            shutil.move(str(downloaded), dest)
            digest = sha256(dest)
            record = {**item, "item_id": iid, "niche": niche["slug"], "asset_type": asset_type, "query": query, "downloaded_at": utc_now(), "sha256": digest, "licensed_stock": True}
            append_manifest(dest_dir, record)
            con.execute("INSERT OR REPLACE INTO assets(item_id,niche,asset_type,query,title,source_url,downloaded_at,local_path,sha256,status,reason) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (iid,niche["slug"],asset_type,query,item["title"],item["url"],record["downloaded_at"],str(dest),digest,"accepted","matched and downloaded"))
            con.commit()
            accepted += 1
        if accepted:
            remote = f"{s['drive_remote'].rstrip(':')}:/{s['drive_root'].strip('/')}/{niche['slug']}/"
            subprocess.run(["rclone", "copy", str(s["download_root"] / niche["slug"]), remote, "--create-empty-src-dirs", "--transfers", "2", "--checkers", "4"], check=True)
    finally:
        d.quit()
        con.close()
    print(json.dumps({"accepted": accepted, "niche": niche["slug"], "asset_type": asset_type}))


if __name__ == "__main__":
    main()

