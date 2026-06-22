from __future__ import annotations

import numpy as np
import pytest

from goat_data.config import load_yaml, resolve_paths
from goat_data.load import load_advanced_seasons
from goat_data.players import resolve_allowlist
from goat_data.run_pipeline import _filter_seasons
from goat_data.shooting_zones import build_season_zone_shares
from goat_data.era_adjust import era_adjust


@pytest.fixture(scope="module")
def paths():
    return resolve_paths()


@pytest.fixture(scope="module")
def allowlist(paths):
    return resolve_allowlist(paths)


def test_zone_shares_sum_to_one(paths, allowlist):
    pipeline_cfg = load_yaml(paths.pipeline)
    raw = load_advanced_seasons(paths)
    era_result = era_adjust(raw, paths, allowlist.pre_three_point_line_players)
    filtered, _ = _filter_seasons(era_result.frame, pipeline_cfg)
    allowlist_seasons = filtered[filtered["player_id"].isin(allowlist.player_ids)].copy()

    season_zones = build_season_zone_shares(paths, allowlist_seasons)
    zones_cfg = load_yaml(paths.root / "config" / "scoring_zones.yaml")
    share_cols = [
        meta["share_column"]
        for meta in zones_cfg["zones"].values()
        if not meta.get("derived")
    ]

    totals = season_zones[share_cols].sum(axis=1)
    valid = totals[totals > 0]
    assert not valid.empty
    assert np.allclose(valid, 1.0, atol=0.05)
