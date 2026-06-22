from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goat_data.config import load_yaml, resolve_paths
from goat_data.excitement import (
    active_showman_weights,
    build_career_excitement,
    build_season_excitement,
    renormalize_weights,
)
from goat_data.players import resolve_allowlist
from goat_data.run_pipeline import _filter_seasons


@pytest.fixture(scope="module")
def paths():
    return resolve_paths()


@pytest.fixture(scope="module")
def allowlist(paths):
    return resolve_allowlist(paths)


def test_partial_reweight_sums_to_one(paths):
    cfg = load_yaml(paths.root / "config" / "showman.yaml")
    weights = active_showman_weights(cfg, partial=True)
    assert pytest.approx(sum(weights.values()), rel=0, abs=1e-9) == 1.0
    assert "dunk_freq" not in weights
    assert "and1_rate" not in weights


def test_full_weights_sum_to_one(paths):
    cfg = load_yaml(paths.root / "config" / "showman.yaml")
    weights = active_showman_weights(cfg, partial=False)
    assert pytest.approx(sum(weights.values()), rel=0, abs=1e-9) == 1.0


def test_legacy_partial_renormalize_matches_config(paths):
    cfg = load_yaml(paths.root / "config" / "showman.yaml")
    raw = cfg["weights"]["legacy_partial"]
    active = {k: v for k, v in raw.items() if k not in {"dunk_freq", "and1_rate"}}
    expected = renormalize_weights(active)
    assert active_showman_weights(cfg, partial=True) == expected


def test_partial_players_exclude_dunk_and1_from_composite(paths, allowlist):
    pipeline_cfg = load_yaml(paths.pipeline)
    from goat_data.load import load_advanced_seasons
    from goat_data.era_adjust import era_adjust

    raw = load_advanced_seasons(paths)
    era_result = era_adjust(raw, paths, allowlist.pre_three_point_line_players)
    filtered, _ = _filter_seasons(era_result.frame, pipeline_cfg)
    allowlist_seasons = filtered[filtered["player_id"].isin(allowlist.player_ids)].copy()

    season_excitement = build_season_excitement(paths, allowlist_seasons)
    result = build_career_excitement(paths, allowlist_seasons, allowlist.player_ids)
    career = result.career

    partial_ids = set(career.loc[career["showman_partial"], "player_id"])
    assert partial_ids

    for player_id in partial_ids:
        row = career.loc[career["player_id"] == player_id].iloc[0]
        cfg = load_yaml(paths.root / "config" / "showman.yaml")
        weights = active_showman_weights(cfg, partial=True)

        from goat_data.excitement import _weighted_showman_raw

        expected = _weighted_showman_raw(row, weights)

        assert np.isfinite(row["showman_raw"])
        assert row["showman_raw"] == pytest.approx(expected, rel=1e-6, abs=1e-6)

        player_seasons = season_excitement[season_excitement["player_id"] == player_id]
        assert player_seasons["dunk_freq"].isna().any() or player_seasons["and1_rate"].isna().any()


def test_partial_ignores_dunk_and1_z(paths, allowlist):
    pipeline_cfg = load_yaml(paths.pipeline)
    from goat_data.era_adjust import era_adjust
    from goat_data.excitement import _weighted_showman_raw
    from goat_data.load import load_advanced_seasons

    raw = load_advanced_seasons(paths)
    era_result = era_adjust(raw, paths, allowlist.pre_three_point_line_players)
    filtered, _ = _filter_seasons(era_result.frame, pipeline_cfg)
    allowlist_seasons = filtered[filtered["player_id"].isin(allowlist.player_ids)].copy()

    result = build_career_excitement(paths, allowlist_seasons, allowlist.player_ids)
    career = result.career
    cfg = load_yaml(paths.root / "config" / "showman.yaml")

    partial = career[career["showman_partial"]].head(1)
    assert not partial.empty
    row = partial.iloc[0].copy()
    weights = active_showman_weights(cfg, partial=True)
    baseline = _weighted_showman_raw(row, weights)

    row["dunk_freq_z"] = 99.0
    row["and1_rate_z"] = -99.0
    assert _weighted_showman_raw(row, weights) == pytest.approx(baseline, rel=0, abs=1e-9)

