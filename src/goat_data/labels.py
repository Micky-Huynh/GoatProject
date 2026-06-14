from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from goat_data.config import GoatPaths, load_yaml


@dataclass
class LabelStats:
    mvp_rows: int
    all_nba_first_rows: int
    all_nba_any_rows: int
    seasons_labeled: int


def _filter_frame(frame: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    out = frame.copy()
    for key, expected in filters.items():
        if isinstance(expected, list):
            out = out[out[key].isin(expected)]
        else:
            out = out[out[key] == expected]
    return out


def build_season_labels(
    paths: GoatPaths,
    season_keys: pd.DataFrame,
) -> tuple[pd.DataFrame, LabelStats]:
    cfg = load_yaml(paths.labels)
    keys = season_keys[["player_id", "season"]].drop_duplicates().copy()
    labels = keys.copy()

    mvp_cfg = cfg["mvp_vote_share"]
    mvp = pd.read_csv(paths.raw_data / mvp_cfg["source_file"])
    mvp = _filter_frame(mvp, mvp_cfg["filter"])
    mvp = mvp[["player_id", "season", mvp_cfg["value_column"]]].rename(
        columns={mvp_cfg["value_column"]: mvp_cfg["output_column"]}
    )
    labels = labels.merge(mvp, on=["player_id", "season"], how="left")
    labels[mvp_cfg["output_column"]] = labels[mvp_cfg["output_column"]].fillna(
        mvp_cfg["default_when_missing"]
    )

    for label_key in ("all_nba_first", "all_nba_any"):
        label_cfg = cfg[label_key]
        teams = pd.read_csv(paths.raw_data / label_cfg["source_file"])
        teams = _filter_frame(teams, label_cfg["filter"])
        teams = teams[["player_id", "season"]].drop_duplicates()
        teams[label_cfg["output_column"]] = label_cfg["value"]
        labels = labels.merge(teams, on=["player_id", "season"], how="left")
        labels[label_cfg["output_column"]] = labels[label_cfg["output_column"]].fillna(
            label_cfg["default_when_missing"]
        ).astype(int)

    stats = LabelStats(
        mvp_rows=int((labels["mvp_vote_share"] > 0).sum()),
        all_nba_first_rows=int(labels["all_nba_first"].sum()),
        all_nba_any_rows=int(labels["all_nba_any"].sum()),
        seasons_labeled=int(len(labels)),
    )
    return labels, stats
