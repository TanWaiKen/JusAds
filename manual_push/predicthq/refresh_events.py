#!/usr/bin/env python3
"""Paginated PredictHQ event export and idempotent Supabase refresh.

This is an operator tool. It is intentionally outside the deployed backend.

Run from the repository root after installing Python 3.12+:
  python manual_push/predicthq/refresh_events.py --dry-run
  python manual_push/predicthq/refresh_events.py --replace-backups
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / "backend" / ".env"
BACKUP_DIR = ROOT / "manual_push" / "backups" / "predicthq"
PREDICTHQ_URL = "https://api.predicthq.com/v1/events/"
COUNTRIES = {"MY": "malaysia", "SG": "singapore", "TH": "thailand", "ID": "indonesia", "VN": "vietnam", "PH": "philippines"}
EVENT_TYPES = {"sports": "sports", "festivals": "festive", "concerts": "festive", "public-holidays": "national", "school-holidays": "national", "observances": "national"}
CATEGORY_FILTER = "festivals,sports,public-holidays,concerts,expos,conferences,observances,community"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def request_json(url: str, token: str, *, method: str = "GET", body: Any | None = None, headers: dict[str, str] | None = None) -> Any:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in {"api.predicthq.com", urlparse(os.environ["SUPABASE_URL"]).netloc}:
        raise ValueError("Refusing an unexpected API host")
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request_headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if payload:
        request_headers["Content-Type"] = "application/json"
    request_headers.update(headers or {})
    request = Request(url, method=method, data=payload, headers=request_headers)
    with urlopen(request, timeout=30) as response:  # nosec B310 - host checked above
        return json.loads(response.read().decode("utf-8"))


def fetch_country(country: str, token: str, days: int, page_size: int) -> tuple[list[dict[str, Any]], int | None, bool, int]:
    today = datetime.now(UTC).date()
    params = {
        "active.gte": today.isoformat(),
        "active.lte": (today + timedelta(days=days)).isoformat(),
        "category": CATEGORY_FILTER,
        "country": country,
        "limit": str(page_size),
        "sort": "rank",
    }
    url = f"{PREDICTHQ_URL}?{urlencode(params)}"
    results: list[dict[str, Any]] = []
    overflow = False
    reported_count: int | None = None
    pages = 0
    while url:
        page = request_json(url, token)
        pages += 1
        results.extend(item for item in page.get("results", []) if isinstance(item, dict) and item.get("id"))
        overflow = overflow or bool(page.get("overflow"))
        count = page.get("count")
        if isinstance(count, int):
            reported_count = count
        next_url = page.get("next")
        url = next_url if isinstance(next_url, str) and next_url.startswith(PREDICTHQ_URL) else ""
    return results, reported_count, overflow, pages


def date_only(value: Any) -> str:
    return str(value or datetime.now(UTC).date().isoformat())[:10]


def normalize(event: dict[str, Any], market: str) -> dict[str, Any]:
    category = event.get("category")
    category = category[0] if isinstance(category, list) and category else category
    return {
        "name": str(event.get("title") or "Untitled event")[:500], "market": market,
        "start_date": date_only(event.get("start")), "end_date": date_only(event.get("end") or event.get("start")),
        "event_type": EVENT_TYPES.get(str(category or "").lower(), "global"),
        "tags": [str(tag) for tag in event.get("labels", []) if isinstance(tag, str)][:25],
        "impact_score": max(0, min(100, int(event.get("rank") or 0))), "source": "predicthq",
        "source_event_id": str(event["id"]), "source_updated_at": event.get("updated") or None,
        "source_payload": event, "last_synced_at": datetime.now(UTC).isoformat(),
    }


def write_csv(rows: list[dict[str, Any]], replace_backups: bool) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    old_backups = list(BACKUP_DIR.glob("predicthq_events_*.csv")) if replace_backups else []
    destination = BACKUP_DIR / f"predicthq_events_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.csv"
    columns = ["source_event_id", "name", "market", "start_date", "end_date", "event_type", "impact_score", "tags", "source_updated_at"]
    with destination.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                column: (json.dumps(row["tags"], ensure_ascii=False) if column == "tags" else row.get(column, ""))
                for column in columns
            })
    # Rotate only after the new CSV has been written successfully. This protects
    # the previous operator backup if disk or encoding errors occur mid-export.
    for old_file in old_backups:
        if old_file != destination:
            old_file.unlink()
    return destination


def upsert(rows: list[dict[str, Any]], url: str, key: str) -> int:
    endpoint = f"{url.rstrip('/')}/rest/v1/cultural_events?on_conflict=source,source_event_id"
    response = request_json(endpoint, key, method="POST", body=rows, headers={"apikey": key, "Prefer": "resolution=merge-duplicates,return=representation"})
    return len(response) if isinstance(response, list) else 0


def prune_expired(url: str, key: str, retention_days: int) -> int:
    """Delete only stale imported events; never touch curated/manual rows."""
    cutoff = (datetime.now(UTC).date() - timedelta(days=retention_days)).isoformat()
    endpoint = f"{url.rstrip('/')}/rest/v1/cultural_events?source=eq.predicthq&end_date=lt.{cutoff}"
    response = request_json(endpoint, key, method="DELETE", headers={"apikey": key, "Prefer": "return=representation"})
    return len(response) if isinstance(response, list) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Export all available paginated PredictHQ events and upsert them into Supabase.")
    parser.add_argument("--days", type=int, default=120, choices=range(1, 366))
    parser.add_argument("--markets", default="MY,SG,TH,ID,VN,PH")
    parser.add_argument("--page-size", type=int, default=100, choices=range(1, 101))
    parser.add_argument("--retention-days", type=int, default=90, choices=range(0, 3660))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace-backups", action="store_true", help="Delete only prior generated PredictHQ CSV backups after a new export is ready.")
    args = parser.parse_args()
    load_env(ENV_FILE)
    token, supabase_url = os.environ.get("PREDICTHQ_API_KEY"), os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not token or not supabase_url or not supabase_key:
        print("Missing PREDICTHQ_API_KEY, SUPABASE_URL, or server-only SUPABASE_KEY.", file=sys.stderr)
        return 2
    selected = [code.strip().upper() for code in args.markets.split(",") if code.strip().upper() in COUNTRIES]
    if not selected:
        print("No valid markets selected.", file=sys.stderr)
        return 2
    rows, overflow = [], False
    for country in selected:
        events, reported_count, country_overflow, pages = fetch_country(country, token, args.days, args.page_size)
        rows.extend(normalize(event, COUNTRIES[country]) for event in events)
        overflow = overflow or country_overflow
        expected = str(reported_count) if reported_count is not None else "unknown"
        print(f"{country}: {len(events)} fetched across {pages} page(s); API count={expected}; overflow={country_overflow}")
    unique = list({row["source_event_id"]: row for row in rows}.values())
    backup = write_csv(unique, args.replace_backups)
    print(f"CSV backup: {backup.relative_to(ROOT)} ({len(unique)} unique events)")
    if overflow:
        print("WARNING: PredictHQ reported subscription overflow. This is the maximum accessible result set for at least one query, not necessarily all matching events.")
    else:
        print("PredictHQ reported no subscription overflow. All records matching the selected countries, categories, and date window were paginated.")
    if args.dry_run:
        print("Dry run: Supabase unchanged.")
    else:
        print(f"Supabase: {upsert(unique, supabase_url, supabase_key)} rows inserted or updated.")
        print(f"Supabase: {prune_expired(supabase_url, supabase_key, args.retention_days)} expired PredictHQ rows pruned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
