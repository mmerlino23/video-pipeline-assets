from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def settings() -> dict:
    cfg = yaml.safe_load((ROOT / "config" / "niches.yaml").read_text(encoding="utf-8"))
    return {
        "config": cfg,
        "selenium_url": os.getenv("SELENIUM_URL", "http://127.0.0.1:4444/wd/hub"),
        "download_root": Path(os.getenv("DOWNLOAD_ROOT", "/srv/envato-drip-feed/library")),
        "state_db": Path(os.getenv("STATE_DB", "/srv/envato-drip-feed/state/state.sqlite3")),
        "drive_remote": os.getenv("DRIVE_REMOTE", "merlino-drive:"),
        "drive_root": os.getenv("DRIVE_ROOT", "Media Library/Envato Licensed Stock"),
        "max_downloads": int(os.getenv("MAX_DOWNLOADS_PER_RUN", cfg["rotation"]["max_downloads_per_run"])),
        "max_runtime_minutes": int(os.getenv("MAX_RUNTIME_MINUTES", "50")),
    }


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assets (
          item_id TEXT PRIMARY KEY, niche TEXT NOT NULL, asset_type TEXT NOT NULL,
          query TEXT NOT NULL, title TEXT NOT NULL, source_url TEXT NOT NULL,
          downloaded_at TEXT, local_path TEXT, sha256 TEXT, status TEXT NOT NULL,
          reason TEXT
        );
        """
    )
    return con


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def append_manifest(folder: Path, record: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "manifest.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

