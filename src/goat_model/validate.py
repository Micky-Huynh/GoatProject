from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from goat_model.io import (
    ensure_output_path,
    load_context,
    load_manifest,
    load_season_vectors,
    write_json,
    z_columns_from_manifest,
)


def _resolve_processed_artifact(root: Path, configured_path: str) -> Path:
    if configured_path.startswith("processed/"):
        return root / "GoatProject-data" / configured_path
    return root / configured_path


def _require_xgboost() -> tuple[Any, Any]:
    try:
        from xgboost import XGBClassifier, XGBRegressor
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError("xgboost is required for validation. Install it via pyproject dependencies.") from exc
    return XGBClassifier, XGBRegressor


def _safe_spearman(x: pd.Series, y: pd.Series) -> float:
    rho = x.corr(y, method="spearman")
    if pd.isna(rho):
        return 0.0
    return float(rho)


def _top_mean_abs_shap(shap_values: np.ndarray, feature_names: list[str], top_k: int = 10) -> list[dict[str, float]]:
    magnitudes = np.mean(np.abs(shap_values), axis=0)
    ranked_idx = np.argsort(magnitudes)[::-1][:top_k]
    return [
        {"feature": feature_names[idx], "mean_abs_shap": float(magnitudes[idx])}
        for idx in ranked_idx
    ]


def run_validation(goat_root: Path | None = None, include_shap: bool = False) -> dict[str, Any]:
    XGBClassifier, XGBRegressor = _require_xgboost()
    ctx = load_context(goat_root)
    manifest = load_manifest(ctx)
    z_cols = z_columns_from_manifest(manifest)
    season_vectors = load_season_vectors(ctx, manifest)

    labels_cfg_path = ctx.paths_cfg["artifacts"]["season_labels"]
    labels_path = _resolve_processed_artifact(ctx.root, labels_cfg_path)
    labels = pd.read_parquet(labels_path)

    frame = season_vectors[["player_id", "season", *z_cols]].merge(
        labels[["player_id", "season", "mvp_vote_share", "all_nba_first", "all_nba_any"]],
        on=["player_id", "season"],
        how="inner",
    )
    frame["season"] = frame["season"].astype(int)

    split_cfg = ctx.pipeline_cfg["validator"]
    train_end = int(split_cfg["train_seasons_end"])
    test_start = int(split_cfg["test_seasons_start"])
    train = frame[frame["season"] <= train_end].copy()
    test = frame[frame["season"] >= test_start].copy()

    if train.empty or test.empty:
        raise ValueError("Validator split produced an empty train/test set.")

    X_train = np.nan_to_num(train[z_cols].to_numpy(dtype=float), nan=0.0)
    X_test = np.nan_to_num(test[z_cols].to_numpy(dtype=float), nan=0.0)
    y_train_mvp = train["mvp_vote_share"].to_numpy(dtype=float)
    y_test_mvp = test["mvp_vote_share"].to_numpy(dtype=float)
    y_train_all_nba = train["all_nba_first"].to_numpy(dtype=int)
    y_test_all_nba = test["all_nba_first"].to_numpy(dtype=int)

    reg_model = XGBRegressor(
        objective="reg:squarederror",
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        n_jobs=1,
    )
    clf_model = XGBClassifier(
        objective="binary:logistic",
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="logloss",
        random_state=42,
        n_jobs=1,
    )
    reg_model.fit(X_train, y_train_mvp)
    clf_model.fit(X_train, y_train_all_nba)

    mvp_preds = reg_model.predict(X_test)
    all_nba_proba = clf_model.predict_proba(X_test)[:, 1]

    mvp_spearman = _safe_spearman(pd.Series(y_test_mvp), pd.Series(mvp_preds))

    try:
        from sklearn.metrics import roc_auc_score

        all_nba_metric_name = "roc_auc"
        all_nba_metric_value = float(roc_auc_score(y_test_all_nba, all_nba_proba))
    except Exception:  # pragma: no cover - fallback path
        all_nba_metric_name = "accuracy"
        all_nba_metric_value = float((y_test_all_nba == (all_nba_proba >= 0.5).astype(int)).mean())

    rankings_path = ctx.output_dir / "goat_rankings.csv"
    rankings = pd.read_csv(rankings_path)
    career_preds = (
        test.assign(mvp_pred=mvp_preds)
        .groupby("player_id", as_index=False)["mvp_pred"]
        .mean()
        .rename(columns={"mvp_pred": "mean_test_mvp_prediction"})
    )
    career_eval = rankings[["player_id", "score_goat_index"]].merge(career_preds, on="player_id", how="inner")
    career_spearman = _safe_spearman(
        career_eval["score_goat_index"], career_eval["mean_test_mvp_prediction"]
    )

    report: dict[str, Any] = {
        "validator": "xgboost_award_alignment_v1",
        "non_gating": True,
        "split": {
            "train_seasons_end": train_end,
            "test_seasons_start": test_start,
        },
        "primary_metrics": {
            "test_sample_count": int(len(test)),
            "mvp_vote_share": {
                "metric": "spearman",
                "value": mvp_spearman,
            },
            "all_nba_first": {
                "metric": all_nba_metric_name,
                "value": all_nba_metric_value,
            },
        },
        "secondary_metrics": {
            "career_goat_index_vs_mean_test_prediction_spearman": career_spearman,
            "player_count": int(career_eval["player_id"].nunique()),
        },
        "inputs": {
            "season_vectors": str(_resolve_processed_artifact(ctx.root, manifest["artifacts"]["season_vectors"])),
            "season_labels": str(labels_path),
            "goat_rankings": str(rankings_path),
        },
    }

    if include_shap:
        shap_payload: dict[str, Any] = {"enabled": True}
        try:
            import shap

            sample_size = min(len(X_test), 200)
            sample_idx = np.arange(sample_size)
            X_sample = X_test[sample_idx]

            reg_explainer = shap.TreeExplainer(reg_model)
            reg_values = np.asarray(reg_explainer.shap_values(X_sample))
            clf_explainer = shap.TreeExplainer(clf_model)
            clf_raw_values = clf_explainer.shap_values(X_sample)
            if isinstance(clf_raw_values, list):
                clf_values = np.asarray(clf_raw_values[-1])
            else:
                clf_values = np.asarray(clf_raw_values)

            shap_payload.update(
                {
                    "available": True,
                    "sample_size": int(sample_size),
                    "mvp_vote_share_top_features": _top_mean_abs_shap(reg_values, z_cols),
                    "all_nba_first_top_features": _top_mean_abs_shap(clf_values, z_cols),
                }
            )
        except ImportError:
            shap_payload.update(
                {
                    "available": False,
                    "reason": "shap is not installed. Install optional dependency to enable SHAP diagnostics.",
                }
            )
        report["shap"] = shap_payload

    output_path = ensure_output_path(ctx, "validation_report.json")
    write_json(output_path, report)
    return report
