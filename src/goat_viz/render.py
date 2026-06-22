from __future__ import annotations

import json
from html import escape
from pathlib import Path
from textwrap import fill
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .io import VizArtifacts, VizPaths
from .alchemy_page import render_alchemy_html
from .pca_map import render_pca_map_html
from .embed_3d import render_embed_3d_html
from .how_it_works import render_how_it_works_html
from .site_shell import render_site_shell_html


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


def _player_color_palette(count: int) -> list[tuple[float, float, float, float]]:
    import matplotlib.cm as cm
    import numpy as np

    cmap = plt.colormaps["turbo"].resampled(max(count, 1))
    return [cmap(i / max(count - 1, 1)) for i in range(count)]


def _rankings_plain_footnotes(era_line: str) -> list[str]:
    return [
        (
            "How to read: #1 at the top is the highest-ranked player on this chart. "
            "Each score blends career production, team success, and awards — not any one statistic. "
            "Use the rank order (#1, #2, …) to compare players; bar length is the composite number, not a simple quality meter."
        ),
        era_line or "Scores are era-adjusted so players from different decades compare fairly.",
    ]


def _heatmap_tick_label(name: str) -> str:
    parts = str(name).strip().split()
    return parts[-1] if len(parts) > 1 else str(name)


def _wrap_footnote_lines(lines: list[str], *, width: int = 92) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        if not line:
            continue
        wrapped.extend(fill(line, width=width).splitlines())
    return wrapped


def _footnote_axes_bottom(
    line_count: int,
    *,
    line_height: float = 0.028,
    margin_bottom: float = 0.012,
    axis_label_reserve: float = 0.20,
    gap: float = 0.05,
) -> float:
    """Reserve figure fraction below axes for tick labels, xlab, and footnotes."""
    if line_count <= 0:
        return axis_label_reserve + gap + 0.04
    footnote_block = margin_bottom + line_count * line_height
    return min(0.58, axis_label_reserve + gap + footnote_block)


def _readable_footnotes(
    fig: plt.Figure,
    theme: dict[str, str],
    lines: list[str],
    *,
    width: int = 92,
    line_height: float = 0.028,
    margin_bottom: float = 0.012,
) -> None:
    """Stack wrapped footnotes upward from the figure bottom (below the axes)."""
    wrapped = _wrap_footnote_lines(lines, width=width)
    y = margin_bottom
    for line in wrapped:
        fig.text(
            0.5,
            y,
            line,
            color=theme["text"],
            fontsize=8.5,
            ha="center",
            va="bottom",
            alpha=0.9,
        )
        y += line_height


def _footer_height_ratio(line_count: int) -> float:
    return min(0.34, 0.14 + line_count * 0.032)


def _render_footer_axes(
    footer_ax: plt.Axes,
    theme: dict[str, str],
    lines: list[str],
    *,
    width: int = 92,
) -> None:
    """Draw wrapped captions inside a dedicated footer axes (no overlap with xlab)."""
    footer_ax.axis("off")
    footer_ax.set_facecolor(theme["background"])
    wrapped = _wrap_footnote_lines(lines, width=width)
    if not wrapped:
        return
    y = 0.98
    step = 0.92 / len(wrapped)
    for line in wrapped:
        footer_ax.text(
            0.5,
            y,
            line,
            transform=footer_ax.transAxes,
            ha="center",
            va="top",
            fontsize=8.5,
            color=theme["text"],
            alpha=0.9,
        )
        y -= step


def _apply_footnotes_layout(
    fig: plt.Figure,
    theme: dict[str, str],
    lines: list[str],
    *,
    width: int = 92,
    left: float = 0.1,
    right: float = 0.96,
    top: float = 0.88,
    line_height: float = 0.028,
    axis_label_reserve: float = 0.20,
    gap: float = 0.05,
) -> None:
    """Set axes margins from footnote height, then draw captions under the plot."""
    wrapped = _wrap_footnote_lines(lines, width=width)
    bottom = _footnote_axes_bottom(
        len(wrapped),
        line_height=line_height,
        axis_label_reserve=axis_label_reserve,
        gap=gap,
    )
    fig.subplots_adjust(bottom=bottom, left=left, right=right, top=top)
    _readable_footnotes(fig, theme, lines, width=width, line_height=line_height)



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
    df = artifacts.rankings.copy()
    df = df.sort_values("score_goat_index", ascending=True).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    short_names = df["display_name"].map(_heatmap_tick_label)

    width_px, height_px = _chart_pixels(
        config,
        "rankings",
        width=2000,
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
    ax.set_yticklabels(short_names, fontsize=7)
    ax.invert_yaxis()
    for label in ax.get_yticklabels():
        label.set_ha("right")
    ax.set_xlabel("Composite GOAT score", fontsize=10, labelpad=6)
    ax.set_title(
        "GOAT ranking",
        fontsize=16,
        pad=12,
        loc="center",
    )
    ax.tick_params(axis="x", labelsize=8, pad=2)
    ax.margins(x=0.08)

    x_max = float(df["score_goat_index"].max())
    x_pad = max(x_max * 0.04, 0.15)
    for bar, rank, value in zip(bars, df["rank"], df["score_goat_index"]):
        label_x = max(float(value), 0) + x_pad
        ax.text(
            label_x,
            bar.get_y() + bar.get_height() / 2,
            f"#{rank} · {value:.2f}",
            color=theme["text"],
            va="center",
            ha="left",
            fontsize=8,
        )

    left = min(0.34, _left_margin_for_names(short_names) + 0.03)
    fig.subplots_adjust(bottom=0.05, left=left, right=0.96, top=0.98)
    _apply_dark_axes(fig, ax, theme)

    out_path = paths.posts_output / "goat_rankings.png"
    fig.savefig(out_path, dpi=dpi, pad_inches=0.25)
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
    colors = _player_color_palette(len(coords))
    ax.scatter(
        coords[pc1_col],
        coords[pc2_col],
        c=colors,
        alpha=0.92,
        s=64,
        edgecolors=theme["text"],
        linewidths=0.35,
    )

    x_min, x_max = float(coords[pc1_col].min()), float(coords[pc1_col].max())
    y_min, y_max = float(coords[pc2_col].min()), float(coords[pc2_col].max())
    x_pad = max((x_max - x_min) * 0.18, 0.5)
    y_pad = max((y_max - y_min) * 0.18, 0.5)
    ax.set_xlim(x_min - x_pad, x_max + x_pad)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)

    ax.set_title("PCA map of career vectors", fontsize=16, pad=16, loc="center")
    ax.set_xlabel("PC1 (impact direction)", fontsize=11, labelpad=10)
    ax.set_ylabel("PC2 (style mix)", fontsize=11, labelpad=10)
    ax.axhline(0, color=theme["text"], alpha=0.2, linewidth=0.8)
    ax.axvline(0, color=theme["text"], alpha=0.2, linewidth=0.8)

    footnote_lines = [
        variance_line,
        "Each dot is one player (unique color). Names: PCA Map tab in the app.",
        era_line,
    ]
    _apply_footnotes_layout(fig, theme, footnote_lines, left=0.1, top=0.92)
    _apply_dark_axes(fig, ax, theme)

    out_path = paths.posts_output / "pca_scatter.png"
    fig.savefig(out_path, dpi=dpi, pad_inches=0.25)
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
    sim.index = [_heatmap_tick_label(name_map.get(str(idx), str(idx))) for idx in sim.index]
    sim.columns = [_heatmap_tick_label(name_map.get(str(col), str(col))) for col in sim.columns]

    width_px, height_px = _chart_pixels(config, "heatmap", width=4000, height=4000)
    fig_w, fig_h = _figure_inches(width_px, height_px, dpi)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    cmap = sns.color_palette("rocket", as_cmap=True)
    sns.heatmap(sim, ax=ax, cmap=cmap, cbar=True, square=True, linewidths=0.2)
    tick_font = max(5, min(14, round(5 * width_px / 2000)))
    title_font = max(16, min(32, round(16 * width_px / 2000)))
    ax.set_title(
        "Cosine similarity heatmap (play-style proximity)",
        fontsize=title_font,
        pad=max(16, round(16 * width_px / 2000)),
        loc="center",
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.tick_params(axis="x", labelrotation=45, labelsize=tick_font, pad=2)
    ax.tick_params(axis="y", labelsize=tick_font, pad=2)
    for label in ax.get_xticklabels():
        label.set_ha("right")
        label.set_rotation_mode("anchor")

    _apply_footnotes_layout(
        fig,
        theme,
        [disclaimer, era_line],
        left=0.30,
        top=0.92,
        axis_label_reserve=0.26,
    )
    _apply_dark_axes(fig, ax, theme)

    out_path = paths.posts_output / "similarity_heatmap.png"
    fig.savefig(out_path, dpi=dpi, pad_inches=0.25)
    plt.close(fig)
    return out_path




def _format_validation_english(report: dict[str, Any]) -> str:
    """Human-readable summary of the optional XGBoost validation report."""
    lines: list[str] = []
    lines.append(f"Validator: {report.get('validator', 'unknown')}")
    if report.get("non_gating"):
        lines.append("This check is informational only — it does not gate publishing.")
    split = report.get("split", {})
    if split:
        lines.append(
            f"Train seasons through {split.get('train_seasons_end', '?')}; "
            f"test seasons from {split.get('test_seasons_start', '?')} onward."
        )
    primary = report.get("primary_metrics", {})
    if primary:
        lines.append("")
        lines.append("Primary test metrics:")
        if "test_sample_count" in primary:
            lines.append(f"  • Test seasons evaluated: {primary['test_sample_count']}")
        mvp = primary.get("mvp_vote_share", {})
        if mvp:
            lines.append(
                f"  • MVP vote share alignment (Spearman): {float(mvp.get('value', 0)):.3f} "
                "(higher = model tracks MVP voting better)"
            )
        all_nba = primary.get("all_nba_first", {})
        if all_nba:
            lines.append(
                f"  • All-NBA 1st team detection (ROC AUC): {float(all_nba.get('value', 0)):.3f} "
                "(1.0 = perfect separation)"
            )
    secondary = report.get("secondary_metrics", {})
    if secondary:
        lines.append("")
        lines.append("Secondary checks:")
        spearman = secondary.get("career_goat_index_vs_mean_test_prediction_spearman")
        if spearman is not None:
            lines.append(
                f"  • Career GOAT index vs mean test prediction (Spearman): {float(spearman):.3f}"
            )
        if "player_count" in secondary:
            lines.append(f"  • Players in career comparison: {secondary['player_count']}")
    return "\n".join(lines)


def _validation_report_html(report: dict[str, Any]) -> str:
    pretty_json = json.dumps(report, indent=2, sort_keys=False)
    english = _format_validation_english(report)
    return f"""
    <details class="validation-section">
      <summary>Model validation (optional)</summary>
      <div class="tab-bar">
        <button type="button" class="tab-btn active" data-tab="validation-english">Summary</button>
        <button type="button" class="tab-btn" data-tab="validation-json">Raw JSON</button>
      </div>
      <div id="validation-english" class="tab-panel active validation-scroll">
        <pre class="english">{escape(english)}</pre>
      </div>
      <div id="validation-json" class="tab-panel validation-scroll">
        <pre>{escape(pretty_json)}</pre>
      </div>
    </details>
    <script>
      (function () {{
        const section = document.querySelector('.validation-section');
        if (!section) return;
        section.querySelectorAll('.tab-btn').forEach((btn) => {{
          btn.addEventListener('click', () => {{
            section.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
            section.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
            btn.classList.add('active');
            const panel = section.querySelector('#' + btn.dataset.tab);
            if (panel) panel.classList.add('active');
          }});
        }});
      }})();
    </script>"""





def _rankings_description_html(config: dict[str, Any]) -> str:
    _, era_line = _caption_lines(config)
    lines = _rankings_plain_footnotes(era_line)
    paragraphs = "".join(f"<p>{escape(line)}</p>" for line in lines if line)
    return f'<div class="preview-description">{paragraphs}</div>'


_PREVIEW_CHART_KEYS: dict[str, str] = {
    "goat_rankings.png": "rankings",
    "pca_scatter.png": "pca",
    "similarity_heatmap.png": "heatmap",
}

_PREVIEW_TITLES: dict[str, str] = {
    "goat_rankings.png": "GOAT ranking",
    "pca_scatter.png": "PCA map (2D)",
    "similarity_heatmap.png": "Play-style similarity",
}

HOME_PREVIEW_KEYS = frozenset({"goat_rankings", "pca_scatter", "similarity_heatmap"})


def _chart_description_html(filename: str, config: dict[str, Any]) -> str:
    _, era_line = _caption_lines(config)
    copy: dict[str, list[str]] = {
        "pca_scatter.png": [
            "Each dot is one player along the two strongest stat-space axes (PC1 and PC2). "
            "Players near each other have similar profiles — this is not a better/worse chart.",
        ],
        "similarity_heatmap.png": [
            "Cell color shows how alike two players' stat profiles are (cosine similarity). "
            "Brighter red means more similar play style, not greater greatness.",
        ],
    }
    lines = copy.get(filename, [])
    if era_line and filename != "goat_rankings.png":
        lines = list(lines) + [era_line]
    if not lines:
        return ""
    paragraphs = "".join(f"<p>{escape(line)}</p>" for line in lines if line)
    return f'<div class="preview-description">{paragraphs}</div>'


def _preview_title(filename: str) -> str:
    return _PREVIEW_TITLES.get(filename, filename.replace("_", " ").replace(".png", ""))



def _preview_dimensions(
    config: dict[str, Any],
    filename: str,
    *,
    row_count: int | None = None,
) -> tuple[int, int]:
    chart_key = _PREVIEW_CHART_KEYS.get(filename)
    if chart_key == "rankings":
        return _chart_pixels(
            config,
            "rankings",
            width=2000,
            height=1400,
            row_count=row_count,
        )
    defaults: dict[str, tuple[int, int]] = {
        "pca": (1400, 1400),
        "heatmap": (4000, 4000),
    }
    if chart_key in defaults:
        w, h = defaults[chart_key]
        return _chart_pixels(config, chart_key, width=w, height=h)
    return 980, 720


def _preview_figure(
    paths: VizPaths,
    config: dict[str, Any],
    file: Path,
    *,
    row_count: int | None = None,
) -> str:
    width_px, height_px = _preview_dimensions(config, file.name, row_count=row_count)
    rel = file.relative_to(paths.viz_output).as_posix()
    is_rankings = file.name == "goat_rankings.png"
    is_heatmap = file.name == "similarity_heatmap.png"
    if is_rankings:
        figure_class = "preview preview-rankings"
        frame_class = "preview-chart preview-frame preview-rankings"
    elif is_heatmap:
        figure_class = "preview preview-heatmap"
        frame_class = "preview-chart preview-frame preview-heatmap"
    else:
        figure_class = "preview"
        frame_class = "preview-frame"
    title = _preview_title(file.name)
    alt = escape(title)
    if is_rankings:
        img_tag = (
            f'<img src="{rel}" alt="{alt}" loading="lazy" />'
        )
        description_html = _rankings_description_html(config)
    elif is_heatmap:
        img_tag = (
            f'<img src="{rel}" alt="{alt}" loading="lazy" />'
        )
        description_html = _chart_description_html(file.name, config)
    else:
        img_tag = (
            f'<img src="{rel}" width="{width_px}" height="{height_px}" '
            f'alt="{alt}" loading="lazy" />'
        )
        description_html = _chart_description_html(file.name, config)
    return (
        f'<figure class="{figure_class}">'
        f'<figcaption>{escape(title)}</figcaption>'
        f'<div class="{frame_class}">'
        f"{img_tag}"
        f"</div>"
        f"{description_html}"
        f"</figure>"
    )

def render_home_html(
    paths: VizPaths,
    artifacts: VizArtifacts,
    generated_files: list[Path],
) -> Path:
    disclaimer, era_line = _caption_lines(artifacts.config)

    validation_html = ""
    if artifacts.validation_report is not None:
        validation_html = _validation_report_html(artifacts.validation_report)

    row_count = None
    if "player_id" in artifacts.rankings.columns:
        row_count = len(artifacts.rankings)
    previews = "".join(
        _preview_figure(paths, artifacts.config, f, row_count=row_count)
        for f in generated_files
    )


    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GOAT Overview</title>
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
    .preview-frame {{
      width: min(100%, 980px);
      height: min(72vh, 800px);
      margin: 12px auto 0;
      border: 1px solid #30363d;
      border-radius: 8px;
      overflow: hidden;
      background: #0d1117;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .preview-frame.preview-rankings {{
      width: min(100%, 1100px);
      max-height: min(85vh, 900px);
      height: auto;
      min-height: 420px;
      overflow-x: hidden;
      overflow-y: auto;
      display: block;
      padding: 0;
    }}
    .preview-frame img {{
      display: block;
      max-width: 100%;
      max-height: 100%;
      width: auto;
      height: auto;
      object-fit: contain;
      object-position: center center;
    }}
    .preview-frame.preview-rankings img {{
      width: 100%;
      max-width: 100%;
      max-height: none;
      height: auto;
      object-fit: unset;
    }}
    .preview-frame.preview-heatmap {{
      width: min(100%, 1100px);
      max-height: min(92vh, 1100px);
      height: auto;
      min-height: 520px;
      overflow: auto;
      display: block;
      padding: 0;
    }}
    .preview-frame.preview-heatmap img {{
      width: 100%;
      max-width: 100%;
      max-height: none;
      height: auto;
      object-fit: unset;
    }}
    .preview.preview-rankings .preview-chart,
    .preview.preview-heatmap .preview-chart {{
      margin-bottom: 0;
    }}
    .preview-description {{
      width: min(100%, 1100px);
      margin: 16px auto 0;
      padding: 14px 16px;
      border: 1px solid #30363d;
      border-radius: 8px;
      background: #161b22;
      text-align: left;
      color: #8b949e;
      font-size: 0.9rem;
      line-height: 1.55;
    }}
    .preview-description p {{
      margin: 0 0 10px;
    }}
    .preview-description p:last-child {{
      margin-bottom: 0;
    }}
    figcaption {{
      color: #e6edf3;
      font-size: 1rem;
      font-weight: 600;
      margin-bottom: 4px;
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
    .validation-section {{
      margin-top: 40px;
      max-width: 760px;
      margin-left: auto;
      margin-right: auto;
      border: 1px solid #30363d;
      border-radius: 10px;
      padding: 12px 16px 16px;
      background: #161b22;
    }}
    .validation-section summary {{
      cursor: pointer;
      font-weight: 600;
      font-size: 0.9rem;
      color: #e6edf3;
      list-style-position: outside;
    }}
    .validation-section[open] summary {{
      margin-bottom: 12px;
    }}
    .tab-bar {{
      display: flex;
      justify-content: center;
      gap: 8px;
      margin: 16px 0 12px;
    }}
    .tab-btn {{
      padding: 6px 14px;
      border-radius: 8px;
      border: 1px solid #484f58;
      background: #21262d;
      color: #e6edf3;
      cursor: pointer;
      font-size: 0.85rem;
    }}
    .tab-btn:hover {{
      border-color: #58a6ff;
    }}
    .tab-btn.active {{
      background: #f97316;
      color: #0d1117;
      border-color: #f97316;
      font-weight: 600;
    }}
    .tab-panel {{
      display: none;
      max-width: 760px;
      margin: 0 auto;
    }}
    .tab-panel.active {{
      display: block;
    }}
    .validation-scroll {{
      max-height: min(50vh, 420px);
      overflow: auto;
      padding: 2px;
    }}
    .validation-scroll pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      overflow: visible;
    }}
    pre.english {{
      white-space: pre-wrap;
      word-break: break-word;
    }}
  </style>
</head>
<body>
  <main class="page">
<h1>Overview</h1>
    <div class="meta">
      <p class="muted">Compare curated all-time players across rankings, maps, and blends. Open <strong>How It Works</strong> in the nav bar for the full math behind each model.</p>
      <p class="muted">{escape(era_line)}</p>
    </div>
    <h2>Charts</h2>
    <div class="gallery">
      {previews}
    </div>
    {validation_html}
  </main>
</body>
</html>
"""
    out_path = paths.viz_output / "home.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def render_all(paths: VizPaths, artifacts: VizArtifacts) -> dict[str, Path]:
    paths.viz_output.mkdir(parents=True, exist_ok=True)
    paths.posts_output.mkdir(parents=True, exist_ok=True)

    generated: dict[str, Path] = {}
    generated["goat_rankings"] = render_headline_chart(paths, artifacts)
    generated["pca_scatter"] = render_pca_scatter(paths, artifacts)
    generated["pca_map"] = render_pca_map_html(paths, artifacts)

    heatmap_path = render_similarity_heatmap(paths, artifacts)
    if heatmap_path is not None:
        generated["similarity_heatmap"] = heatmap_path

    embed_3d_path = None
    if artifacts.config.get("embed_3d", {}).get("enabled", True):
        embed_3d_path = render_embed_3d_html(paths, artifacts)
        generated["embed_3d"] = embed_3d_path

    alchemy_path = None
    if artifacts.config.get("alchemy_page", {}).get("enabled", True):
        alchemy_path = render_alchemy_html(paths, artifacts)
        generated["alchemy"] = alchemy_path

    theme = _theme(artifacts.config)
    generated["how_it_works"] = render_how_it_works_html(paths, artifacts)
    home_html = render_home_html(
        paths,
        artifacts,
        [p for k, p in generated.items() if k in HOME_PREVIEW_KEYS],
    )
    generated["home_html"] = home_html

    shell_html = render_site_shell_html(
        accent=theme["accent"],
        background=theme["background"],
        text=theme["text"],
    )
    index_path = paths.viz_output / "index.html"
    index_path.write_text(shell_html, encoding="utf-8")
    generated["index_html"] = index_path
    return generated
