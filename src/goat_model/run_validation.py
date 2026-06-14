from __future__ import annotations

import argparse
from pathlib import Path

from goat_model.validate import run_validation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Step 4 season-level validator.")
    parser.add_argument(
        "--goat-root",
        type=Path,
        default=None,
        help="Optional absolute path to GoatProject root.",
    )
    parser.add_argument(
        "--with-shap",
        action="store_true",
        help="Include optional SHAP diagnostics if shap is installed.",
    )
    args = parser.parse_args()

    report = run_validation(goat_root=args.goat_root, include_shap=args.with_shap)
    primary = report["primary_metrics"]
    print("validation_report.json written")
    print(
        "mvp_vote_share spearman=",
        f"{primary['mvp_vote_share']['value']:.6f}",
        "| all_nba_first",
        f"{primary['all_nba_first']['metric']}={primary['all_nba_first']['value']:.6f}",
    )


if __name__ == "__main__":
    main()
