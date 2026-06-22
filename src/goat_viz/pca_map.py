from __future__ import annotations

from html import escape
from pathlib import Path

from .io import VizArtifacts, VizPaths
from .site_shell import SITE_EMBED_HEAD, SITE_NAV_MESSAGE_JS


def _player_colors(count: int) -> list[str]:
    return [f"hsl({(i * 137.508) % 360:.1f}, 72%, 58%)" for i in range(count)]


def render_pca_map_html(paths: VizPaths, artifacts: VizArtifacts) -> Path:
    config = artifacts.config
    theme = config.get("theme", {})
    bg = theme.get("background", "#0d1117")
    text = theme.get("text", "#e6edf3")
    muted = "#8b949e"
    accent = theme.get("accent", "#f97316")

    coords = artifacts.pca_coordinates.copy()
    pc1_col = "PC1" if "PC1" in coords.columns else "pc1"
    pc2_col = "PC2" if "PC2" in coords.columns else "pc2"
    if "display_name" not in coords.columns:
        coords["display_name"] = coords.get("player_id", coords.index).astype(str)
    if "player_id" not in coords.columns:
        coords["player_id"] = coords.index.astype(str)
    coords = coords.sort_values("display_name")

    player_ids = coords["player_id"].astype(str).tolist()
    names = coords["display_name"].astype(str).tolist()
    x_vals = coords[pc1_col].astype(float).tolist()
    y_vals = coords[pc2_col].astype(float).tolist()
    colors = _player_colors(len(names))

    cum_2d = artifacts.pca_explained_variance.get("cumulative_2d")
    variance_line = (
        f"PC1 + PC2 explain {float(cum_2d) * 100:.1f}% of variance."
        if isinstance(cum_2d, (int, float)) else "See MATHS.md for variance shares."
    )
    captions = config.get("captions", {})
    disclaimer = captions.get("exploratory_disclaimer", "")
    era_line = captions.get("era_adjustment", "")

    x_min, x_max = min(x_vals), max(x_vals)
    y_min, y_max = min(y_vals), max(y_vals)
    x_pad = max((x_max - x_min) * 0.12, 0.4)
    y_pad = max((y_max - y_min) * 0.12, 0.4)
    plot_x_min, plot_x_max = x_min - x_pad, x_max + x_pad
    plot_y_min, plot_y_max = y_min - y_pad, y_max + y_pad

    def to_svg_x(x: float) -> float:
        return 40 + (x - plot_x_min) / max(plot_x_max - plot_x_min, 1e-9) * 720

    def to_svg_y(y: float) -> float:
        return 20 + (plot_y_max - y) / max(plot_y_max - plot_y_min, 1e-9) * 520

    dots_svg: list[str] = []
    legend_items: list[str] = []
    for player_id, name, x, y, color in zip(player_ids, names, x_vals, y_vals, colors):
        cx, cy = to_svg_x(x), to_svg_y(y)
        safe_name = escape(name)
        safe_id = escape(player_id)
        dots_svg.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="{color}" stroke="{text}" '
            f'stroke-width="0.6" data-id="{safe_id}" data-label="{safe_name}" '
            f'class="pca-dot" tabindex="0" role="img" aria-label="{safe_name}"></circle>'
        )
        legend_items.append(
            f'<div class="legend-row" data-id="{safe_id}" role="button" tabindex="0">'
            f'<input type="checkbox" class="legend-toggle" checked aria-label="Show {safe_name}" />'
            f'<span class="swatch" style="background:{color}"></span>'
            f'<span class="legend-name">{safe_name}</span>'
            f'<span class="legend-coords">({x:.2f}, {y:.2f})</span>'
            f"</div>"
        )

    grid_lines = []
    if plot_x_min <= 0 <= plot_x_max:
        zx = to_svg_x(0)
        grid_lines.append(f'<line x1="{zx:.1f}" y1="20" x2="{zx:.1f}" y2="540" stroke="{text}" stroke-opacity="0.15"/>')
    if plot_y_min <= 0 <= plot_y_max:
        zy = to_svg_y(0)
        grid_lines.append(f'<line x1="40" y1="{zy:.1f}" x2="760" y2="{zy:.1f}" stroke="{text}" stroke-opacity="0.15"/>')

    embed_head = SITE_EMBED_HEAD
    nav_js = SITE_NAV_MESSAGE_JS
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PCA Map — GOAT Viz</title>
{embed_head}
  <style>
    html, body {{ margin: 0; background: {bg}; color: {text}; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    #app {{ display: grid; grid-template-columns: minmax(0, 1fr) min(300px, 34vw); min-height: 100vh; }}
    #main {{ padding: 20px 16px 24px; display: flex; flex-direction: column; min-width: 0; }}
    header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }}
    header h1 {{ margin: 0; font-size: 1.1rem; font-weight: 600; }}
    header a {{ color: {accent}; text-decoration: none; font-size: 0.85rem; }}
    .explain {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 14px; margin-bottom: 12px; font-size: 0.82rem; line-height: 1.55; color: {muted}; }}
    .explain strong {{ color: {text}; }}
    .explain ul {{ margin: 8px 0 0; padding-left: 1.2rem; }}
    .plot-wrap {{ border: 1px solid #30363d; border-radius: 10px; background: #0d1117; overflow: hidden; position: relative; }}
    svg {{ width: 100%; height: auto; display: block; }}
    #pca-tooltip {{
      position: fixed;
      pointer-events: none;
      background: #161b22;
      border: 1px solid #30363d;
      color: {text};
      padding: 5px 9px;
      border-radius: 6px;
      font-size: 0.78rem;
      line-height: 1.2;
      z-index: 50;
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
      transform: translate(12px, -50%);
      white-space: nowrap;
    }}
    #pca-tooltip[hidden] {{ display: none; }}
    #legend-panel {{ border-left: 1px solid #30363d; display: flex; flex-direction: column; min-height: 0; background: {bg}; }}
    #legend-panel h2 {{ margin: 0; padding: 14px 14px 6px; font-size: 0.9rem; font-weight: 600; }}
    .legend-actions {{
      display: flex; gap: 8px; padding: 0 14px 8px;
    }}
    .legend-actions button {{
      flex: 1;
      padding: 5px 8px;
      border-radius: 6px;
      border: 1px solid #484f58;
      background: #21262d;
      color: {text};
      font-size: 0.72rem;
      cursor: pointer;
    }}
    .legend-actions button:hover {{ border-color: {accent}; background: #30363d; }}
    #visible-count {{ color: {muted}; font-size: 0.75rem; padding: 0 14px 6px; }}
    #legend-search {{ margin: 0 14px 8px; padding: 7px 10px; border-radius: 8px; border: 1px solid #484f58; background: #21262d; color: {text}; width: calc(100% - 28px); box-sizing: border-box; font-size: 0.8rem; }}
    #legend-list {{ overflow-y: auto; flex: 1; padding: 0 10px 14px; min-height: 0; max-height: calc(100vh - 160px); }}
    .legend-row {{
      display: grid;
      grid-template-columns: 16px 14px 1fr auto;
      gap: 8px;
      align-items: center;
      padding: 5px 6px;
      border-radius: 6px;
      font-size: 0.76rem;
      cursor: pointer;
      user-select: none;
    }}
    .legend-row:hover, .legend-row.active {{ background: rgba(249, 115, 22, 0.12); }}
    .legend-row.off {{ opacity: 0.45; }}
    .legend-row.off .legend-name {{ text-decoration: line-through; }}
    .legend-toggle {{ margin: 0; accent-color: {accent}; cursor: pointer; }}
    .swatch {{ width: 12px; height: 12px; border-radius: 999px; border: 1px solid rgba(255,255,255,0.35); }}
    .legend-name {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .legend-coords {{ color: {muted}; font-size: 0.7rem; white-space: nowrap; }}
    .pca-dot {{ cursor: pointer; transition: opacity 0.15s ease; }}
    .pca-dot.hidden {{ opacity: 0; pointer-events: none; }}
    .pca-dot.highlight {{ stroke: {accent}; stroke-width: 2.2; }}
  </style>
</head>
<body>
  <div id="app">
    <div id="main">
      <header><h1>PCA map of career vectors</h1></header>
      <div class="explain">
        <strong>How to read this chart</strong>
        <ul>
          <li>Each colored dot is one allowlist player at (PC1, PC2).</li>
          <li><strong>PC1</strong> (horizontal) ≈ impact; <strong>PC2</strong> (vertical) ≈ style mix.</li>
          <li>{escape(variance_line)}</li>
          <li>Hover a dot for the player name. Use the legend checkboxes to show or hide players.</li>
        </ul>
        <p style="margin:10px 0 0;">{escape(disclaimer)}</p>
        <p style="margin:6px 0 0;">{escape(era_line)}</p>
      </div>
      <div class="plot-wrap">
        <svg viewBox="0 0 800 560" role="img" aria-label="PCA scatter plot">
          <rect width="800" height="560" fill="{bg}"/>
          {''.join(grid_lines)}
          <text x="400" y="555" fill="{muted}" font-size="11" text-anchor="middle">PC1 →</text>
          <text x="12" y="290" fill="{muted}" font-size="11" text-anchor="middle" transform="rotate(-90 12 290)">PC2 →</text>
          {''.join(dots_svg)}
        </svg>
      </div>
    </div>
    <aside id="legend-panel">
      <h2>Players ({len(names)})</h2>
      <p id="visible-count"></p>
      <div class="legend-actions">
        <button type="button" id="show-all-players">Show all</button>
        <button type="button" id="hide-all-players">Hide all</button>
      </div>
      <input id="legend-search" type="search" placeholder="Filter legend..." />
      <div id="legend-list">{''.join(legend_items)}</div>
    </aside>
  </div>
  <div id="pca-tooltip" hidden></div>
  <script>
    const rows = Array.from(document.querySelectorAll('.legend-row'));
    const dots = Array.from(document.querySelectorAll('.pca-dot'));
    const dotById = new Map(dots.map((d) => [d.dataset.id, d]));
    const rowById = new Map(rows.map((r) => [r.dataset.id, r]));
    const tooltip = document.getElementById('pca-tooltip');
    const visibleCountEl = document.getElementById('visible-count');

    function setVisible(playerId, visible) {{
      const dot = dotById.get(playerId);
      const row = rowById.get(playerId);
      if (!dot || !row) return;
      const checkbox = row.querySelector('.legend-toggle');
      dot.classList.toggle('hidden', !visible);
      row.classList.toggle('off', !visible);
      if (checkbox) checkbox.checked = visible;
      updateVisibleCount();
    }}

    function isVisible(playerId) {{
      const dot = dotById.get(playerId);
      return dot ? !dot.classList.contains('hidden') : false;
    }}

    function toggleVisible(playerId) {{
      setVisible(playerId, !isVisible(playerId));
    }}

    function updateVisibleCount() {{
      const shown = dots.filter((d) => !d.classList.contains('hidden')).length;
      visibleCountEl.textContent = shown + ' of ' + dots.length + ' visible';
    }}

    function highlight(playerId, on) {{
      dots.forEach((d) => d.classList.toggle('highlight', on && d.dataset.id === playerId));
      rows.forEach((r) => r.classList.toggle('active', on && r.dataset.id === playerId));
    }}

    document.getElementById('legend-search').addEventListener('input', (e) => {{
      const q = e.target.value.trim().toLowerCase();
      rows.forEach((row) => {{
        const name = row.querySelector('.legend-name')?.textContent?.toLowerCase() || '';
        row.style.display = name.includes(q) ? 'grid' : 'none';
      }});
    }});

    rows.forEach((row) => {{
      const playerId = row.dataset.id;
      const checkbox = row.querySelector('.legend-toggle');
      checkbox.addEventListener('change', () => setVisible(playerId, checkbox.checked));
      row.addEventListener('click', (e) => {{
        if (e.target.closest('.legend-toggle')) return;
        const next = !isVisible(playerId);
        setVisible(playerId, next);
      }});
      row.addEventListener('keydown', (e) => {{
        if (e.key === 'Enter' || e.key === ' ') {{
          e.preventDefault();
          toggleVisible(playerId);
        }}
      }});
      row.addEventListener('mouseenter', () => highlight(playerId, true));
      row.addEventListener('mouseleave', () => highlight(playerId, false));
    }});

    dots.forEach((dot) => {{
      const playerId = dot.dataset.id;
      dot.addEventListener('mouseenter', () => {{
        if (dot.classList.contains('hidden')) return;
        tooltip.textContent = dot.dataset.label || '';
        tooltip.hidden = false;
        highlight(playerId, true);
      }});
      dot.addEventListener('mousemove', (e) => {{
        if (tooltip.hidden) return;
        tooltip.style.left = e.clientX + 'px';
        tooltip.style.top = e.clientY + 'px';
      }});
      dot.addEventListener('mouseleave', () => {{
        tooltip.hidden = true;
        highlight(playerId, false);
      }});
      dot.addEventListener('click', () => toggleVisible(playerId));
      dot.addEventListener('keydown', (e) => {{
        if (e.key === 'Enter' || e.key === ' ') {{
          e.preventDefault();
          toggleVisible(playerId);
        }}
      }});
    }});

    document.getElementById('show-all-players').addEventListener('click', () => {{
      rows.forEach((row) => setVisible(row.dataset.id, true));
    }});
    document.getElementById('hide-all-players').addEventListener('click', () => {{
      rows.forEach((row) => setVisible(row.dataset.id, false));
    }});

    updateVisibleCount();
  </script>
{nav_js}
</body>
</html>"""
    out_path = paths.viz_output / "pca_map.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
