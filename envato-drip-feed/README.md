# Envato Niche Drip Feed

Server-side acquisition service for licensed Envato assets. It reuses one persistent
Chromium profile, rotates through configured niches, rejects obvious mismatches and
duplicates, records provenance, and syncs accepted assets to Google Drive.

## Package layout

`<drive-root>/<niche>/<YYYY-MM>/<asset-type>/`

Every package contains the original download, `manifest.jsonl`, and a source record.
Stock media is labeled as licensed stock and must never be represented as client work.

## Commands

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp env.example .env
.venv/bin/python scripts/init_state.py
.venv/bin/python scripts/auth_session.py
.venv/bin/python scripts/run_batch.py --dry-run
.venv/bin/python scripts/run_batch.py
```

The `auth_session.py` process opens Envato in the Selenium browser and keeps the
session alive while the operator signs in through noVNC. Stop it with Ctrl+C after
the script reports that the authenticated account page is visible.

## Safety gates

- At most the configured number of downloads per run.
- Item IDs are never downloaded twice.
- Files with unsupported extensions, implausible size, or blocked terms are rejected.
- Every accepted asset retains its Envato item URL, query, type, timestamp, and hash.
- A filesystem lock prevents overlapping timer runs.

