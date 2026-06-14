from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from goat_model.io import GoatContext, aggregate_career_vectors, build_full_league_season_vectors


@dataclass(frozen=True)
class RankComparison:
    spearman: float
    top5_overlap: int


def _rank_ids_by_l2(frame: pd.DataFrame, z_cols: list[str]) -> list[str]:
    scored = frame[["player_id", *z_cols]].copy()
    scored["score_l2"] = np.linalg.norm(np.nan_to_num(scored[z_cols].to_numpy(dtype=float), nan=0.0), axis=1)
    return scored.sort_values("score_l2", kind="mergesort")["player_id"].tolist()


def _comparison_vs_baseline(baseline_ids: list[str], candidate_ids: list[str]) -> RankComparison:
    base_rank = {pid: idx + 1 for idx, pid in enumerate(baseline_ids)}
    cand_rank = {pid: idx + 1 for idx, pid in enumerate(candidate_ids)}
    shared = [pid for pid in baseline_ids if pid in cand_rank]
    rho = pd.Series([base_rank[pid] for pid in shared]).corr(
        pd.Series([cand_rank[pid] for pid in shared]),
        method="spearman",
    )
    top5_overlap = len(set(baseline_ids[:5]) & set(candidate_ids[:5]))
    return RankComparison(spearman=float(rho), top5_overlap=int(top5_overlap))


def run_sensitivity(
    ctx: GoatContext,
    baseline_rankings: pd.DataFrame,
    baseline_career_vectors: pd.DataFrame,
    season_vectors_allowlist: pd.DataFrame,
    z_cols: list[str],
) -> dict:
    baseline_ids = baseline_rankings.sort_values("rank_l2", kind="mergesort")["player_id"].tolist()
    gate_cfg = ctx.scoring_cfg["publish_gate"]
    s5_drop = list(ctx.scoring_cfg["s5_collinearity_block"])

    # S1: alternate minimum-minute threshold.
    alt_min_minutes = int(ctx.pipeline_cfg.get("sensitivity", {}).get("s1_alt_min_minutes", 400))
    s1_seasons = season_vectors_allowlist[season_vectors_allowlist["mp"] >= alt_min_minutes].copy()
    s1_career = aggregate_career_vectors(s1_seasons, z_cols=z_cols, weight_by_minutes=False)
    s1_ids = _rank_ids_by_l2(s1_career, z_cols)
    s1_cmp = _comparison_vs_baseline(baseline_ids, s1_ids)

    # S2: minutes-weighted career mean.
    s2_career = aggregate_career_vectors(season_vectors_allowlist, z_cols=z_cols, weight_by_minutes=True)
    s2_ids = _rank_ids_by_l2(s2_career, z_cols)
    s2_cmp = _comparison_vs_baseline(baseline_ids, s2_ids)

    # S3: league-only z-score (season groups, no position stratification).
    full_seasons_s3, _ = build_full_league_season_vectors(ctx, group_mode="season_only")
    s3_allowlist = full_seasons_s3[full_seasons_s3["player_id"].isin(set(baseline_ids))].copy()
    s3_career = aggregate_career_vectors(s3_allowlist, z_cols=z_cols, weight_by_minutes=False)
    s3_ids = _rank_ids_by_l2(s3_career, z_cols)
    s3_cmp = _comparison_vs_baseline(baseline_ids, s3_ids)

    # S4: publish-gate metrics between baseline L2 and Mahalanobis rankings.
    s4_spearman = pd.Series(baseline_rankings["rank_l2"]).corr(
        pd.Series(baseline_rankings["rank_mahalanobis"]), method="spearman"
    )
    s4_overlap = len(
        set(baseline_rankings.nsmallest(5, "rank_l2")["player_id"])
        & set(baseline_rankings.nsmallest(5, "rank_mahalanobis")["player_id"])
    )

    # S5: drop collinearity block features and compare to baseline L2.
    dropped_cols = {f"{name}_z" for name in s5_drop}
    s5_cols = [col for col in z_cols if col not in dropped_cols]
    s5_ids = _rank_ids_by_l2(baseline_career_vectors[["player_id", *s5_cols]], s5_cols)
    s5_cmp = _comparison_vs_baseline(baseline_ids, s5_ids)

    min_spearman = float(gate_cfg["min_spearman_l2_vs_mahalanobis"])
    min_top5_overlap = int(gate_cfg["min_top5_overlap_l2_vs_mahalanobis"])
    publish_gate_pass = bool((s4_spearman >= min_spearman) and (s4_overlap >= min_top5_overlap))

    return {
        "baseline": ctx.scoring_cfg["scores"]["l2"]["id"],
        "publish_gate_pass": publish_gate_pass,
        "publish_gate": {
            "spearman_l2_vs_mahalanobis": float(s4_spearman),
            "top5_overlap": int(s4_overlap),
            "thresholds": {
                "min_spearman": min_spearman,
                "min_top5_overlap": min_top5_overlap,
            },
        },
        "runs": {
            "S1_min_minutes": {
                "alt_min_minutes": alt_min_minutes,
                "spearman_vs_baseline": s1_cmp.spearman,
                "top5_overlap_vs_baseline": s1_cmp.top5_overlap,
                "soft_warning": bool(
                    s1_cmp.spearman < float(gate_cfg["soft_warnings"]["min_s1_spearman_vs_baseline"])
                ),
            },
            "S2_weighted_career": {
                "spearman_vs_baseline": s2_cmp.spearman,
                "top5_overlap_vs_baseline": s2_cmp.top5_overlap,
            },
            "S3_league_zscore": {
                "spearman_vs_baseline": s3_cmp.spearman,
                "top5_overlap_vs_baseline": s3_cmp.top5_overlap,
                "soft_warning": bool(
                    s3_cmp.top5_overlap < int(gate_cfg["soft_warnings"]["min_s3_top5_overlap"])
                ),
            },
            "S4_l2_vs_mahalanobis": {
                "spearman_l2_vs_mahalanobis": float(s4_spearman),
                "top5_overlap_l2_vs_mahalanobis": int(s4_overlap),
            },
            "S5_collinearity_drop": {
                "dropped_features": s5_drop,
                "kept_feature_count": len(s5_cols),
                "spearman_vs_baseline": s5_cmp.spearman,
                "top5_overlap_vs_baseline": s5_cmp.top5_overlap,
            },
        },
    }
