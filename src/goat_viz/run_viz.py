from __future__ import annotations

import argparse

from .io import load_artifacts
from .render import render_all


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render GOAT Step 5 visualizations.")
    parser.add_argument(
        "--goat-root",
        default=None,
        help="Optional absolute path to GOAT_ROOT. Falls back to GOAT_ROOT env var.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths, artifacts = load_artifacts(args.goat_root)
    generated = render_all(paths, artifacts)

    print("Generated visualization artifacts:")
    for key, path in generated.items():
        print(f"- {key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
