from __future__ import annotations

from html import escape
from pathlib import Path
from textwrap import fill
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .io import VizArtifacts, VizPaths
from .embed_3d import render_embed_3d_html


def _chart_pixels(
    config: dict[str, Any],
    chart_name: str,
    *,
    width: int,
    height: int,
    row_count: int | None = None,
) -> tuple[int, int]:
    charts = config.get("export", {}).get("charts", {})
    spec = charts.get(chart_name, {})
    width_px = int(spec.get("width", width))
    height_px = int(spec.get("height", height))

    if row_count is not None:
        min_height = int(spec.get("min_height", height))
        per_row = int(spec.get("height_per_player", 64))
        height_px = max(min_height, row_count * per_row)

    return width_px, height_px


def _figure_inches(width_px: int, height_px: int, dpi: int) -> tuple[float, float]:
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


def _left_margin_for_names(names: pd.Series) -> float:
    max_chars = int(names.astype(str).str.len().max())
    return min(0.42, 0.16 + max_chars * 0.0085)


def _add_footnotes(
    fig: plt.Figure,
    theme: dict[str, str],
    lines: list[str],
    *,
    bottom: float = 0.08,
) -> None:
    y = bottom + 0.06 * (len(lines) - 1)
    for line in lines:
        if not line:
            continue
        fig.text(
            0.5,
            y,
            fill(line, width=118),
            color=theme["text"],
            fontsize=9,
            ha="center",
            va="top",
            alpha=0.85,
        )
        y -= 0.045


def _annotate_pca_players(
    ax: plt.Axes,
    coords: pd.DataFrame,
    pc1_col: str,
    pc2_col: str,
    theme: dict[str, str],
) -> None:
    x_values = coords[pc1_col]
    y_values = coords[pc2_col]
    x_mid = x_values.median()
    y_mid = y_values.median()
    x_span = max(float(x_values.max() - x_values.min()), 1.0)
    y_span = max(float(y_values.max() - y_values.min()), 1.0)
    x_pad = x_span * 0.04
    y_pad = y_span * 0.05

    for _, row in coords.iterrows():
        x = float(row[pc1_col])
        y = float(row[pc2_col])
        ha = "left" if x >= x_mid else "right"
        va = "bottom" if y >= y_mid else "top"
        dx = x_pad if ha == "left" else -x_pad
        dy = y_pad if va == "bottom" else -y_pad
        ax.annotate(
            str(row["display_name"]),
            (x, y),
            xytext=(x + dx, y + dy),
            textcoords="data",
            fontsize=10,
            color=theme["text"],
            ha=ha,
            va=va,
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": theme["background"],
                "edgecolor": "none",
                "alpha": 0.72,
            },
        )


def render_headline_chart(paths: VizPaths, artifacts: VizArtifacts) -> Path:
    config = artifacts.config
    theme = _theme(config)
    dpi = int(config.get("export", {}).get("dpi", 300))
    disclaimer, era_line = _caption_lines(config)

    df = artifacts.rankings.copy()
    df = df.sort_values("score_goat_index", ascending=True).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)

    width_px, height_px = _chart_pixels(
        config,
        "rankings",
        width=1600,
        height=1400,
        row_count=len(df),
    )
    fig_w, fig_h = _figure_inches(width_px, height_px, dpi)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    y_positions = list(range(len(df)))
    bars = ax.barh(
        y_positions,
        df["score_goat_index"],
        height=0.72,
        color=theme["accent"],
    )
    ax.set_yticks(y_positions)
    ax.set_yticklabels(df["display_name"], fontsize=11)
    ax.invert_yaxis()
    ax.set_xlabel("score_goat_index (lower is better; PCA + titles + clutch)", fontsize=11, labelpad=12)
    ax.set_title(
        "GOAT index (PCA + playoff context)",
        fontsize=16,
        pad=16,
        loc="center",
    )
    ax.tick_params(axis="x", labelsize=10)
    ax.margins(x=0.08)

    for bar, rank, value in zip(bars, df["rank"], df["score_goat_index"]):
        ax.text(
            value,
            bar.get_y() + bar.get_height() / 2,
            f"  #{rank} · {value:.2f}",
            color=theme["text"],
            va="center",
            ha="left",
            fontsize=10,
        )

    left = _left_margin_for_names(df["display_name"])
    fig.subplots_adjust(bottom=0.16, left=left, right=0.94, top=0.92)
    _add_footnotes(fig, theme, [disclaimer, era_line], bottom=0.03)
    _apply_dark_axes(fig, ax, theme)

    out_path = paths.posts_output / "goat_rankings.png"
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
    return out_path


def render_pca_scatter(paths: VizPaths, artifacts: VizArtifacts) -> Path:
    config = artifacts.config
    theme = _theme(config)
    dpi = int(config.get("export", {}).get("dpi", 300))
    disclaimer, era_line = _caption_lines(config)
    variance_line = _variance_summary(artifacts.pca_explained_variance)

    coords = artifacts.pca_coordinates.copy()
    pc1_col = "PC1" if "PC1" in coords.columns else "pc1"
    pc2_col = "PC2" if "PC2" in coords.columns else "pc2"

    width_px, height_px = _chart_pixels(config, "pca", width=1400, height=1200)
    fig_w, fig_h = _figure_inches(width_px, height_px, dpi)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    ax.scatter(
        coords[pc1_col],
        coords[pc2_col],
        color=theme["accent"],
        alpha=0.95,
        s=72,
        edgecolors=theme["text"],
        linewidths=0.4,
    )

    x_min, x_max = float(coords[pc1_col].min()), float(coords[pc1_col].max())
    y_min, y_max = float(coords[pc2_col].min()), float(coords[pc2_col].max())
    x_pad = max((x_max - x_min) * 0.18, 0.5)
    y_pad = max((y_max - y_min) * 0.18, 0.5)
    ax.set_xlim(x_min - x_pad, x_max + x_pad)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)

    _annotate_pca_players(ax, coords, pc1_col, pc2_col, theme)

    ax.set_title("PCA map of career vectors", fontsize=16, pad=16, loc="center")
    ax.set_xlabel("PC1", fontsize=11, labelpad=10)
    ax.set_ylabel("PC2", fontsize=11, labelpad=10)
    ax.axhline(0, color=theme["text"], alpha=0.2, linewidth=0.8)
    ax.axvline(0, color=theme["text"], alpha=0.2, linewidth=0.8)

    fig.subplots_adjust(bottom=0.14, left=0.1, right=0.96, top=0.9)
    _add_footnotes(fig, theme, [variance_line, disclaimer, era_line], bottom=0.02)
    _apply_dark_axes(fig, ax, theme)

    out_path = paths.posts_output / "pca_scatter.png"
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
    return out_path


def render_similarity_heatmap(paths: VizPaths, artifacts: VizArtifacts) -> Path | None:
    if artifacts.similarity_matrix.empty:
        return None

    config = artifacts.config
    theme = _theme(config)
    dpi = int(config.get("export", {}).get("dpi", 300))
    disclaimer, era_line = _caption_lines(config)

    sim = artifacts.similarity_matrix.copy()
    index_col = sim.columns[0]
    sim = sim.set_index(index_col)
    sim = sim.apply(pd.to_numeric, errors="coerce")

    name_map = (
        artifacts.rankings.set_index("player_id")["display_name"].to_dict()
        if "player_id" in artifacts.rankings.columns
        else {}
    )
    sim.index = [name_map.get(str(idx), str(idx)) for idx in sim.index]
    sim.columns = [name_map.get(str(col), str(col)) for col in sim.columns]

    width_px, height_px = _chart_pixels(config, "heatmap", width=1500, height=1400)
    fig_w, fig_h = _figure_inches(width_px, height_px, dpi)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    cmap = sns.color_palette("rocket", as_cmap=True)
    sns.heatmap(sim, ax=ax, cmap=cmap, cbar=True, square=True, linewidths=0.2)
    ax.set_title(
        "Cosine similarity heatmap (play-style proximity)",
        fontsize=16,
        pad=16,
        loc="center",
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.tick_params(axis="x", labelrotation=45, labelsize=9)
    ax.tick_params(axis="y", labelsize=9)

    fig.subplots_adjust(bottom=0.14, left=0.22, right=0.95, top=0.9)
    _add_footnotes(fig, theme, [disclaimer, era_line], bottom=0.03)
    _apply_dark_axes(fig, ax, theme)

    out_path = paths.posts_output / "similarity_heatmap.png"
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
    return out_path


def render_index_html(
    paths: VizPaths,
    artifacts: VizArtifacts,
    generated_files: list[Path],
    embed_3d_path: Path | None = None,
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
        f'<figure class="preview">'
        f'<figcaption>{escape(f.name)}</figcaption>'
        f'<img src="{f.relative_to(paths.viz_output).as_posix()}" alt="{escape(f.name)}">'
        f"</figure>"
        for f in generated_files
    )

    embed_section = ""
    if embed_3d_path is not None:
        rel = embed_3d_path.relative_to(paths.viz_output).as_posix()
        embed_section = f"""
    <h2>3D Stat-Space Explorer</h2>
    <div class="embed-shell">
      <iframe src="{rel}" title="3D PCA embedding" loading="lazy"></iframe>
    </div>
    <p class="center-copy"><a href="{rel}">Open full-screen 3D explorer</a></p>
"""

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GOAT Viz Output</title>
  <style>
    :root {{
      color-scheme: dark;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0d1117;
      color: #e6edf3;
      line-height: 1.5;
    }}
    .page {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 40px 24px 64px;
    }}
    h1, h2 {{
      text-align: center;
      font-weight: 600;
    }}
    h1 {{
      margin-bottom: 8px;
    }}
    .meta {{
      text-align: center;
      margin: 0 auto 24px;
      max-width: 760px;
    }}
    .meta p {{
      margin: 8px 0;
    }}
    a {{ color: #58a6ff; }}
    ul {{
      max-width: 520px;
      margin: 0 auto 32px;
      padding-left: 1.2rem;
    }}
    .gallery {{
      display: grid;
      gap: 40px;
      margin-top: 24px;
    }}
    .preview {{
      margin: 0;
      text-align: center;
    }}
    .preview img {{
      display: block;
      width: min(100%, 980px);
      height: auto;
      margin: 12px auto 0;
      border: 1px solid #30363d;
      border-radius: 8px;
    }}
    figcaption {{
      color: #8b949e;
      font-size: 0.95rem;
    }}
    .muted {{ color: #8b949e; }}
    .center-copy {{ text-align: center; max-width: 760px; margin: 0 auto 16px; }}
    .embed-shell {{
      width: min(100%, 980px);
      height: min(72vh, 720px);
      margin: 0 auto 12px;
      border: 1px solid #30363d;
      border-radius: 12px;
      overflow: hidden;
      background: #0d1117;
    }}
    .embed-shell iframe {{
      width: 100%;
      height: 100%;
      border: 0;
      display: block;
    }}
    details {{
      max-width: 760px;
      margin: 32px auto 0;
    }}
    pre {{
      overflow-x: auto;
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 12px;
    }}
  </style>
</head>
<body>
  <main class="page">
    <h1>GOAT Visualization</h1>
    <div class="meta">
      <p><strong>Publish gate:</strong> {gate_status}</p>
      <p class="muted">{escape(disclaimer)}</p>
      <p class="muted">{escape(era_line)}</p>
    </div>
    <h2>Generated Files</h2>
    <ul>{file_items}</ul>
    {embed_section}
    <h2>Previews</h2>
    <div class="gallery">
      {previews}
    </div>
    {validation_html}
  </main>
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

    embed_3d_path = None
    if artifacts.config.get("embed_3d", {}).get("enabled", True):
        embed_3d_path = render_embed_3d_html(paths, artifacts)
        generated["embed_3d"] = embed_3d_path

    index_html = render_index_html(
        paths,
        artifacts,
        [p for k, p in generated.items() if k not in {"index_html", "embed_3d"}],
        embed_3d_path=embed_3d_path,
    )
    generated["index_html"] = index_html
    return generated
