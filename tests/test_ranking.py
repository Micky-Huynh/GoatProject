from __future__ import annotations

from pathlib import Path

import pandas.testing as pdt

from goat_model.run_ranking import run


def _default_goat_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_rankings_have_21_players_and_required_columns() -> None:
    rankings, _ = run(_default_goat_root())
    assert len(rankings) == 21
    required = {
        "player_id",
        "display_name",
        "score_l2",
        "score_mahalanobis",
        "score_pca_whitened_l2",
        "rank_l2",
        "rank_mahalanobis",
        "rank_pca_whitened_l2",
        "public_headline_score",
        "rank_method_primary",
    }
    assert required.issubset(rankings.columns)


def test_ranking_rerun_is_deterministic() -> None:
    rankings_a, report_a = run(_default_goat_root())
    rankings_b, report_b = run(_default_goat_root())
    pdt.assert_frame_equal(
        rankings_a.sort_values("player_id").reset_index(drop=True),
        rankings_b.sort_values("player_id").reset_index(drop=True),
        check_exact=False,
        rtol=0,
        atol=1e-12,
    )
    assert report_a["publish_gate_pass"] == report_b["publish_gate_pass"]
    assert report_a["publish_gate"] == report_b["publish_gate"]


def test_sensitivity_report_has_required_keys() -> None:
    _, report = run(_default_goat_root())
    assert "publish_gate_pass" in report
    assert "publish_gate" in report
    assert {"spearman_l2_vs_mahalanobis", "top5_overlap", "thresholds"}.issubset(
        report["publish_gate"].keys()
    )
    assert "runs" in report
    assert {
        "S1_min_minutes",
        "S2_weighted_career",
        "S3_league_zscore",
        "S4_l2_vs_mahalanobis",
        "S5_collinearity_drop",
    }.issubset(report["runs"].keys())
