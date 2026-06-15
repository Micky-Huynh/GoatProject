from __future__ import annotations

import numpy as np
import pandas as pd

from goat_model.io import GoatContext, load_yaml


def _zscore(series: pd.Series) -> pd.Series:
    values = series.astype(float)
    std = values.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(0.0, index=series.index)
    return (values - values.mean()) / std


def load_playoff_context(ctx: GoatContext) -> pd.DataFrame:
    path = ctx.processed_dir / "playoff_context.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing playoff context: {path}. Run data pipeline first.")
    return pd.read_parquet(path)


def load_season_labels(ctx: GoatContext) -> pd.DataFrame:
    path = ctx.processed_dir / "season_labels.parquet"
    return pd.read_parquet(path)


def _impact_dominance(career_vectors: pd.DataFrame, player_ids: pd.Series, impact_features: list[str]) -> pd.Series:
    career = career_vectors.set_index("player_id")
    cols = [c for c in impact_features if c in career.columns]
    if not cols:
        return pd.Series(0.0, index=player_ids.index)
    impact = career.reindex(player_ids.tolist())[cols].mean(axis=1)
    impact.index = player_ids.index
    return _zscore(impact.fillna(0.0))


def apply_playoff_and_clutch_scores(
    ctx: GoatContext,
    rankings: pd.DataFrame,
    playoff_context: pd.DataFrame,
    season_labels: pd.DataFrame,
    career_vectors: pd.DataFrame,
) -> pd.DataFrame:
    """Merge championship context and clutch/consensus adjustment into rankings."""
    playoffs_cfg = load_yaml(ctx.root / "config" / "playoffs.yaml")
    clutch_cfg = playoffs_cfg.get("clutch_consensus", {})
    goat_cfg = playoffs_cfg.get("goat_index", {})

    merge_cols = [
        "player_id",
        "championships",
        "finals_losses",
        "finals_appearances",
        "playoff_seasons",
        "playoff_performance",
        "playoff_depth_total",
        "team_strength_index",
        "championship_credit",
        "finals_loss_debit",
        "championship_net",
        "max_consecutive_championships",
        "repeat_titles_score",
    ]
    merge_cols = [c for c in merge_cols if c in playoff_context.columns]
    merged = rankings.merge(playoff_context[merge_cols], on="player_id", how="left")

    for col in ["championships", "finals_losses", "finals_appearances", "playoff_seasons", "max_consecutive_championships"]:
        if col in merged.columns:
            merged[col] = merged[col].fillna(0).astype(int)
    for col in [
        "playoff_performance",
        "playoff_depth_total",
        "team_strength_index",
        "championship_credit",
        "finals_loss_debit",
        "championship_net",
        "max_consecutive_championships",
        "repeat_titles_score",
    ]:
        if col in merged.columns:
            merged[col] = merged[col].fillna(0.0).astype(float)

    impact_features = list(clutch_cfg.get("impact_features", ["bpm_z", "vorp_z", "per_z", "ws_z"]))
    stat_dominance = _impact_dominance(career_vectors, merged["player_id"], impact_features)
    merged["stat_outlier_z"] = stat_dominance

    labels = season_labels.copy()
    mvp = labels.groupby("player_id")["mvp_vote_share"].max().rename("mvp_peak")
    all_nba = labels.groupby("player_id")["all_nba_first"].sum().rename("all_nba_first_count")
    consensus_frame = pd.DataFrame({"player_id": merged["player_id"]}).merge(
        mvp.reset_index(), on="player_id", how="left"
    ).merge(all_nba.reset_index(), on="player_id", how="left")
    consensus_frame["mvp_peak"] = consensus_frame["mvp_peak"].fillna(0.0)
    consensus_frame["all_nba_first_count"] = consensus_frame["all_nba_first_count"].fillna(0.0)

    if "playoff_performance" not in merged.columns:
        merged["playoff_performance"] = 0.0
    playoff_success = (
        merged["playoff_performance"]
        * float(clutch_cfg.get("playoff_performance_weight", 1.25))
        + merged["championships"] * float(clutch_cfg.get("ring_weight", 2.0))
        + merged["finals_appearances"] * float(clutch_cfg.get("finals_appearance_weight", 0.75))
        - merged["finals_losses"] * float(clutch_cfg.get("finals_loss_weight", 0.35))
    )
    playoff_success_z = _zscore(playoff_success)
    consensus = (
        consensus_frame["mvp_peak"] * float(clutch_cfg.get("mvp_vote_weight", 3.0))
        + consensus_frame["all_nba_first_count"] * float(clutch_cfg.get("all_nba_first_weight", 0.8))
    )
    consensus_z = _zscore(consensus)

    damp = float(clutch_cfg.get("consensus_dampening", 0.45))
    penalty_w = float(clutch_cfg.get("penalty_weight", 0.55))
    clutch_gap = (stat_dominance - playoff_success_z - consensus_z * damp).clip(lower=0.0)
    merged["clutch_penalty"] = clutch_gap * penalty_w

    pca_w = float(goat_cfg.get("pca_weight", 1.0))
    champ_w = float(goat_cfg.get("championship_weight", 0.35))
    clutch_w = float(goat_cfg.get("clutch_penalty_weight", 0.45))
    merged["score_goat_index"] = (
        merged["score_pca_whitened_l2"] * pca_w
        - merged["championship_net"] * champ_w
        + merged["clutch_penalty"] * clutch_w
    )
    merged["score_goat_index"] = merged["score_goat_index"].fillna(merged["score_pca_whitened_l2"])
    merged["clutch_penalty"] = merged["clutch_penalty"].fillna(0.0)
    merged["stat_outlier_z"] = merged["stat_outlier_z"].fillna(0.0)
    merged["rank_goat_index"] = merged["score_goat_index"].rank(method="min", ascending=True).astype(int)
    return merged
