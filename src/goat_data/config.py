from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PIPELINE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
PRE_THREE_POINT_LINE_SEASON = 1980
RIDGE_EPSILON = 1e-4


@dataclass(frozen=True)
class GoatPaths:
    root: Path
    raw_data: Path
    processed: Path
    allowlist: Path
    features: Path
    labels: Path
    pipeline: Path


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def find_goat_root(start: Path | None = None) -> Path:
    env = os.environ.get("GOAT_ROOT")
    if env:
        root = Path(env).expanduser().resolve()
        if (root / "config" / "allowlist.yaml").is_file():
            return root
        raise FileNotFoundError(f"GOAT_ROOT={root} missing config/allowlist.yaml")

    cursor = (start or Path(__file__)).resolve()
    for parent in cursor.parents:
        if (parent / "config" / "allowlist.yaml").is_file():
            return parent

    raise FileNotFoundError("Could not locate GoatProject root (set GOAT_ROOT)")


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def resolve_paths(root: Path | None = None) -> GoatPaths:
    goat_root = root or find_goat_root()
    data_dir = goat_root / "GoatProject-data"
    return GoatPaths(
        root=goat_root,
        raw_data=data_dir / "data",
        processed=data_dir / "processed",
        allowlist=goat_root / "config" / "allowlist.yaml",
        features=goat_root / "config" / "features.yaml",
        labels=goat_root / "config" / "labels.yaml",
        pipeline=goat_root / "config" / "pipeline.yaml",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def config_hashes(paths: GoatPaths) -> dict[str, str]:
    return {
        "pipeline.yaml": sha256_file(paths.pipeline),
        "features.yaml": sha256_file(paths.features),
        "labels.yaml": sha256_file(paths.labels),
        "allowlist.yaml": sha256_file(paths.allowlist),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")


def feature_spec(features_cfg: dict[str, Any]) -> tuple[list[str], dict[str, str], dict[str, int], list[str]]:
    name_to_column: dict[str, str] = {}
    orientation: dict[str, int] = {}
    pre_three_excluded: list[str] = []
    for name, meta in features_cfg["features"].items():
        name_to_column[name] = meta["column"]
        orientation[name] = int(meta["orient"])
        if meta.get("exclude_when_pre_three_point_line"):
            pre_three_excluded.append(name)
    return list(features_cfg["features"].keys()), name_to_column, orientation, pre_three_excluded


def z_column(feature_name: str) -> str:
    return f"{feature_name}_z"
