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

def load_shooting_seasons(paths: GoatPaths) -> pd.DataFrame:
    shooting = pd.read_csv(paths.raw_data / "Player Shooting.csv")
    keep = [
        "player_id",
        "player",
        "season",
        "team",
        "pos",
        "mp",
        "percent_fga_from_x0_3_range",
        "percent_fga_from_x3_10_range",
        "percent_fga_from_x10_16_range",
        "percent_fga_from_x16_3p_range",
        "percent_fga_from_x3p_range",
        "percent_corner_3s_of_3pa",
        "percent_dunks_of_fga",
        "num_heaves_attempted",
    ]
    frame = _dedupe_player_season(shooting[keep], _pick_advanced_row)
    frame["season"] = frame["season"].astype(int)
    frame["mp"] = pd.to_numeric(frame["mp"], errors="coerce")
    numeric_cols = [col for col in keep if col not in {"player_id", "player", "season", "team", "pos"}]
    for column in numeric_cols:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def load_play_by_play_seasons(paths: GoatPaths) -> pd.DataFrame:
    pbp = pd.read_csv(paths.raw_data / "Player Play By Play.csv")
    keep = ["player_id", "player", "season", "team", "pos", "mp", "and1"]
    frame = _dedupe_player_season(pbp[keep], _pick_advanced_row)
    frame["season"] = frame["season"].astype(int)
    frame["mp"] = pd.to_numeric(frame["mp"], errors="coerce")
    frame["and1"] = pd.to_numeric(frame["and1"], errors="coerce")
    return frame


def load_player_totals_seasons(paths: GoatPaths) -> pd.DataFrame:
    totals = pd.read_csv(paths.raw_data / "Player Totals.csv")
    keep = ["player_id", "player", "season", "team", "pos", "mp", "fga"]
    frame = _dedupe_player_season(totals[keep], _pick_advanced_row)
    frame["season"] = frame["season"].astype(int)
    frame["mp"] = pd.to_numeric(frame["mp"], errors="coerce")
    frame["fga"] = pd.to_numeric(frame["fga"], errors="coerce")
    return frame

