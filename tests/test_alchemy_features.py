from __future__ import annotations

from pathlib import Path

from goat_model.io import (
    alchemy_z_columns_from_manifest,
    load_context,
    load_manifest,
    z_columns_from_manifest,
)


def _default_goat_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_alchemy_columns_are_distinct_from_ranking_columns() -> None:
    ctx = load_context(_default_goat_root())
    manifest = load_manifest(ctx)
    ranking_cols = z_columns_from_manifest(manifest)
    alchemy_cols = alchemy_z_columns_from_manifest(manifest)

    assert len(ranking_cols) == 11
    assert len(alchemy_cols) == 18
    assert set(ranking_cols).issubset(set(alchemy_cols))
    assert alchemy_cols != ranking_cols
    assert alchemy_cols[:11] == ranking_cols
    assert set(alchemy_cols) - set(ranking_cols) == {
        "showman_z",
        "zone_0_3_z",
        "zone_3_10_z",
        "zone_10_16_z",
        "zone_16_3p_z",
        "zone_3p_z",
        "zone_corner3_z",
    }
