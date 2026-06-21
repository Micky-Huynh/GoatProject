from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from goat_model.combine import (
    blend_vectors,
    build_alchemy_cache,
    canonical_pair_key,
    combine_players,
    lookup_cached_combine,
    nearest_neighbor,
    save_alchemy_cache,
)
from goat_model.io import load_career_vectors, load_context, load_manifest, load_yaml, z_columns_from_manifest


def _default_goat_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sample_context():
    ctx = load_context(_default_goat_root())
    manifest = load_manifest(ctx)
    careers = load_career_vectors(ctx, manifest)
    z_cols = z_columns_from_manifest(manifest)
    alchemy_cfg = load_yaml(ctx.root / "config" / "alchemy.yaml")
    return ctx, manifest, careers, z_cols, alchemy_cfg


def test_canonical_pair_key_is_order_independent() -> None:
    assert canonical_pair_key("b", "a") == canonical_pair_key("a", "b")


def test_blend_vectors_stays_in_r11() -> None:
    u = np.ones(11)
    v = np.arange(11, dtype=float)
    w = blend_vectors(u, v, alpha=0.5, beta=0.5)
    assert w.shape == (11,)


def test_combine_same_pair_always_same_result() -> None:
    _, manifest, careers, z_cols, alchemy_cfg = _sample_context()
    ids = careers["player_id"].astype(str).tolist()
    first = combine_players(ids[0], ids[1], careers, z_cols, alchemy_cfg)
    second = combine_players(ids[1], ids[0], careers, z_cols, alchemy_cfg)
    assert first["nearest_player_id"] == second["nearest_player_id"]
    assert first["blend_vector"] == second["blend_vector"]
    assert len(first["blend_vector"]) == 11


def test_nearest_neighbor_self_is_zero_distance() -> None:
    _, _, careers, z_cols, _ = _sample_context()
    pool = careers[z_cols].to_numpy(dtype=float)
    blend = pool[0]
    pid, _, dist = nearest_neighbor(
        blend,
        pool,
        careers["player_id"].astype(str).tolist(),
        careers["display_name"].astype(str).tolist(),
        metric="l2",
    )
    assert pid == str(careers.iloc[0]["player_id"])
    assert dist == pytest.approx(0.0, abs=1e-9)


def test_cache_hash_invalidation() -> None:
    _, manifest, careers, z_cols, alchemy_cfg = _sample_context()
    cache = build_alchemy_cache(careers, z_cols, alchemy_cfg, manifest)
    ids = careers["player_id"].astype(str).tolist()
    entry = lookup_cached_combine(ids[0], ids[1], cache, expected_config_hash=cache["config_hash"])
    assert entry is not None
    assert lookup_cached_combine(ids[0], ids[1], cache, expected_config_hash="deadbeef") is None


def test_build_and_save_cache_roundtrip(tmp_path: Path) -> None:
    _, manifest, careers, z_cols, alchemy_cfg = _sample_context()
    cache = build_alchemy_cache(careers.head(5), z_cols, alchemy_cfg, manifest)
    out = tmp_path / "alchemy_cache.json"
    save_alchemy_cache(out, cache)
    assert out.exists()
    assert len(cache["entries"]) == 10
