#!/usr/bin/env python3
"""Verify GoatProject checkpoint artifacts for clone-and-run bootstrap."""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


def find_root(start: Path | None = None) -> Path:
    cursor = (start or Path(__file__)).resolve()
    for parent in cursor.parents:
        if (parent / "checkpoint.yaml").is_file() and (parent / "config" / "allowlist.yaml").is_file():
            return parent
    raise FileNotFoundError("Could not locate GoatProject root (missing checkpoint.yaml)")


def load_checkpoint(root: Path) -> dict:
    path = root / "checkpoint.yaml"
    text = path.read_text(encoding="utf-8")
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install pyyaml (or run bootstrap.sh first)")
    return yaml.safe_load(text)


def verify(root: Path) -> list[str]:
    cfg = load_checkpoint(root)
    errors: list[str] = []

    for rel in cfg.get("required_files", []):
        path = root / rel
        if not path.is_file():
            errors.append(f"Missing required file: {rel}")

    for rel in cfg.get("config_files", []):
        path = root / rel
        if not path.is_file():
            errors.append(f"Missing config: {rel}")

    for wt in cfg.get("worktrees", []):
        wt_path = root / wt["path"]
        if not wt_path.is_dir():
            errors.append(f"Missing worktree directory: {wt['path']} (run ./bootstrap.sh)")

    manifest_path = root / "GoatProject-data/processed/manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        checks = cfg.get("manifest_checks", {})
        player_count = int(manifest.get("player_count", 0))
        min_players = int(checks.get("player_count_min", 100))
        if player_count < min_players:
            errors.append(f"manifest player_count={player_count} (need >={min_players})")

        feature_cols = manifest.get("feature_columns", [])
        expected_core = int(checks.get("feature_columns_count", 11))
        if len(feature_cols) != expected_core:
            errors.append(f"manifest feature_columns={len(feature_cols)} (need {expected_core})")

        alchemy_cols = manifest.get("alchemy_feature_columns", [])
        expected_alchemy = int(checks.get("alchemy_feature_columns_count", 18))
        if len(alchemy_cols) != expected_alchemy:
            errors.append(
                f"manifest alchemy_feature_columns={len(alchemy_cols)} (need {expected_alchemy}); "
                "re-run data pipeline or pull latest data branch"
            )

    cache_path = root / "GoatProject-modeling/output/alchemy_cache.json"
    if cache_path.is_file():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        cache_checks = cfg.get("alchemy_cache_checks", {})
        expected_schema = str(cache_checks.get("schema_version", "2.0.0"))
        if str(cache.get("schema_version")) != expected_schema:
            errors.append(
                f"alchemy_cache schema_version={cache.get('schema_version')} (need {expected_schema})"
            )
        expected_dim = int(cache_checks.get("feature_dimension", 18))
        if int(cache.get("feature_dimension", 0)) != expected_dim:
            errors.append(f"alchemy_cache feature_dimension={cache.get('feature_dimension')} (need {expected_dim})")
        entries = cache.get("entries", {})
        min_pairs = int(cache_checks.get("min_pair_entries", 4000))
        if len(entries) < min_pairs:
            errors.append(f"alchemy_cache entries={len(entries)} (need >={min_pairs})")

    return errors


def main() -> int:
    root = find_root()
    cfg = load_checkpoint(root)
    errors = verify(root)
    if errors:
        print(f"Checkpoint {cfg.get('version')} ({cfg.get('label')}): FAIL", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print("\nFix: ./bootstrap.sh   or rebuild: ./run.sh", file=sys.stderr)
        return 1

    print(f"Checkpoint {cfg.get('version')} ({cfg.get('label')}): OK")
    print(f"  root: {root}")
    print("  View: ./open.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
