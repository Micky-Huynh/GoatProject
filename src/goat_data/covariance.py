from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from goat_data.aggregate import aggregate_career_vectors
from goat_data.config import RIDGE_EPSILON, z_column


@dataclass
class CovarianceResult:
    matrix: np.ndarray
    feature_names: list[str]
    player_count: int
    condition_number: float
    max_correlation: float
    path: str


def _max_abs_correlation(matrix: np.ndarray) -> float:
    if matrix.shape[0] < 2:
        return 0.0
    std = np.sqrt(np.diag(matrix))
    denom = np.outer(std, std)
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = matrix / denom
    corr = np.nan_to_num(corr, nan=0.0)
    np.fill_diagonal(corr, 0.0)
    return float(np.abs(corr).max())


def build_league_covariance(
    season_vectors: pd.DataFrame,
    feature_names: list[str],
    display_names: dict[str, str],
    output_path,
) -> CovarianceResult:
    careers = aggregate_career_vectors(season_vectors, feature_names, display_names)
    z_cols = [z_column(name) for name in feature_names]
    values = careers[z_cols].to_numpy(dtype=float)
    values = np.nan_to_num(values, nan=0.0)
    sample = np.cov(values, rowvar=False)
    regularized = sample + RIDGE_EPSILON * np.eye(sample.shape[0])
    cond = float(np.linalg.cond(regularized))
    max_corr = _max_abs_correlation(sample)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(output_path, regularized)

    return CovarianceResult(
        matrix=regularized,
        feature_names=feature_names,
        player_count=int(len(careers)),
        condition_number=cond,
        max_correlation=max_corr,
        path=str(output_path),
    )
