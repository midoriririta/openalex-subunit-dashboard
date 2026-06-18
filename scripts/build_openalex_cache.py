from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.openalex_dashboard.cache_builder import build_cache_from_staff_csv, find_default_staff_csv
from src.openalex_dashboard.config import CACHE_DIR, DATASET_CONFIGS, OUTPUT_DIR, DEFAULT_OPENALEX_MAILTO


def build_one(dataset_key: str, input_csv: Path | None, args: argparse.Namespace) -> None:
    csv_path = input_csv or find_default_staff_csv(dataset_key)
    if not csv_path or not Path(csv_path).exists():
        raise FileNotFoundError(
            f"No raw CSV found for dataset '{dataset_key}'. Expected: {DATASET_CONFIGS[dataset_key]['default_staff_csv']}"
        )

    result = build_cache_from_staff_csv(
        input_csv=Path(csv_path),
        dataset_key=dataset_key,
        cache_dir=Path(args.output_dir),
        output_dir=Path(args.export_output_dir),
        mailto=args.mailto or DEFAULT_OPENALEX_MAILTO or os.environ.get("OPENALEX_MAILTO", ""),
        max_candidates_per_person=args.max_candidates_per_person,
        min_author_score=args.min_author_score,
        throttle_s=args.throttle_s,
    )
    print(f"\nSaved OpenAlex cache for {dataset_key}:")
    for name, path in result["paths"].items():
        print(f"- {name}: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or refresh the OpenAlex dashboard cache from raw staff CSVs.")
    parser.add_argument("--input_csv", default=None, help="Optional input CSV. When omitted, uses data/raw/<dataset>_openalex_people.csv.")
    parser.add_argument("--output_dir", default=str(CACHE_DIR))
    parser.add_argument("--dataset", choices=["demography", "ndph", "all"], default="all")
    parser.add_argument("--export_output_dir", default=str(OUTPUT_DIR), help="Directory for optional parquet export artefacts.")
    parser.add_argument("--mailto", default=None)
    parser.add_argument("--max_candidates_per_person", type=int, default=2)
    parser.add_argument("--min_author_score", type=float, default=0.55)
    parser.add_argument("--throttle_s", type=float, default=0.12)
    args = parser.parse_args()

    if args.dataset == "all":
        if args.input_csv:
            raise ValueError("--input_csv can only be used when --dataset is demography or ndph, not all.")
        for dataset_key in ["ndph", "demography"]:
            build_one(dataset_key, None, args)
    else:
        build_one(args.dataset, Path(args.input_csv) if args.input_csv else None, args)


if __name__ == "__main__":
    main()
