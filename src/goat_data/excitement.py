from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from goat_data.config import GoatPaths, load_yaml
from goat_data.era_adjust import _zscore_values
from goat_data.labels import build_season_labels
from goat_data.load import load_play_by_play_seasons, load_player_totals_seasons, load_shooting_seasons

SEASON_Z_COMPONENTS = ("dunk_freq", "and1_rate", "all_star_rate", "heave_rate")
WEIGHT_KEYS = ("dunk_freq", "and1_rate", "all_star_rate", "mvp_share_peak", "heave_rate")
EXCLUDED_PARTIAL = frozenset({"dunk_freq", "and1_rate"})


@dataclass
class ExcitementResult:
    career: pd.DataFrame


def _showman_config(paths: GoatPaths) -> dict:
    return load_yaml(paths.root / "config" / "showman.yaml")


def renormalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Showman weights must sum to a positive value")
    return {key: value / total for key, value in weights.items()}


def active_showman_weights(cfg: dict, partial: bool) -> dict[str, float]:
    if partial:
        raw = {
            key: value
            for key, value in cfg["weights"]["legacy_partial"].items()
            if key not in EXCLUDED_PARTIAL
        }
        return renormalize_weights(raw)
    return renormalize_weights(cfg["weights"]["full"])


def _build_all_star_flags(paths: GoatPaths, season_keys: pd.DataFrame) -> pd.DataFrame:
    cfg = _showman_config(paths)
    asg = pd.read_csv(paths.raw_data / cfg["sources"]["all_star"])
    selected = asg[["player_id", "season"]].drop_duplicates()
    selected["all_star"] = 1
    out = season_keys.merge(selected, on=["player_id", "season"], how="left")
    out["all_star"] = out["all_star"].fillna(0).astype(int)
    return out


def build_season_excitement(
    paths: GoatPaths,
    season_frame: pd.DataFrame,
) -> pd.DataFrame:
    keys = season_frame[["player_id", "season", "pos"]].drop_duplicates().copy()
    shooting = load_shooting_seasons(paths)
    pbp = load_play_by_play_seasons(paths)
    totals = load_player_totals_seasons(paths)

    frame = keys.merge(
        shooting[["player_id", "season", "percent_dunks_of_fga", "num_heaves_attempted"]],
        on=["player_id", "season"],
        how="left",
    )
    frame = frame.merge(pbp[["player_id", "season", "and1"]], on=["player_id", "season"], how="left")
    frame = frame.merge(totals[["player_id", "season", "fga"]], on=["player_id", "season"], how="left")

    frame["dunk_freq"] = frame["percent_dunks_of_fga"]
    frame["and1_rate"] = np.where(frame["fga"] > 0, frame["and1"] / frame["fga"], np.nan)
    frame["heave_rate"] = np.where(frame["fga"] > 0, frame["num_heaves_attempted"] / frame["fga"], np.nan)

    asg = _build_all_star_flags(paths, keys[["player_id", "season"]])
    frame = frame.merge(asg, on=["player_id", "season"], how="left")
    frame["all_star_rate"] = frame["all_star"].astype(float)

    labels, _ = build_season_labels(paths, keys[["player_id", "season"]])
    frame = frame.merge(labels[["player_id", "season", "mvp_vote_share"]], on=["player_id", "season"], how="left")
    frame["mvp_vote_share"] = frame["mvp_vote_share"].fillna(0.0)

    return frame[
        ["player_id", "season", "pos", "dunk_freq", "and1_rate", "all_star_rate", "heave_rate", "mvp_vote_share"]
    ]


def _era_adjust_components(
    season_frame: pd.DataFrame,
    pipeline_cfg: dict,
) -> pd.DataFrame:
    out = season_frame.copy()
    primary_cols = list(pipeline_cfg["era_adjustment"]["group_by"])
    min_group_n = int(pipeline_cfg["era_adjustment"]["min_group_n"])

    for component in SEASON_Z_COMPONENTS:
        z_col = f"{component}_z"
        out[z_col] = np.nan
        for _, group in out.groupby(primary_cols, dropna=False):
            out.loc[group.index, z_col] = _zscore_values(group[component])

    group_sizes = out.groupby(primary_cols, dropna=False)["player_id"].transform("count")
    fallback_mask = group_sizes < min_group_n
    if fallback_mask.any():
        for component in SEASON_Z_COMPONENTS:
            z_col = f"{component}_z"
            fallback = out.loc[fallback_mask].copy()
            for _, group in fallback.groupby(["season"], dropna=False):
                out.loc[group.index, z_col] = _zscore_values(group[component])

    return out


def _partial_mask(season_frame: pd.DataFrame) -> pd.Series:
    grouped = season_frame.groupby("player_id", as_index=True)
    dunk_missing = grouped["dunk_freq"].apply(lambda values: values.isna().any())
    and1_missing = grouped["and1_rate"].apply(lambda values: values.isna().any())
    return dunk_missing | and1_missing


def _weighted_showman_raw(row: pd.Series, weights: dict[str, float]) -> float:
    available: dict[str, float] = {}
    for component, weight in weights.items():
        z_col = f"{component}_z"
        value = row.get(z_col)
        if pd.isna(value):
            continue
        available[component] = weight
    if not available:
        return float("nan")
    normalized = renormalize_weights(available)
    total = 0.0
    for component, weight in normalized.items():
        total += weight * float(row[f"{component}_z"])
    return total


def build_career_excitement(
    paths: GoatPaths,
    season_frame: pd.DataFrame,
    allowlist_player_ids: list[str],
) -> ExcitementResult:
    cfg = _showman_config(paths)
    pipeline_cfg = load_yaml(paths.pipeline)
    season_excitement = build_season_excitement(paths, season_frame)
    adjusted = _era_adjust_components(season_excitement, pipeline_cfg)

    z_cols = [f"{name}_z" for name in SEASON_Z_COMPONENTS]
    career = adjusted.groupby("player_id", as_index=False).agg(
        **{z_col: (z_col, "mean") for z_col in z_cols},
        dunk_freq=("dunk_freq", "mean"),
        and1_rate=("and1_rate", "mean"),
        all_star_rate=("all_star_rate", "mean"),
        heave_rate=("heave_rate", "mean"),
        mvp_share_peak=("mvp_vote_share", "max"),
    )

    partial = _partial_mask(season_excitement)
    career["showman_partial"] = career["player_id"].map(partial).fillna(False).astype(bool)

    allowlist_mask = career["player_id"].isin(allowlist_player_ids)
    career["mvp_share_peak_z"] = np.nan
    peaks = career.loc[allowlist_mask, "mvp_share_peak"]
    career.loc[allowlist_mask, "mvp_share_peak_z"] = _zscore_values(peaks).values

    showman_raw = []
    for _, row in career.iterrows():
        weights = active_showman_weights(cfg, bool(row["showman_partial"]))
        showman_raw.append(_weighted_showman_raw(row, weights))
    career["showman_raw"] = showman_raw

    career["showman_z"] = np.nan
    allowlist = career.loc[allowlist_mask, "showman_raw"]
    career.loc[allowlist_mask, "showman_z"] = _zscore_values(allowlist).values

    return ExcitementResult(career=career)
