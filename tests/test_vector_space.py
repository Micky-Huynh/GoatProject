from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from goat_data.config import feature_spec, load_yaml, resolve_paths, z_column
from goat_data.run_pipeline import run


@pytest.fixture(scope="module")
def paths():
    return resolve_paths()


@pytest.fixture(scope="module")
def manifest(paths):
    return run(paths.root)


def test_ambient_real_vector_space_axioms():
    """Axioms for V = R^d with standard operations (§7.0.1)."""
    rng = np.random.default_rng(0)
    d = 11
    u = rng.normal(size=d)
    v = rng.normal(size=d)
    alpha = 1.75
    beta = -0.4

    w = u + v
    assert w.shape == (d,)
    assert np.allclose(w, v + u)

    scaled = alpha * u
    assert scaled.shape == (d,)
    assert np.allclose(scaled, u * alpha)

    assert np.allclose(u + (-u), np.zeros(d))
    assert np.allclose(alpha * (u + v), alpha * u + alpha * v)
    assert np.allclose((alpha + beta) * u, alpha * u + beta * u)
    assert np.allclose(1.0 * u, u)


def test_manifest_vector_space_metadata(manifest):
    vs = manifest["vector_space"]
    assert vs["ambient_space"] == "R^d_standard"
    assert vs["field"] == "R"
    assert vs["embeddings_are_subspace"] is False
    assert vs["feature_dimension"] == len(manifest["feature_columns"])
    assert vs["feature_dimension"] == 11


def test_career_vectors_fixed_finite_dimension(paths, manifest):
    processed = paths.processed
    career = pd.read_parquet(processed / "career_vectors.parquet")
    z_cols = manifest["feature_columns"]

    assert len(career) == manifest["player_count"] == 100
    assert len(z_cols) == manifest["vector_space"]["feature_dimension"]

    values = career[z_cols].to_numpy(dtype=float)
    assert values.shape == (manifest["player_count"], 11)
    assert np.isfinite(values).all()


def test_allowlist_embeddings_not_closed_under_addition(paths, manifest):
    """Falsification: sum of two career embeddings is not a pipeline-produced row."""
    career = pd.read_parquet(paths.processed / "career_vectors.parquet")
    z_cols = manifest["feature_columns"]
    vectors = career.set_index("player_id")[z_cols].to_numpy(dtype=float)

    combined = vectors[0] + vectors[1]
    distances = np.linalg.norm(vectors - combined, axis=1)
    assert distances.min() > 1e-6


def test_saved_manifest_matches_run(paths, manifest):
    saved = json.loads((paths.processed / "manifest.json").read_text(encoding="utf-8"))
    assert saved["vector_space"] == manifest["vector_space"]


def test_feature_dimension_matches_config(paths, manifest):
    features_cfg = load_yaml(paths.features)
    feature_names, _, _, _ = feature_spec(features_cfg)
    z_cols = [z_column(name) for name in feature_names]
    assert manifest["feature_columns"] == z_cols
    assert manifest["vector_space"]["feature_dimension"] == len(z_cols)


def test_alchemy_feature_columns_length(manifest):
    assert len(manifest["feature_columns"]) == 11
    assert len(manifest["alchemy_feature_columns"]) == 18
    assert manifest["vector_space"]["alchemy_feature_dimension"] == 18

