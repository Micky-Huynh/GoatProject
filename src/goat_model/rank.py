from __future__ import annotations

import numpy as np
import pandas as pd


def compute_publish_gate(
    rankings: pd.DataFrame,
    min_spearman: float,
    min_top5_overlap: int,
) -> dict[str, float | int | bool]:
    rho = pd.Series(rankings["rank_l2"]).corr(pd.Series(rankings["rank_mahalanobis"]), method="spearman")
    top_l2 = set(rankings.nsmallest(5, "rank_l2")["player_id"])
    top_mahal = set(rankings.nsmallest(5, "rank_mahalanobis")["player_id"])
    overlap = int(len(top_l2 & top_mahal))
    return {
        "spearman_l2_vs_mahalanobis": float(rho),
        "top5_overlap": overlap,
        "pass": bool((rho >= min_spearman) and (overlap >= min_top5_overlap)),
    }


def _rank_ascending(scores: pd.Series) -> pd.Series:
    return scores.rank(method="min", ascending=True).astype(int)


def _mahalanobis_scores(values: np.ndarray, covariance: np.ndarray, epsilon: float) -> np.ndarray:
    sigma = covariance + (epsilon * np.eye(covariance.shape[0]))
    inv_sigma = np.linalg.inv(sigma)
    quad = np.einsum("ij,jk,ik->i", values, inv_sigma, values)
    return np.sqrt(np.clip(quad, a_min=0.0, a_max=None))


def _pca_whitened_l2_scores(
    target_values: np.ndarray,
    full_league_values: np.ndarray,
    cumulative_variance_threshold: float,
) -> np.ndarray:
    full_league_values = np.nan_to_num(full_league_values, nan=0.0)
    target_values = np.nan_to_num(target_values, nan=0.0)
    mean = full_league_values.mean(axis=0, keepdims=True)
    centered = full_league_values - mean
    _, singular_values, vt = np.linalg.svd(centered, full_matrices=False)
    explained_variance = (singular_values ** 2) / max(centered.shape[0] - 1, 1)
    total_variance = explained_variance.sum()
    explained_ratio = explained_variance / total_variance if total_variance > 0 else explained_variance
    cumulative = np.cumsum(explained_ratio)
    k = int(np.searchsorted(cumulative, cumulative_variance_threshold) + 1)
    k = min(k, full_league_values.shape[1])
    components = vt[:k]
    target_centered = target_values - mean
    projected = target_centered @ components.T
    whiten_denominator = np.sqrt(np.clip(explained_variance[:k], a_min=1e-12, a_max=None))
    whitened = projected / whiten_denominator
    return np.linalg.norm(whitened, axis=1)


def _alchemy_display_columns(career_vectors: pd.DataFrame) -> list[str]:
    alchemy_cols = ["showman_z", "showman_partial"]
    zone_share_cols = [col for col in career_vectors.columns if col.startswith("zone_") and col.endswith("_share")]
    return [col for col in alchemy_cols + sorted(zone_share_cols) if col in career_vectors.columns]


def build_rankings(
    career_vectors: pd.DataFrame,
    z_cols: list[str],
    covariance: np.ndarray,
    full_league_careers: pd.DataFrame,
    scoring_cfg: dict,
) -> pd.DataFrame:
    target_values = np.nan_to_num(career_vectors[z_cols].to_numpy(dtype=float), nan=0.0)
    full_values = np.nan_to_num(full_league_careers[z_cols].to_numpy(dtype=float), nan=0.0)
    l2_values = np.linalg.norm(target_values, axis=1)
    mahal_values = _mahalanobis_scores(
        target_values,
        covariance,
        epsilon=float(scoring_cfg["scores"]["mahalanobis"]["regularization_epsilon"]),
    )
    pca_values = _pca_whitened_l2_scores(
        target_values,
        full_values,
        cumulative_variance_threshold=float(
            scoring_cfg["scores"]["pca_whitened_l2"]["cumulative_variance_threshold"]
        ),
    )

    rankings = career_vectors[["player_id", "display_name"]].copy()
    rankings["score_l2"] = l2_values
    rankings["score_mahalanobis"] = mahal_values
    rankings["score_pca_whitened_l2"] = pca_values
    rankings["rank_l2"] = _rank_ascending(rankings["score_l2"])
    rankings["rank_mahalanobis"] = _rank_ascending(rankings["score_mahalanobis"])
    rankings["rank_pca_whitened_l2"] = _rank_ascending(rankings["score_pca_whitened_l2"])

    display_cols = _alchemy_display_columns(career_vectors)
    if display_cols:
        meta = career_vectors[["player_id", *display_cols]].drop_duplicates("player_id")
        rankings = rankings.merge(meta, on="player_id", how="left")

    rankings = rankings.sort_values("rank_pca_whitened_l2", kind="mergesort").reset_index(drop=True)
    return rankings
