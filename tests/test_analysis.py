from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from goat_model.run_analysis import run


def _default_goat_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_analysis_artifacts_are_written() -> None:
    paths = run(_default_goat_root())
    required = {
        "similarity_matrix",
        "pca_coordinates",
        "pca_explained_variance",
        "pca_loadings",
        "uniqueness",
    }
    assert required.issubset(paths.keys())
    for path in paths.values():
        assert path.exists()


def test_similarity_matrix_shape_and_diagonal() -> None:
    paths = run(_default_goat_root())
    similarity = pd.read_csv(paths["similarity_matrix"], index_col="player_id")
    assert similarity.shape == (100, 100)
    assert similarity.index.tolist() == similarity.columns.tolist()
    assert np.allclose(similarity.values.diagonal(), 1.0, atol=1e-12)


def test_pca_variance_payload_and_coordinates() -> None:
    paths = run(_default_goat_root())
    coords = pd.read_csv(paths["pca_coordinates"])
    assert {"player_id", "display_name", "PC1", "PC2"}.issubset(coords.columns)
    assert len(coords) == 100

    with paths["pca_explained_variance"].open(encoding="utf-8") as handle:
        payload = json.load(handle)
    assert "components" in payload
    assert "cumulative_variance" in payload
    assert len(payload["components"]) >= 2
    assert {"component", "explained_variance_ratio", "cumulative_explained_variance"}.issubset(
        payload["components"][0].keys()
    )


def test_uniqueness_fields() -> None:
    paths = run(_default_goat_root())
    uniqueness = pd.read_csv(paths["uniqueness"])
    expected = {
        "player_id",
        "display_name",
        "nearest_neighbor_player_id",
        "nearest_neighbor_similarity",
        "uniqueness",
    }
    assert expected.issubset(uniqueness.columns)
    assert len(uniqueness) == 100
