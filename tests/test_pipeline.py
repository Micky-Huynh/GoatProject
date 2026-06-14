from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from goat_data.config import PRE_THREE_POINT_LINE_SEASON, resolve_paths, z_column
from goat_data.era_adjust import _zscore_values, era_adjust
from goat_data.load import load_advanced_seasons
from goat_data.players import resolve_allowlist
from goat_data.run_pipeline import _filter_seasons, run


@pytest.fixture(scope="module")
def paths():
    return resolve_paths()


@pytest.fixture(scope="module")
def allowlist(paths):
    return resolve_allowlist(paths)


def test_full_league_zscore_before_allowlist_filter(paths, allowlist):
    raw = load_advanced_seasons(paths)
    result = era_adjust(raw, paths, allowlist.pre_three_point_line_players)
    adjusted = result.frame

    assert len(adjusted) == len(raw)
    assert adjusted["player_id"].nunique() > len(allowlist.player_ids)

    sample = adjusted[(adjusted["season"] == 2020) & (adjusted["pos"] == "PG")].dropna(subset=["bpm"])
    z = (sample["bpm"] - sample["bpm"].mean()) / sample["bpm"].std(ddof=0)
    assert np.allclose(sample["bpm_z"].values, z.values, equal_nan=True, atol=1e-6)


def test_kareem_moses_pre_three_point_excludes_x3p(paths, allowlist):
    raw = load_advanced_seasons(paths)
    result = era_adjust(raw, paths, allowlist.pre_three_point_line_players)
    flagged = result.frame[
        result.frame["player_id"].isin(allowlist.pre_three_point_line_players)
        & (result.frame["season"] < PRE_THREE_POINT_LINE_SEASON)
    ]
    assert not flagged.empty
    assert flagged["x3p_ar"].isna().all()
    assert flagged["x3p_ar_z"].isna().all()


def test_bpm_missing_seasons_dropped(paths):
    pipeline_cfg = __import__("goat_data.config", fromlist=["load_yaml"]).load_yaml(paths.pipeline)
    raw = load_advanced_seasons(paths)
    raw.loc[raw.index[0], "bpm"] = np.nan
    filtered, drops = _filter_seasons(raw, pipeline_cfg)
    assert drops["dropped_missing_core"] >= 1
    assert filtered["bpm"].notna().all()
    assert filtered["vorp"].notna().all()


def test_zero_std_fallback():
    series = pd.Series([5.0, 5.0, 5.0])
    z = _zscore_values(series)
    assert (z == 0.0).all()


def test_pipeline_outputs(paths):
    manifest = run(paths.root)
    assert manifest["player_count"] == 21

    processed = paths.processed
    assert (processed / "career_vectors.parquet").exists()
    assert (processed / "season_labels.parquet").exists()
    assert (processed / "league_career_covariance.npy").exists()

    career = pd.read_parquet(processed / "career_vectors.parquet")
    assert len(career) == 21

    with (processed / "manifest.json").open(encoding="utf-8") as handle:
        saved = json.load(handle)
    assert "config_hashes" in saved
    assert "raw_csv_checksums" in saved
    assert "feature_correlation_max" in saved
    assert "covariance_condition_number" in saved
    assert "label_stats" in saved
    assert saved["era_adjustment"]["fallback_row_count"] >= 0
