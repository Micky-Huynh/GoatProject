from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from goat_data.config import GoatPaths, load_yaml
from goat_data.era_adjust import _zscore_values
from goat_data.load import load_shooting_seasons


@dataclass
class ShootingZonesResult:
    career: pd.DataFrame


def _zones_config(paths: GoatPaths) -> dict:
    return load_yaml(paths.root / "config" / "scoring_zones.yaml")


def _zone_specs(cfg: dict) -> list[tuple[str, str, str, str | None]]:
    specs: list[tuple[str, str, str, str | None]] = []
    for zone_key, meta in cfg["zones"].items():
        specs.append((zone_key, meta["share_column"], meta["z_column"], meta.get("column")))
    return specs


def build_season_zone_shares(
    paths: GoatPaths,
    season_frame: pd.DataFrame,
) -> pd.DataFrame:
    cfg = _zones_config(paths)
    keys = season_frame[["player_id", "season", "pos"]].drop_duplicates().copy()
    shooting = load_shooting_seasons(paths)

    frame = keys.merge(shooting, on=["player_id", "season"], how="left", suffixes=("", "_shoot"))

    for zone_key, meta in cfg["zones"].items():
        share_col = meta["share_column"]
        if meta.get("derived"):
            corner = pd.to_numeric(frame[meta["inputs"]["corner_share"]], errors="coerce")
            three_range = pd.to_numeric(frame[meta["inputs"]["three_point_range"]], errors="coerce")
            frame[share_col] = corner * three_range
        else:
            frame[share_col] = pd.to_numeric(frame[meta["column"]], errors="coerce")

    share_cols = [meta["share_column"] for meta in cfg["zones"].values()]
    return frame[["player_id", "season", "pos", *share_cols]]


def _era_adjust_zone_shares(
    season_frame: pd.DataFrame,
    zone_specs: list[tuple[str, str, str, str | None]],
    pipeline_cfg: dict,
) -> pd.DataFrame:
    out = season_frame.copy()
    primary_cols = list(pipeline_cfg["era_adjustment"]["group_by"])
    min_group_n = int(pipeline_cfg["era_adjustment"]["min_group_n"])

    for _, share_col, z_col, _ in zone_specs:
        out[z_col] = np.nan
        for _, group in out.groupby(primary_cols, dropna=False):
            out.loc[group.index, z_col] = _zscore_values(group[share_col])

    group_sizes = out.groupby(primary_cols, dropna=False)["player_id"].transform("count")
    fallback_mask = group_sizes < min_group_n
    if fallback_mask.any():
        for _, share_col, z_col, _ in zone_specs:
            fallback = out.loc[fallback_mask].copy()
            for _, group in fallback.groupby(["season"], dropna=False):
                out.loc[group.index, z_col] = _zscore_values(group[share_col])

    return out


def build_career_shooting_zones(
    paths: GoatPaths,
    season_frame: pd.DataFrame,
) -> ShootingZonesResult:
    cfg = _zones_config(paths)
    pipeline_cfg = load_yaml(paths.pipeline)
    zone_specs = _zone_specs(cfg)

    season_zones = build_season_zone_shares(paths, season_frame)
    adjusted = _era_adjust_zone_shares(season_zones, zone_specs, pipeline_cfg)

    share_cols = [spec[1] for spec in zone_specs]
    z_cols = [spec[2] for spec in zone_specs]

    grouped = adjusted.groupby("player_id", as_index=False)
    career = grouped[share_cols + z_cols].mean()
    career[share_cols] = career[share_cols].fillna(0.0)
    career[z_cols] = career[z_cols].fillna(0.0)

    return ShootingZonesResult(career=career)
