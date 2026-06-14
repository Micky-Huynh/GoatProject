from __future__ import annotations

import pandas as pd

from goat_data.config import GoatPaths, feature_spec, load_yaml


def _pick_advanced_row(group: pd.DataFrame) -> pd.Series:
    totals = group[group["team"].astype(str).str.endswith("TM", na=False)]
    if not totals.empty:
        return totals.iloc[0]
    return group.sort_values("mp", ascending=False).iloc[0]


def _pick_season_info_row(group: pd.DataFrame) -> pd.Series:
    totals = group[group["team"].astype(str).str.endswith("TM", na=False)]
    if not totals.empty:
        return totals.iloc[0]
    return group.iloc[0]


def _dedupe_player_season(frame: pd.DataFrame, pick_fn) -> pd.DataFrame:
    rows = [pick_fn(group) for _, group in frame.groupby(["player_id", "season"], sort=False)]
    return pd.DataFrame(rows).reset_index(drop=True)


def load_advanced_seasons(paths: GoatPaths) -> pd.DataFrame:
    features_cfg = load_yaml(paths.features)
    _, name_to_column, _, _ = feature_spec(features_cfg)
    raw_columns = sorted(set(name_to_column.values()))

    advanced = pd.read_csv(paths.raw_data / "Advanced.csv")
    keep = ["player_id", "player", "season", "team", "pos", "mp", *raw_columns]
    advanced = _dedupe_player_season(advanced[keep], _pick_advanced_row)

    season_info = pd.read_csv(paths.raw_data / "Player Season Info.csv")
    season_info = _dedupe_player_season(season_info, _pick_season_info_row)
    season_info = season_info[["player_id", "season", "age"]]

    frame = advanced.merge(season_info, on=["player_id", "season"], how="left")
    frame["season"] = frame["season"].astype(int)
    frame["mp"] = pd.to_numeric(frame["mp"], errors="coerce")
    for column in raw_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame
