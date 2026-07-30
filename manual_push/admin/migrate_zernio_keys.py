"""Encrypt legacy plaintext Zernio keys without exposing their values.

Run from the repository root.  The default is a read-only preview; pass
``--apply`` only after recording the preview count.  The script is idempotent:
already encrypted entries are skipped and no account, user, or key is deleted.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env", override=False)

from shared.zernio_key_vault import encrypt_key  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Persist encrypted values.")
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise SystemExit("SUPABASE_URL and a server-only SUPABASE_KEY are required.")

    client = create_client(url, key)
    rows = client.table("users").select("email,zernio_api_key").not_.is_("zernio_api_key", "null").execute().data or []
    legacy = [row for row in rows if not str(row.get("zernio_api_key") or "").startswith("fernet:v1:")]

    print(f"Legacy plaintext Zernio entries: {len(legacy)}")
    if not args.apply:
        print("Dry run only. Re-run with --apply to encrypt these values.")
        return 0

    migrated = 0
    for row in legacy:
        # Never log the email together with a key, and never print a key.
        client.table("users").update(
            {"zernio_api_key": encrypt_key(str(row["zernio_api_key"]))}
        ).eq("email", row["email"]).execute()
        migrated += 1
    print(f"Encrypted entries: {migrated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
