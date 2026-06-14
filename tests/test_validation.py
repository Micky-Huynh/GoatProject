from __future__ import annotations

from pathlib import Path

from goat_model.validate import run_validation


def _default_goat_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_validation_report_primary_metrics_shape() -> None:
    report = run_validation(_default_goat_root(), include_shap=False)

    assert report["non_gating"] is True
    assert report["split"]["train_seasons_end"] == 2014
    assert report["split"]["test_seasons_start"] == 2015
    primary = report["primary_metrics"]
    assert primary["mvp_vote_share"]["metric"] == "spearman"
    assert -1.0 <= primary["mvp_vote_share"]["value"] <= 1.0
    assert primary["all_nba_first"]["metric"] in {"roc_auc", "accuracy"}
    assert 0.0 <= primary["all_nba_first"]["value"] <= 1.0


def test_validation_does_not_modify_goat_rankings() -> None:
    goat_root = _default_goat_root()
    rankings_path = goat_root / "GoatProject-modeling" / "output" / "goat_rankings.csv"
    before = rankings_path.read_bytes()

    run_validation(goat_root, include_shap=False)

    after = rankings_path.read_bytes()
    assert before == after
