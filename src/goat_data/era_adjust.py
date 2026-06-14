from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from goat_data.config import (
    PRE_THREE_POINT_LINE_SEASON,
    GoatPaths,
    feature_spec,
    load_yaml,
    z_column,
)


@dataclass
class EraAdjustResult:
    frame: pd.DataFrame
    fallback_row_count: int
    group_levels_used: dict[str, int]


def _zscore_values(values: pd.Series) -> pd.Series:
    valid = values.dropna()
    if valid.empty:
        return pd.Series(np.nan, index=values.index)
    std = valid.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(0.0, index=values.index)
    mean = valid.mean()
    return (values - mean) / std


def _assign_group_zscores(
    frame: pd.DataFrame,
    group_cols: list[str],
    feature_names: list[str],
    name_to_column: dict[str, str],
) -> pd.DataFrame:
    out = frame.copy()
    z_cols = [z_column(name) for name in feature_names]
    for col in z_cols:
        out[col] = np.nan

    for _, group in out.groupby(group_cols, dropna=False):
        for name in feature_names:
            raw_col = name_to_column[name]
            out.loc[group.index, z_column(name)] = _zscore_values(group[raw_col])
    return out


def era_adjust(
    frame: pd.DataFrame,
    paths: GoatPaths,
    pre_three_player_ids: set[str],
) -> EraAdjustResult:
    features_cfg = load_yaml(paths.features)
    pipeline_cfg = load_yaml(paths.pipeline)
    feature_names, name_to_column, orientation, pre_three_excluded = feature_spec(features_cfg)

    working = frame.copy()
    working["pre_three_point_line"] = working["player_id"].isin(pre_three_player_ids) & (
        working["season"] < PRE_THREE_POINT_LINE_SEASON
    )

    for name in pre_three_excluded:
        raw_col = name_to_column[name]
        working.loc[working["pre_three_point_line"], raw_col] = np.nan

    primary_cols = list(pipeline_cfg["era_adjustment"]["group_by"])
    min_group_n = int(pipeline_cfg["era_adjustment"]["min_group_n"])

    adjusted = _assign_group_zscores(working, primary_cols, feature_names, name_to_column)

    group_sizes = adjusted.groupby(primary_cols, dropna=False)["player_id"].transform("count")
    fallback_mask = group_sizes < min_group_n
    fallback_row_count = int(fallback_mask.sum())

    if fallback_mask.any():
        season_adjusted = _assign_group_zscores(
            working.loc[fallback_mask],
            ["season"],
            feature_names,
            name_to_column,
        )
        z_cols = [z_column(name) for name in feature_names]
        adjusted.loc[fallback_mask, z_cols] = season_adjusted[z_cols].to_numpy()

    for name, orient in orientation.items():
        adjusted[z_column(name)] = adjusted[z_column(name)] * orient

    levels = {
        "season_pos_groups": int(adjusted.groupby(primary_cols, dropna=False).ngroups),
        "fallback_rows": fallback_row_count,
    }
    return EraAdjustResult(
        frame=adjusted,
        fallback_row_count=fallback_row_count,
        group_levels_used=levels,
    )
