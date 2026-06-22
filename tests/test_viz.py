from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from goat_viz.io import load_artifacts
from goat_viz.render import render_all


def _write_minimum_files(goat_root: Path, include_sensitivity: bool = True) -> None:
    (goat_root / "config").mkdir(parents=True, exist_ok=True)
    (goat_root / "GoatProject-modeling" / "output").mkdir(parents=True, exist_ok=True)
    (goat_root / "GoatProject-viz" / "output" / "posts").mkdir(parents=True, exist_ok=True)

    (goat_root / "config" / "viz.yaml").write_text(
        "\n".join(
            [
                "theme:",
                "  background: '#0d1117'",
                "  text: '#e6edf3'",
                "  accent: '#f97316'",
                "export:",
                "  dpi: 300",
                "  post_formats:",
                "    - name: square",
                "      width: 1080",
                "      height: 1080",
                "captions:",
                "  exploratory_disclaimer: 'Layout view only.'",
                "  era_adjustment: 'Era-adjusted z-scores.'",
                "embed_3d:",
                "  enabled: true",
            ]
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        [
            {
                "player_id": "jordami01",
                "display_name": "Michael Jordan",
                "score_pca_whitened_l2": 1.0,
                "score_goat_index": 1.0,
                "rank_pca_whitened_l2": 1,
                "championships": 6,
                "playoff_seasons": 15,
                "playoff_performance": 2.4,
                "stat_outlier_z": 1.2,
                "team_strength_index": 0.5,
                "clutch_penalty": 0.0,
                "score_l2": 1.0,
                "score_mahalanobis": 1.2,
                "rank_l2": 1,
                "rank_mahalanobis": 2,
            },
            {
                "player_id": "jamesle01",
                "display_name": "LeBron James",
                "score_pca_whitened_l2": 2.0,
                "score_goat_index": 2.5,
                "rank_pca_whitened_l2": 2,
                "championships": 0,
                "playoff_seasons": 0,
                "playoff_performance": 0.0,
                "stat_outlier_z": -0.5,
                "team_strength_index": 0.0,
                "clutch_penalty": 0.3,
                "score_l2": 2.0,
                "score_mahalanobis": 1.8,
                "rank_l2": 2,
                "rank_mahalanobis": 1,
            },
        ]
    ).to_csv(goat_root / "GoatProject-modeling" / "output" / "goat_rankings.csv", index=False)

    pd.DataFrame(
        [
            {"player_id": "jordami01", "display_name": "Michael Jordan", "PC1": 0.5, "PC2": -0.2, "PC3": 0.1},
            {"player_id": "jamesle01", "display_name": "LeBron James", "PC1": -0.3, "PC2": 0.4, "PC3": -0.2},
        ]
    ).to_csv(goat_root / "GoatProject-modeling" / "output" / "pca_coordinates.csv", index=False)

    pd.DataFrame(
        [
            {"player_id": "jordami01", "jordami01": 1.0, "jamesle01": 0.8},
            {"player_id": "jamesle01", "jordami01": 0.8, "jamesle01": 1.0},
        ]
    ).to_csv(goat_root / "GoatProject-modeling" / "output" / "similarity_matrix.csv", index=False)

    (goat_root / "GoatProject-modeling" / "output" / "pca_explained_variance.json").write_text(
        json.dumps(
            {
                "cumulative_2d": 0.61,
                "components": [
                    {"component": "PC1", "explained_variance_ratio": 0.45},
                    {"component": "PC2", "explained_variance_ratio": 0.16},
                    {"component": "PC3", "explained_variance_ratio": 0.12},
                ],
            }
        ),
        encoding="utf-8",
    )

    (goat_root / "GoatProject-modeling" / "output" / "validation_report.json").write_text(
        json.dumps({
            "validator": "test",
            "non_gating": True,
            "primary_metrics": {"test_sample_count": 10, "mvp_vote_share": {"value": 0.5}},
        }),
        encoding="utf-8",
    )

    if include_sensitivity:
        (goat_root / "GoatProject-modeling" / "output" / "sensitivity_report.json").write_text(
            json.dumps({"publish_gate_pass": True}),
            encoding="utf-8",
        )


def test_requires_sensitivity_report(tmp_path: Path) -> None:
    _write_minimum_files(tmp_path, include_sensitivity=False)
    with pytest.raises(FileNotFoundError):
        load_artifacts(str(tmp_path))


def test_player_profiles_use_career_vectors(tmp_path: Path) -> None:
    _write_minimum_files(tmp_path, include_sensitivity=True)
    processed = tmp_path / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "player_id": "jordami01",
                "display_name": "Michael Jordan",
                "bpm_z": 2.0,
                "vorp_z": 2.1,
                "per_z": 1.8,
                "ws_z": 1.9,
                "ts_percent_z": 1.0,
                "usg_percent_z": 1.2,
                "ast_percent_z": 0.5,
                "stl_percent_z": 1.4,
                "blk_percent_z": 0.8,
                "tov_percent_z": 0.6,
                "x3p_ar_z": 0.2,
            },
            {
                "player_id": "jamesle01",
                "display_name": "LeBron James",
                "bpm_z": 1.5,
                "vorp_z": 1.6,
                "per_z": 1.4,
                "ws_z": 1.3,
                "ts_percent_z": 0.8,
                "usg_percent_z": 1.0,
                "ast_percent_z": 1.2,
                "stl_percent_z": 0.9,
                "blk_percent_z": 0.7,
                "tov_percent_z": 0.4,
                "x3p_ar_z": 0.1,
            },
        ]
    ).to_parquet(processed / "career_vectors.parquet", index=False)

    from goat_viz.profiles import compute_player_profiles

    _, artifacts = load_artifacts(str(tmp_path))
    profiles = compute_player_profiles(artifacts.career_vectors, artifacts.rankings, artifacts.config)
    assert profiles["jordami01"]["is_impact_crown"] is True
    assert any(row["key"] == "defense" for row in profiles["jordami01"]["aspects"])


def test_render_outputs(tmp_path: Path) -> None:
    _write_minimum_files(tmp_path, include_sensitivity=True)
    paths, artifacts = load_artifacts(str(tmp_path))
    outputs = render_all(paths, artifacts)

    assert outputs["index_html"].exists()
    assert outputs["home_html"].exists()
    assert outputs["how_it_works"].exists()
    assert outputs["goat_rankings"].exists()
    assert outputs["pca_scatter"].exists()
    assert outputs["similarity_heatmap"].exists()
    assert outputs["embed_3d"].exists()
    html = outputs["embed_3d"].read_text(encoding="utf-8")
    assert "three.module.js" in html
    assert "data:image/jpeg;base64," in html
    assert "profile-panel" in html
    assert "is_impact_crown" in html
    assert "cohortImpactLeader" in html
    assert 'id="alchemy-toggle"' not in html
    assert outputs["alchemy"].exists()
    assert outputs["pca_map"].exists()
    pca_map_html = outputs["pca_map"].read_text(encoding="utf-8")
    assert "pca-tooltip" in pca_map_html
    assert "legend-toggle" in pca_map_html
    assert "show-all-players" in pca_map_html
    alchemy_html = outputs["alchemy"].read_text(encoding="utf-8")
    shell_html = outputs["index_html"].read_text(encoding="utf-8")
    index_html = outputs["home_html"].read_text(encoding="utf-8")
    assert "alpha-slider" in alchemy_html
    assert "combinePlayers" in alchemy_html
    assert "focusBlendTrio" in alchemy_html
    assert "panel-explore" in alchemy_html
    assert "toggleAllPlayersPcaView" in alchemy_html
    assert "resize-left" in alchemy_html
    assert "math-modal" in alchemy_html
    assert "math-explain-button" in alchemy_html
    assert "renderMathWorkedExample" in alchemy_html
    assert "show-all-players" in alchemy_html
    assert "goatNavigate" in alchemy_html
    for page_html in (html, alchemy_html):
        mod_idx = page_html.find('<script type="module">')
        import_idx = page_html.find("import * as THREE", mod_idx)
        nav_idx = page_html.find("function goatNavigate")
        assert nav_idx != -1 and mod_idx != -1 and import_idx != -1
        assert nav_idx < mod_idx < import_idx
    assert "site-nav" in shell_html
    assert "site-frame" in shell_html
    assert "home.html" in shell_html
    assert "how_it_works.html" in shell_html
    assert "How It Works" in shell_html
    assert "validation-json" in index_html
    assert "validation-english" in index_html
    assert "how_it_works.html" not in index_html
    assert "GOAT ranking" in index_html
    assert "goat_rankings.png</figcaption>" not in index_html
    assert ".tab-panel.active" in index_html
    assert "display: none" in index_html
    assert "preview-description" in index_html
    assert "preview-chart" in index_html
    how_html = outputs["how_it_works"].read_text(encoding="utf-8")
    assert "score_goat_index" in how_html
    assert "What it is and what it does" in how_html

