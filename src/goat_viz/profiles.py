from __future__ import annotations

from typing import Any

import pandas as pd


def _default_aspects() -> dict[str, dict[str, Any]]:
    return {
        "overall": {
            "label": "Overall impact",
            "features": ["bpm_z", "vorp_z", "per_z", "ws_z"],
        },
        "scoring": {
            "label": "Scoring",
            "features": ["ts_percent_z", "usg_percent_z", "x3p_ar_z"],
        },
        "playmaking": {
            "label": "Playmaking",
            "features": ["ast_percent_z"],
        },
        "defense": {
            "label": "Defense",
            "features": ["stl_percent_z", "blk_percent_z"],
        },
        "ball_security": {
            "label": "Ball security",
            "features": ["tov_percent_z"],
        },
    }


def _aspect_config(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    configured = config.get("skill_aspects")
    if not configured:
        return _default_aspects()
    return configured


def _cohort_score_0_100(values: pd.Series) -> pd.Series:
    min_val = float(values.min())
    max_val = float(values.max())
    span = max(max_val - min_val, 1e-9)
    return ((values - min_val) / span * 100.0).clip(0.0, 100.0)


def compute_player_profiles(
    career_vectors: pd.DataFrame,
    rankings: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build per-player impact crown flag, playoff context, and skill aspect standings."""
    aspects = _aspect_config(config)
    career = career_vectors.set_index("player_id")

    rank_frame = rankings.copy()
    if "rank_pca_whitened_l2" not in rank_frame.columns:
        rank_frame["rank_pca_whitened_l2"] = rank_frame["score_pca_whitened_l2"].rank(
            method="min", ascending=True
        ).astype(int)
    rank_lookup = rank_frame.set_index("player_id")

    rank_indexed = rank_frame.set_index("player_id")
    if "showman_z" in career.columns and "showman" not in aspects:
        aspects = {
            **aspects,
            "showman": {
                "label": "Showman",
                "features": ["showman_z"],
            },
        }

    aspect_scores: dict[str, pd.Series] = {}
    aspect_display: dict[str, pd.Series] = {}
    aspect_ranks: dict[str, pd.Series] = {}
    for key, spec in aspects.items():
        source = spec.get("source", "career")
        if source == "rankings":
            field = spec.get("field") or (spec.get("features") or [None])[0]
            if not field or field not in rank_indexed.columns:
                continue
            series = rank_indexed[field].reindex(career.index).fillna(0.0).astype(float)
        else:
            feature_cols = [col for col in spec.get("features", []) if col in career.columns]
            if not feature_cols:
                continue
            series = career[feature_cols].mean(axis=1)
        aspect_scores[key] = series
        aspect_display[key] = _cohort_score_0_100(series)
        aspect_ranks[key] = series.rank(method="min", ascending=False).astype(int)

    impact_series = aspect_scores.get("overall")
    if impact_series is not None:
        rank_impact_series = impact_series.rank(method="min", ascending=False).astype(int)
    else:
        rank_impact_series = None

    profiles: dict[str, dict[str, Any]] = {}
    for player_id, row in career.iterrows():
        display_name = str(row.get("display_name", player_id))
        if player_id in rank_lookup.index:
            rank_row = rank_lookup.loc[player_id]
            rank_pca = int(rank_row["rank_pca_whitened_l2"])
            score_pca = float(rank_row["score_pca_whitened_l2"])
            championships = int(rank_row.get("championships", 0) or 0)
            playoff_seasons = int(rank_row.get("playoff_seasons", 0) or 0)
            playoff_performance = float(rank_row.get("playoff_performance", 0.0) or 0.0)
            team_strength = float(rank_row.get("team_strength_index", 0.0) or 0.0)
            clutch_penalty = float(rank_row.get("clutch_penalty", 0.0) or 0.0)
            stat_outlier_z = float(rank_row.get("stat_outlier_z", 0.0) or 0.0)
            score_goat = float(rank_row.get("score_goat_index", score_pca) or score_pca)
            max_consecutive_championships = int(rank_row.get("max_consecutive_championships", 0) or 0)
            repeat_titles_score = float(rank_row.get("repeat_titles_score", 0.0) or 0.0)
        else:
            rank_pca = len(career)
            score_pca = float("nan")
            championships = playoff_seasons = 0
            playoff_performance = team_strength = clutch_penalty = stat_outlier_z = 0.0
            max_consecutive_championships = 0
            repeat_titles_score = 0.0
            score_goat = float("nan")

        aspect_rows: list[dict[str, Any]] = []
        for key, spec in aspects.items():
            if key not in aspect_scores:
                continue
            aspect_rows.append(
                {
                    "key": key,
                    "label": spec.get("label", key.replace("_", " ").title()),
                    "score": round(float(aspect_display[key].loc[player_id]), 1),
                    "rank": int(aspect_ranks[key].loc[player_id]),
                    "z_avg": round(float(aspect_scores[key].loc[player_id]), 2),
                }
            )

        impact_z = (
            round(float(impact_series.loc[player_id]), 2)
            if impact_series is not None
            else 0.0
        )
        rank_impact = (
            int(rank_impact_series.loc[player_id])
            if rank_impact_series is not None
            else len(career)
        )

        profiles[str(player_id)] = {
            "id": str(player_id),
            "name": display_name,
            "rank_pca": rank_pca,
            "score_pca": round(score_pca, 2),
            "impact_z": impact_z,
            "rank_impact": rank_impact,
            "score_goat_index": round(score_goat, 2),
            "is_impact_crown": rank_impact == 1,
            "championships": championships,
            "playoff_seasons": playoff_seasons,
            "playoff_performance": round(playoff_performance, 2),
            "stat_outlier_z": round(stat_outlier_z, 2),
            "team_strength_index": round(team_strength, 2),
            "clutch_penalty": round(clutch_penalty, 2),
            "max_consecutive_championships": max_consecutive_championships,
            "repeat_titles_score": round(repeat_titles_score, 2),
            "aspects": aspect_rows,
        }

    return profiles
