from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .io import VizArtifacts, VizPaths


def _post_size_inches(config: dict[str, Any], dpi: int) -> tuple[float, float]:
    formats = config.get("export", {}).get("post_formats", [])
    default_format = formats[0] if formats else {"width": 1080, "height": 1080}
    width_px = int(default_format.get("width", 1080))
    height_px = int(default_format.get("height", 1080))
    return width_px / dpi, height_px / dpi


def _theme(config: dict[str, Any]) -> dict[str, str]:
    theme = config.get("theme", {})
    return {
        "background": theme.get("background", "#0d1117"),
        "text": theme.get("text", "#e6edf3"),
        "accent": theme.get("accent", "#f97316"),
    }


def _caption_lines(config: dict[str, Any]) -> tuple[str, str]:
    captions = config.get("captions", {})
    return (
        captions.get("exploratory_disclaimer", ""),
        captions.get("era_adjustment", ""),
    )


def _variance_summary(pca_explained_variance: dict[str, Any]) -> str:
    cumulative_2d = pca_explained_variance.get("cumulative_2d")
    if isinstance(cumulative_2d, (int, float)):
        return f"PC1 + PC2 explain {cumulative_2d * 100:.1f}% variance."
    return "PC1 + PC2 variance metadata unavailable."


def _apply_dark_axes(fig: plt.Figure, ax: plt.Axes, theme: dict[str, str]) -> None:
    fig.patch.set_facecolor(theme["background"])
    ax.set_facecolor(theme["background"])
    for spine in ax.spines.values():
        spine.set_color(theme["text"])
    ax.tick_params(colors=theme["text"])
    ax.xaxis.label.set_color(theme["text"])
    ax.yaxis.label.set_color(theme["text"])
    ax.title.set_color(theme["text"])


def render_headline_chart(paths: VizPaths, artifacts: VizArtifacts) -> Path:
    config = artifacts.config
    theme = _theme(config)
    dpi = int(config.get("export", {}).get("dpi", 300))
    fig_w, fig_h = _post_size_inches(config, dpi)
    disclaimer, era_line = _caption_lines(config)

    df = artifacts.rankings.copy()
    df = df.sort_values("public_headline_score", ascending=True).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    df["label"] = df["rank"].astype(str) + ". " + df["display_name"].astype(str)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    bars = ax.barh(df["label"], df["public_headline_score"], color=theme["accent"])
    ax.invert_yaxis()
    ax.set_xlabel("public_headline_score (lower is better)")
    ax.set_title("21-player GOAT stat-space index (headline)")

    for bar, value in zip(bars, df["public_headline_score"]):
        ax.text(
            value,
            bar.get_y() + bar.get_height() / 2,
            f" {value:.2f}",
            color=theme["text"],
            va="center",
            fontsize=8,
        )

    fig.subplots_adjust(bottom=0.28, left=0.33, right=0.96, top=0.9)
    fig.text(0.02, 0.12, disclaimer, color=theme["text"], fontsize=8, wrap=True)
    fig.text(0.02, 0.07, era_line, color=theme["text"], fontsize=8)
    _apply_dark_axes(fig, ax, theme)

    out_path = paths.posts_output / "goat_rankings.png"
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    return out_path


def render_pca_scatter(paths: VizPaths, artifacts: VizArtifacts) -> Path:
    config = artifacts.config
    theme = _theme(config)
    dpi = int(config.get("export", {}).get("dpi", 300))
    fig_w, fig_h = _post_size_inches(config, dpi)
    disclaimer, era_line = _caption_lines(config)
    variance_line = _variance_summary(artifacts.pca_explained_variance)

    coords = artifacts.pca_coordinates.copy()
    pc1_col = "PC1" if "PC1" in coords.columns else "pc1"
    pc2_col = "PC2" if "PC2" in coords.columns else "pc2"

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    ax.scatter(coords[pc1_col], coords[pc2_col], color=theme["accent"], alpha=0.9)

    for _, row in coords.iterrows():
        ax.text(
            row[pc1_col] + 0.03,
            row[pc2_col] + 0.03,
            str(row["display_name"]),
            fontsize=7,
            color=theme["text"],
        )

    ax.set_title("PCA map of career vectors")
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.axhline(0, color=theme["text"], alpha=0.2, linewidth=0.8)
    ax.axvline(0, color=theme["text"], alpha=0.2, linewidth=0.8)

    fig.subplots_adjust(bottom=0.3, left=0.12, right=0.98, top=0.9)
    fig.text(0.02, 0.16, variance_line, color=theme["text"], fontsize=8)
    fig.text(0.02, 0.11, disclaimer, color=theme["text"], fontsize=8, wrap=True)
    fig.text(0.02, 0.06, era_line, color=theme["text"], fontsize=8)
    _apply_dark_axes(fig, ax, theme)

    out_path = paths.posts_output / "pca_scatter.png"
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    return out_path


def render_similarity_heatmap(paths: VizPaths, artifacts: VizArtifacts) -> Path | None:
    if artifacts.similarity_matrix.empty:
        return None

    config = artifacts.config
    theme = _theme(config)
    dpi = int(config.get("export", {}).get("dpi", 300))
    fig_w, fig_h = _post_size_inches(config, dpi)
    disclaimer, era_line = _caption_lines(config)

    sim = artifacts.similarity_matrix.copy()
    index_col = sim.columns[0]
    sim = sim.set_index(index_col)
    sim = sim.apply(pd.to_numeric, errors="coerce")

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    cmap = sns.color_palette("rocket", as_cmap=True)
    sns.heatmap(sim, ax=ax, cmap=cmap, cbar=True, square=True, linewidths=0.2)
    ax.set_title("Cosine similarity heatmap (play-style proximity)")
    ax.set_xlabel("player_id")
    ax.set_ylabel("player_id")
    ax.tick_params(axis="x", labelrotation=90, labelsize=6)
    ax.tick_params(axis="y", labelsize=6)

    fig.subplots_adjust(bottom=0.28, left=0.2, right=0.95, top=0.9)
    fig.text(0.02, 0.12, disclaimer, color=theme["text"], fontsize=8, wrap=True)
    fig.text(0.02, 0.07, era_line, color=theme["text"], fontsize=8)
    _apply_dark_axes(fig, ax, theme)

    out_path = paths.posts_output / "similarity_heatmap.png"
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    return out_path


def render_index_html(
    paths: VizPaths,
    artifacts: VizArtifacts,
    generated_files: list[Path],
) -> Path:
    disclaimer, era_line = _caption_lines(artifacts.config)
    gate_pass = artifacts.sensitivity_report.get("publish_gate_pass")
    gate_status = "PASS" if gate_pass else "FAIL"

    validation_html = ""
    if artifacts.validation_report is not None:
        validation_html = (
            "<details><summary>Validation report (optional)</summary>"
            f"<pre>{escape(str(artifacts.validation_report))}</pre></details>"
        )

    file_items = "\n".join(
        f'<li><a href="{file.relative_to(paths.viz_output).as_posix()}">{file.name}</a></li>'
        for file in generated_files
    )

    previews = "".join(
        f'<div><h3>{escape(f.name)}</h3>'
        f'<img src="{f.relative_to(paths.viz_output).as_posix()}" alt="{escape(f.name)}"></div>'
        for f in generated_files
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GOAT Viz Output</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0d1117;
      color: #e6edf3;
      padding: 24px;
    }}
    a {{ color: #58a6ff; }}
    img {{ max-width: min(100%, 960px); border: 1px solid #30363d; margin: 12px 0; }}
    .muted {{ color: #8b949e; }}
  </style>
</head>
<body>
  <h1>GOAT Visualization (Step 5)</h1>
  <p><strong>Publish gate:</strong> {gate_status}</p>
  <p class="muted">{escape(disclaimer)}</p>
  <p class="muted">{escape(era_line)}</p>
  <h2>Generated Files</h2>
  <ul>{file_items}</ul>
  <h2>Previews</h2>
  {previews}
  {validation_html}
</body>
</html>
"""
    out_path = paths.viz_output / "index.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def render_all(paths: VizPaths, artifacts: VizArtifacts) -> dict[str, Path]:
    paths.viz_output.mkdir(parents=True, exist_ok=True)
    paths.posts_output.mkdir(parents=True, exist_ok=True)

    generated: dict[str, Path] = {}
    generated["goat_rankings"] = render_headline_chart(paths, artifacts)
    generated["pca_scatter"] = render_pca_scatter(paths, artifacts)

    heatmap_path = render_similarity_heatmap(paths, artifacts)
    if heatmap_path is not None:
        generated["similarity_heatmap"] = heatmap_path

    index_html = render_index_html(paths, artifacts, list(generated.values()))
    generated["index_html"] = index_html
    return generated
