from __future__ import annotations

import pandas as pd

from goat_data.config import z_column


def aggregate_career_vectors(
    season_vectors: pd.DataFrame,
    feature_names: list[str],
    display_names: dict[str, str],
) -> pd.DataFrame:
    z_cols = [z_column(name) for name in feature_names]
    grouped = season_vectors.groupby("player_id", as_index=False)
    career = grouped[z_cols].mean()
    # Missing-era features (e.g. x3p_ar pre-1979, sparse usg/tov) have no finite seasons;
    # treat absent coordinates as neutral (population mean in z-space).
    career[z_cols] = career[z_cols].fillna(0.0)
    counts = grouped.agg(season_count=("season", "count"))
    career = career.merge(counts, on="player_id")
    career["display_name"] = career["player_id"].map(display_names)
    return career
