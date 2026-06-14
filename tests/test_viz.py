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
            ]
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        [
            {
                "player_id": "jordami01",
                "display_name": "Michael Jordan",
                "public_headline_score": 1.0,
            },
            {
                "player_id": "jamesle01",
                "display_name": "LeBron James",
                "public_headline_score": 2.0,
            },
        ]
    ).to_csv(goat_root / "GoatProject-modeling" / "output" / "goat_rankings.csv", index=False)

    pd.DataFrame(
        [
            {"player_id": "jordami01", "display_name": "Michael Jordan", "PC1": 0.5, "PC2": -0.2},
            {"player_id": "jamesle01", "display_name": "LeBron James", "PC1": -0.3, "PC2": 0.4},
        ]
    ).to_csv(goat_root / "GoatProject-modeling" / "output" / "pca_coordinates.csv", index=False)

    pd.DataFrame(
        [
            {"player_id": "jordami01", "jordami01": 1.0, "jamesle01": 0.8},
            {"player_id": "jamesle01", "jordami01": 0.8, "jamesle01": 1.0},
        ]
    ).to_csv(goat_root / "GoatProject-modeling" / "output" / "similarity_matrix.csv", index=False)

    (goat_root / "GoatProject-modeling" / "output" / "pca_explained_variance.json").write_text(
        json.dumps({"cumulative_2d": 0.61}),
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


def test_render_outputs(tmp_path: Path) -> None:
    _write_minimum_files(tmp_path, include_sensitivity=True)
    paths, artifacts = load_artifacts(str(tmp_path))
    outputs = render_all(paths, artifacts)

    assert outputs["index_html"].exists()
    assert outputs["goat_rankings"].exists()
    assert outputs["pca_scatter"].exists()
    assert outputs["similarity_heatmap"].exists()
