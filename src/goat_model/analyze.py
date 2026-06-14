from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from goat_model.io import GoatContext, aggregate_career_vectors, build_full_league_season_vectors


@dataclass(frozen=True)
class PcaResult:
    components: np.ndarray
    explained_variance_ratio: np.ndarray
    cumulative_explained_variance: np.ndarray
    n_components: int
    mean: np.ndarray


def _safe_l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return matrix / norms


def cosine_similarity_matrix(career_vectors: pd.DataFrame, z_cols: list[str]) -> pd.DataFrame:
    values = np.nan_to_num(
        career_vectors[z_cols].to_numpy(dtype=float),
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )
    normalized = _safe_l2_normalize(values)
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        similarities = normalized @ normalized.T
    similarities = np.nan_to_num(similarities, nan=0.0, posinf=0.0, neginf=0.0)
    similarities = np.clip(similarities, -1.0, 1.0)
    player_ids = career_vectors["player_id"].tolist()
    return pd.DataFrame(similarities, index=player_ids, columns=player_ids)


def nearest_neighbor_uniqueness(career_vectors: pd.DataFrame, z_cols: list[str]) -> pd.DataFrame:
    sim = cosine_similarity_matrix(career_vectors, z_cols)
    sim_values = sim.to_numpy(copy=True)
    np.fill_diagonal(sim_values, -np.inf)
    nearest_idx = sim_values.argmax(axis=1)
    nearest_similarity = sim_values[np.arange(len(sim_values)), nearest_idx]
    nearest_distance = 1.0 - nearest_similarity
    nearest_player = [sim.columns[idx] for idx in nearest_idx]

    return pd.DataFrame(
        {
            "player_id": career_vectors["player_id"].to_numpy(),
            "display_name": career_vectors["display_name"].to_numpy(),
            "nearest_neighbor_player_id": nearest_player,
            "nearest_neighbor_similarity": nearest_similarity,
            "uniqueness": nearest_distance,
        }
    ).sort_values("uniqueness", ascending=False, kind="mergesort")


def fit_pca_for_threshold(
    full_league_careers: pd.DataFrame,
    z_cols: list[str],
    cumulative_variance_threshold: float,
) -> PcaResult:
    values = np.nan_to_num(full_league_careers[z_cols].to_numpy(dtype=float), nan=0.0)
    mean = values.mean(axis=0, keepdims=True)
    centered = values - mean
    _, singular_values, vt = np.linalg.svd(centered, full_matrices=False)

    explained_variance = (singular_values**2) / max(centered.shape[0] - 1, 1)
    total = explained_variance.sum()
    explained_ratio = explained_variance / total if total > 0 else explained_variance
    cumulative = np.cumsum(explained_ratio)

    n_components = int(np.searchsorted(cumulative, cumulative_variance_threshold) + 1)
    n_components = max(2, min(n_components, len(explained_ratio)))
    return PcaResult(
        components=vt[:n_components],
        explained_variance_ratio=explained_ratio[:n_components],
        cumulative_explained_variance=cumulative[:n_components],
        n_components=n_components,
        mean=mean,
    )


def project_to_pca(career_vectors: pd.DataFrame, z_cols: list[str], pca: PcaResult) -> pd.DataFrame:
    values = np.nan_to_num(career_vectors[z_cols].to_numpy(dtype=float), nan=0.0)
    centered = values - pca.mean
    coords = centered @ pca.components.T
    output = career_vectors[["player_id", "display_name"]].copy()
    for idx in range(pca.n_components):
        output[f"PC{idx + 1}"] = coords[:, idx]
    return output


def pca_loadings(z_cols: list[str], pca: PcaResult) -> pd.DataFrame:
    data: dict[str, Any] = {"feature": z_cols}
    for idx in range(pca.n_components):
        data[f"PC{idx + 1}"] = pca.components[idx]
    return pd.DataFrame(data)


def pca_explained_variance_payload(pca: PcaResult) -> dict[str, Any]:
    components = []
    for idx in range(pca.n_components):
        components.append(
            {
                "component": f"PC{idx + 1}",
                "explained_variance_ratio": float(pca.explained_variance_ratio[idx]),
                "cumulative_explained_variance": float(pca.cumulative_explained_variance[idx]),
            }
        )
    return {
        "n_components": pca.n_components,
        "components": components,
        "cumulative_variance": float(pca.cumulative_explained_variance[-1]) if components else 0.0,
        "pc1_variance_ratio": float(pca.explained_variance_ratio[0]) if pca.n_components >= 1 else 0.0,
        "pc2_variance_ratio": float(pca.explained_variance_ratio[1]) if pca.n_components >= 2 else 0.0,
        "cumulative_2d": float(pca.cumulative_explained_variance[1]) if pca.n_components >= 2 else 0.0,
    }


def build_full_league_careers_for_pca(ctx: GoatContext, z_cols: list[str]) -> pd.DataFrame:
    full_seasons, _ = build_full_league_season_vectors(ctx, group_mode="season_pos_fallback")
    return aggregate_career_vectors(full_seasons, z_cols=z_cols, weight_by_minutes=False)
