from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

DEFAULT_SOURCE_RAW_BASE_URL = (
    "https://raw.githubusercontent.com/midoriririta/subunit_tracking_dual_system_v3/main/data/raw"
)
FILES = ["demography_openalex_people.csv", "ndph_openalex_people.csv"]


def fetch_file(base_url: str, filename: str, overwrite: bool = False) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / filename
    if out.exists() and out.stat().st_size > 0 and not overwrite:
        print(f"Keeping existing {out}")
        return out
    url = f"{base_url.rstrip('/')}/{filename}"
    print(f"Fetching {url}")
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    out.write_bytes(resp.content)
    print(f"Saved {out} ({out.stat().st_size:,} bytes)")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch raw staff CSV files from a public source repository.")
    parser.add_argument("--base_url", default=DEFAULT_SOURCE_RAW_BASE_URL)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        for filename in FILES:
            fetch_file(args.base_url, filename, overwrite=args.overwrite)
    except Exception as exc:
        print(f"Failed to fetch raw data: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
