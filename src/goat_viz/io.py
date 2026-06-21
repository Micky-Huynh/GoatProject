from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


@dataclass(frozen=True)
class VizPaths:
    goat_root: Path
    viz_config: Path
    modeling_output: Path
    viz_output: Path
    posts_output: Path


@dataclass(frozen=True)
class VizArtifacts:
    config: dict[str, Any]
    rankings: pd.DataFrame
    pca_coordinates: pd.DataFrame
    pca_explained_variance: dict[str, Any]
    similarity_matrix: pd.DataFrame
    sensitivity_report: dict[str, Any]
    validation_report: dict[str, Any] | None
    career_vectors: pd.DataFrame | None = None


def resolve_goat_root(cli_goat_root: str | None = None) -> Path:
    if cli_goat_root:
        return Path(cli_goat_root).expanduser().resolve()

    env_root = os.getenv("GOAT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    return Path.cwd().resolve().parent


def build_paths(goat_root: Path) -> VizPaths:
    viz_worktree = goat_root / "GoatProject-viz"
    return VizPaths(
        goat_root=goat_root,
        viz_config=goat_root / "config" / "viz.yaml",
        modeling_output=goat_root / "GoatProject-modeling" / "output",
        viz_output=viz_worktree / "output",
        posts_output=viz_worktree / "output" / "posts",
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _require_file(path: Path, message: str) -> None:
    if not path.exists():
        raise FileNotFoundError(message)


def load_artifacts(cli_goat_root: str | None = None) -> tuple[VizPaths, VizArtifacts]:
    goat_root = resolve_goat_root(cli_goat_root)
    paths = build_paths(goat_root)

    _require_file(paths.viz_config, f"Missing viz config file: {paths.viz_config}")
    _require_file(
        paths.modeling_output / "sensitivity_report.json",
        "Missing sensitivity_report.json. Refusing to generate posts/ assets.",
    )
    _require_file(paths.modeling_output / "goat_rankings.csv", "Missing goat_rankings.csv")
    _require_file(paths.modeling_output / "pca_coordinates.csv", "Missing pca_coordinates.csv")
    _require_file(
        paths.modeling_output / "pca_explained_variance.json",
        "Missing pca_explained_variance.json",
    )

    with paths.viz_config.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    rankings = _read_csv(paths.modeling_output / "goat_rankings.csv")
    pca_coordinates = _read_csv(paths.modeling_output / "pca_coordinates.csv")
    pca_explained_variance = _read_json(paths.modeling_output / "pca_explained_variance.json")
    sensitivity_report = _read_json(paths.modeling_output / "sensitivity_report.json")

    similarity_path = paths.modeling_output / "similarity_matrix.csv"
    similarity_matrix = _read_csv(similarity_path) if similarity_path.exists() else pd.DataFrame()

    validation_path = paths.modeling_output / "validation_report.json"
    validation_report = _read_json(validation_path) if validation_path.exists() else None

    career_vectors_path = paths.goat_root / "GoatProject-data" / "processed" / "career_vectors.parquet"
    if not career_vectors_path.exists():
        career_vectors_path = paths.goat_root / "processed" / "career_vectors.parquet"
    career_vectors = (
        pd.read_parquet(career_vectors_path) if career_vectors_path.exists() else None
    )

    artifacts = VizArtifacts(
        config=config,
        rankings=rankings,
        pca_coordinates=pca_coordinates,
        pca_explained_variance=pca_explained_variance,
        similarity_matrix=similarity_matrix,
        sensitivity_report=sensitivity_report,
        validation_report=validation_report,
        career_vectors=career_vectors,
    )
    return paths, artifacts
