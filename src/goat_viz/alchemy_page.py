from __future__ import annotations

import json
from pathlib import Path

from .alchemy_math import build_math_modal_html
from .alchemy_js import page_animation_js, page_client_js
from .io import VizArtifacts, VizPaths
from .site_shell import SITE_EMBED_HEAD, SITE_NAV_MESSAGE_JS
from .scene_shared import (
    build_players_payload,
    cumulative_3d_pct,
    embed_scene_theme,
    grid_and_origin_js,
    load_alchemy_meta,
    orb_factory_js,
    render_loop_js,
    resize_handler_js,
    scene_bootstrap_js,
    three_importmap_html,
    three_module_imports_js,
)


def _build_alchemy_html(
    *,
    scene: dict,
    disclaimer: str,
    cumulative_3d: float,
    vector_dim: int,
    pca_core_dim: int,
    alpha_default: float,
    players: list,
    alchemy_meta: dict,
    core_columns: list[str],
    alchemy_columns: list[str],
) -> str:
    payload = json.dumps(players)
    disclaimer_json = json.dumps(disclaimer)
    alchemy_json = json.dumps(alchemy_meta)
    page_block = page_client_js(alchemy_json)
    animation_block = page_animation_js()
    math_modal = build_math_modal_html(
        vector_dim=vector_dim,
        pca_core_dim=pca_core_dim,
        cumulative_3d=cumulative_3d,
        alpha_default=alpha_default,
        core_columns=core_columns,
        alchemy_columns=alchemy_columns,
    )
    embed_head = SITE_EMBED_HEAD
    nav_js = SITE_NAV_MESSAGE_JS

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GOAT Alchemy Lab</title>
{embed_head}
  <style>
    html, body {{
      margin: 0; width: 100%; height: 100%; overflow: hidden;
      background: {scene["background"]}; color: {scene["text"]};
      font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    #app {{ display: grid; grid-template-rows: auto minmax(0, 1fr); width: 100%; height: 100%; }}
    #chrome-top {{
      padding: 12px 20px 10px; border-bottom: 1px solid {scene["chrome_border"]};
      background: {scene["background"]}; display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;
    }}
    #chrome-top h1 {{ margin: 0; font-size: 1.05rem; font-weight: 600; }}
    #chrome-top .subtitle {{ margin: 4px 0 0; font-size: 0.78rem; color: {scene["muted"]}; }}
    #chrome-top a {{ color: {scene["accent"]}; font-size: 0.82rem; text-decoration: none; }}
    .chrome-actions {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
    #main {{
      display: grid;
      grid-template-columns: var(--left-sidebar-width, 260px) 5px minmax(0, 1fr) 5px var(--right-sidebar-width, 320px);
      min-height: 0;
    }}
    #controls, #math-panel, #result-panel {{ background: {scene["background"]}; overflow-y: auto; min-height: 0; padding: 14px; }}
    #controls {{ min-width: 0; }}
    #side-panel {{ display: flex; flex-direction: column; min-height: 0; min-width: 0; }}
    .resize-handle {{
      cursor: col-resize; min-height: 0; position: relative; z-index: 2; touch-action: none;
    }}
    .resize-handle::after {{
      content: ''; position: absolute; top: 0; bottom: 0; left: 50%; width: 1px;
      transform: translateX(-50%); background: {scene["chrome_border"]};
    }}
    .resize-handle:hover::after, .resize-handle.dragging::after {{
      width: 3px; background: {scene["accent"]};
    }}
    .sidebar-section {{ margin-bottom: 20px; padding-bottom: 18px; border-bottom: 1px solid {scene["chrome_border"]}; }}
    .sidebar-section:last-child {{ margin-bottom: 0; padding-bottom: 0; border-bottom: 0; }}
    .sidebar-heading {{ margin: 0 0 12px; font-size: 0.88rem; font-weight: 600; }}
    #viewport {{ position: relative; min-height: 0; overflow: hidden; background: {scene["background"]}; }}
    #viewport canvas {{ display: block; width: 100%; height: 100%; }}
    .control-block {{ margin-bottom: 16px; }}
    .control-block h3 {{ margin: 0 0 8px; font-size: 0.86rem; }}
    .control-block input[type="search"] {{
      width: 100%; box-sizing: border-box; margin-bottom: 6px; padding: 7px 10px; border-radius: 8px;
      border: 1px solid #484f58; background: #21262d; color: {scene["text"]}; font-size: 0.8rem;
    }}
    .explore-actions {{ display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }}
    .explore-feature, .reset-btn, #blend-button {{
      width: 100%; box-sizing: border-box; padding: 8px 10px; border-radius: 8px;
      border: 1px solid #484f58; background: #21262d; color: {scene["text"]};
      font-size: 0.78rem; cursor: pointer; text-align: left;
    }}
    .explore-feature:hover, .reset-btn:hover, #blend-button:hover {{
      border-color: {scene["accent"]}; background: #30363d;
    }}
    .explore-feature.active {{
      border-color: {scene["accent"]}; background: rgba(249, 115, 22, 0.18); color: {scene["text"]}; font-weight: 600;
    }}
    #blend-button {{
      text-align: center; background: {scene["accent"]}; color: {scene["background"]}; border-color: {scene["accent"]}; font-weight: 600;
    }}
    #blend-button:hover {{ filter: brightness(1.05); background: {scene["accent"]}; }}
    .picker-list {{ max-height: 140px; overflow-y: auto; border: 1px solid {scene["chrome_border"]}; border-radius: 8px; padding: 4px; }}
    .picker-option {{
      display: block; width: 100%; text-align: left; padding: 6px 8px; border: 0; border-radius: 6px;
      background: transparent; color: {scene["text"]}; font-size: 0.78rem; cursor: pointer;
    }}
    .picker-option:hover {{ background: rgba(249, 115, 22, 0.12); }}
    .picker-option.selected {{ background: {scene["accent"]}; color: {scene["background"]}; font-weight: 600; }}
    .alpha-row {{ display: flex; align-items: center; gap: 10px; font-size: 0.82rem; }}
    .alpha-row input[type="range"] {{ flex: 1; accent-color: {scene["accent"]}; }}
    .skip-row {{ display: flex; align-items: center; gap: 8px; font-size: 0.8rem; margin: 10px 0; }}

    #math-panel details {{ border: 1px solid {scene["chrome_border"]}; border-radius: 8px; padding: 10px 12px; margin-bottom: 14px; }}
    #math-panel summary {{ cursor: pointer; font-weight: 600; font-size: 0.86rem; }}
    .formula {{ margin: 10px 0 0; font-family: "Iowan Old Style", "Palatino Linotype", serif; font-size: 1rem; line-height: 1.6; }}
    .formula-note {{ margin: 8px 0 0; font-size: 0.78rem; color: {scene["muted"]}; line-height: 1.45; }}
    #result-panel h2 {{ margin: 0 0 8px; font-size: 1rem; }}
    #result-panel .muted {{ color: {scene["muted"]}; font-size: 0.78rem; line-height: 1.45; }}
    .partial-badge {{
      display: inline-block; margin: 6px 0 10px; padding: 4px 8px; border-radius: 999px;
      background: rgba(251, 191, 36, 0.15); border: 1px solid rgba(251, 191, 36, 0.55); color: #fbbf24;
      font-size: 0.74rem; font-weight: 600;
    }}
    .discovery-label {{ margin: 0 0 8px; font-size: 0.9rem; line-height: 1.4; }}
    .geom-note {{ margin: 0 0 8px; font-size: 0.76rem; color: {scene["muted"]}; line-height: 1.4; }}
    .zone-section {{ margin: 12px 0; }}
    .zone-section h3 {{ margin: 0 0 8px; font-size: 0.82rem; font-weight: 600; }}
    .zone-charts {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }}
    .zone-col {{ min-width: 0; }}
    .zone-title {{ font-size: 0.68rem; color: {scene["muted"]}; margin-bottom: 4px; text-align: center; }}
    .zone-bar {{ display: flex; height: 52px; border-radius: 6px; overflow: hidden; border: 1px solid {scene["chrome_border"]}; }}
    .zone-seg {{ display: block; height: 100%; min-width: 2px; }}
    .zone-0 {{ background: #ef4444; }}
    .zone-1 {{ background: #f97316; }}
    .zone-2 {{ background: #eab308; }}
    .zone-3 {{ background: #84cc16; }}
    .zone-4 {{ background: #22c55e; }}
    .zone-5 {{ background: #14b8a6; }}
    .zone-empty {{ font-size: 0.68rem; margin: 0; text-align: center; }}
    #math-explain-button, .math-explain-button {{
      padding: 7px 12px; border-radius: 8px; border: 1px solid #484f58;
      background: #21262d; color: {scene["text"]}; font-size: 0.78rem; font-weight: 600; cursor: pointer;
    }}
    #math-explain-button:hover, .math-explain-button:hover {{
      border-color: {scene["accent"]}; background: #30363d;
    }}
    .math-modal {{ position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; padding: 20px; }}
    .math-modal[hidden] {{ display: none !important; }}
    .math-modal-backdrop {{ position: absolute; inset: 0; background: rgba(1, 4, 9, 0.72); }}
    .math-modal-panel {{
      position: relative; width: min(720px, 100%); max-height: min(88vh, 900px);
      background: #161b22; border: 1px solid {scene["chrome_border"]}; border-radius: 12px;
      display: flex; flex-direction: column; box-shadow: 0 16px 48px rgba(0, 0, 0, 0.45);
    }}
    .math-modal-header {{
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
      padding: 14px 16px; border-bottom: 1px solid {scene["chrome_border"]};
    }}
    .math-modal-header h2 {{ margin: 0; font-size: 1rem; font-weight: 600; }}
    .math-modal-close {{
      border: 1px solid #484f58; background: #21262d; color: {scene["text"]};
      width: 32px; height: 32px; border-radius: 8px; font-size: 1.2rem; line-height: 1; cursor: pointer;
    }}
    .math-modal-close:hover {{ border-color: {scene["accent"]}; }}
    .math-modal-body {{ overflow-y: auto; padding: 16px 18px 20px; font-size: 0.82rem; line-height: 1.55; }}
    .math-section {{ margin-bottom: 18px; }}
    .math-section h3 {{ margin: 0 0 8px; font-size: 0.9rem; font-weight: 600; }}
    .math-section p {{ margin: 0 0 8px; color: {scene["text"]}; }}
    .math-note {{ color: {scene["muted"]} !important; font-size: 0.78rem !important; }}
    .math-formula-block {{
      margin: 8px 0; padding: 10px 12px; border-radius: 8px;
      background: #0d1117; border: 1px solid {scene["chrome_border"]};
      font-family: "Iowan Old Style", "Palatino Linotype", serif; font-size: 0.95rem;
    }}
    .math-table {{ width: 100%; border-collapse: collapse; font-size: 0.78rem; margin: 8px 0; }}
    .math-table th, .math-table td {{ border: 1px solid {scene["chrome_border"]}; padding: 6px 8px; text-align: left; }}
    .math-table th {{ background: #21262d; }}
    .math-col-list {{ margin: 6px 0 10px; padding-left: 1.2rem; font-size: 0.76rem; }}
    .math-col-list code {{ color: {scene["accent"]}; }}
    .math-steps {{ margin: 8px 0 0; padding-left: 1.2rem; }}
    .math-worked-section {{ border-top: 1px solid {scene["chrome_border"]}; padding-top: 14px; }}
    .math-worked-table {{ width: 100%; border-collapse: collapse; font-size: 0.74rem; margin: 10px 0; }}
    .math-worked-table th, .math-worked-table td {{ border: 1px solid {scene["chrome_border"]}; padding: 5px 6px; text-align: right; }}
    .math-worked-table th:first-child, .math-worked-table td:first-child {{ text-align: left; }}
    .math-worked-table th {{ background: #21262d; }}
    .math-worked-summary {{ margin: 8px 0 0; font-size: 0.78rem; color: {scene["muted"]}; }}
  </style>
</head>
<body>
  <div id="app">
    <header id="chrome-top">
      <div>
        <h1>⚗ Alchemy Lab</h1>
        <p class="subtitle">Orb positions = PCA({pca_core_dim}-dim core, {cumulative_3d:.1f}% variance) · NN distance = L2 in R^{vector_dim}</p>
      </div>
      <div class="chrome-actions">
        <button type="button" id="math-explain-button">Math explanation</button>
        <nav class="top-nav site-chrome"></nav>
      </div>
    </header>
    <div id="main">
      <aside id="controls">
        <section id="panel-blend" class="sidebar-section">
          <h2 class="sidebar-heading">Blend</h2>
          <div class="control-block"><h3>Player A</h3><input id="player-a-filter" type="search" placeholder="Search Player A..." /><div id="player-a-list" class="picker-list"></div></div>
          <div class="control-block"><h3>Player B</h3><input id="player-b-filter" type="search" placeholder="Search Player B..." /><div id="player-b-list" class="picker-list"></div></div>
          <div class="control-block"><h3>Blend weight α</h3><div class="alpha-row"><span>0</span><input id="alpha-slider" type="range" min="0" max="1" step="0.01" value="{alpha_default}" /><span>1</span><strong id="alpha-value">{alpha_default:.2f}</strong></div></div>
          <label class="skip-row"><input id="skip-animation" type="checkbox" /> Skip animation (snap to result)</label>
          <button type="button" id="blend-button">Blend ⚗</button>
        </section>
        <section id="panel-explore" class="sidebar-section">
          <h2 class="sidebar-heading">Explore features</h2>
          <p class="muted" style="margin:0 0 10px;font-size:0.78rem;">Pick a feature to read about. Toggle “All players” to switch between full PCA view and your last blend trio.</p>
          <div class="explore-actions">
            <button type="button" class="explore-feature active" data-feature="all">All players (PCA view)</button>
            <button type="button" class="explore-feature" data-feature="showman">Showman / excitement</button>
            <button type="button" class="explore-feature" data-feature="zones">Favorite scoring spots</button>
            <button type="button" class="explore-feature" data-feature="impact">Impact (crown metric)</button>
          </div>
          <div id="explore-body"></div>
        </section>
        <section id="panel-math" class="sidebar-section">
          <h2 class="sidebar-heading">Math</h2>
          <div id="math-panel">
            <p class="formula">C(u, v) = α·u + (1−α)·v &nbsp; in &nbsp; ℝ<sup>{vector_dim}</sup></p>
            <p class="formula-note">α = <span class="alpha-live">{alpha_default:.2f}</span>, (1−α) = <span class="beta-live">{1 - alpha_default:.2f}</span>. Discovery = L2 nearest neighbor in ℝ<sup>{vector_dim}</sup>.</p>
            <button type="button" class="math-explain-button" data-math-open>How the algorithm works</button>
          </div>
        </section>
      </aside>
      <div id="resize-left" class="resize-handle" role="separator" aria-orientation="vertical" aria-label="Resize left sidebar" title="Drag to resize"></div>
      <div id="viewport"></div>
      <div id="resize-right" class="resize-handle" role="separator" aria-orientation="vertical" aria-label="Resize right sidebar" title="Drag to resize"></div>
      <aside id="side-panel">
        <div id="result-panel"><p class="muted">All players visible. Pick A + B, then blend to focus on A, B, and the nearest match.</p></div>
      </aside>
    </div>
  </div>
{math_modal}
{three_importmap_html()}
{nav_js}
  <script type="module">
{three_module_imports_js()}
    const sceneTheme = {json.dumps(scene)};
    const players = {payload};
    const showOriginLines = true;
{page_block}
{scene_bootstrap_js()}
{grid_and_origin_js()}
{orb_factory_js()}
{resize_handler_js()}
{animation_block}
{render_loop_js()}
    buildAllOrbs(players, {{ withSpokes: showOriginLines }}).then(() => animate()).catch((error) => {{
      console.error('Failed to load player textures', error);
      animate();
    }});
  </script>
</body>
</html>
"""


def render_alchemy_html(paths: VizPaths, artifacts: VizArtifacts) -> Path:
    config = artifacts.config
    alchemy_page_cfg = config.get("alchemy_page", {})
    if not alchemy_page_cfg.get("enabled", True):
        raise ValueError("alchemy_page is disabled in config/viz.yaml")

    scene = embed_scene_theme(config)
    disclaimer = config.get("captions", {}).get("exploratory_disclaimer", "")
    alchemy_meta = load_alchemy_meta(paths)
    alpha_default = float(alchemy_meta.get("alpha_default", 0.5))
    vector_dim = int(alchemy_meta.get("vector_dim", 18))
    pca_core_dim = int(alchemy_meta.get("pca_core_dim", 11))
    cumulative_3d = cumulative_3d_pct(artifacts.pca_explained_variance)
    players = build_players_payload(paths, artifacts, scene=scene)

    core_columns = list(alchemy_meta.get("core_feature_columns") or [])
    alchemy_columns = list(alchemy_meta.get("alchemy_feature_columns") or [])
    html = _build_alchemy_html(
        scene=scene,
        disclaimer=disclaimer,
        cumulative_3d=cumulative_3d,
        vector_dim=vector_dim,
        pca_core_dim=pca_core_dim,
        alpha_default=alpha_default,
        players=players,
        alchemy_meta=alchemy_meta,
        core_columns=core_columns,
        alchemy_columns=alchemy_columns,
    )
    out_path = paths.viz_output / "alchemy.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
