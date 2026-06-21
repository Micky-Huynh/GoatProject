from __future__ import annotations

import base64
import re
import unicodedata
import yaml
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Circle

from .io import VizArtifacts, VizPaths
from .alchemy_js import click_js, client_js
from .profiles import compute_player_profiles




def _normalize_display_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def _default_viz_player_ids(paths: VizPaths, merged: pd.DataFrame) -> set[str]:
    allowlist_path = paths.goat_root / "config" / "allowlist.yaml"
    if not allowlist_path.exists():
        top = merged.sort_values("rank_pca_whitened_l2").head(21)
        return set(top["player_id"].astype(str))

    cfg = yaml.safe_load(allowlist_path.read_text(encoding="utf-8"))
    wanted = {_normalize_display_name(entry["name"]) for entry in cfg.get("default_viz_players", [])}
    ids = {
        str(row.player_id)
        for row in merged.itertuples(index=False)
        if _normalize_display_name(str(row.display_name)) in wanted
    }
    if ids:
        return ids
    top = merged.sort_values("rank_pca_whitened_l2").head(21)
    return set(top["player_id"].astype(str))

def _theme(config: dict[str, Any]) -> dict[str, str]:
    theme = config.get("theme", {})
    return {
        "background": theme.get("background", "#0d1117"),
        "text": theme.get("text", "#e6edf3"),
        "accent": theme.get("accent", "#f97316"),
    }


def _embed_scene_theme(config: dict[str, Any]) -> dict[str, str]:
    embed_cfg = config.get("embed_3d", {})
    scene = embed_cfg.get("scene", {})
    style = embed_cfg.get("scene_style", "dark")
    if style == "desmos":
        defaults = {
            "background": "#ffffff",
            "text": "#2f3437",
            "muted": "#6b7280",
            "accent": "#2d70b3",
            "grid_major": "#c8c8c8",
            "grid_minor": "#e8e8e8",
            "axis": "#8a8a8a",
            "box": "#d4d4d4",
            "spoke": "#b8bcc2",
            "chrome_border": "#e5e7eb",
            "tooltip_bg": "#ffffff",
            "tooltip_border": "#d1d5db",
            "layout": "desmos",
        }
    else:
        theme = _theme(config)
        defaults = {
            "background": theme["background"],
            "text": theme["text"],
            "muted": "rgba(230, 237, 243, 0.75)",
            "accent": theme["accent"],
            "grid_major": theme["accent"],
            "grid_minor": "#30363d",
            "axis": theme["text"],
            "box": "#30363d",
            "spoke": theme["text"],
            "chrome_border": "#30363d",
            "tooltip_bg": "rgba(22, 27, 34, 0.96)",
            "tooltip_border": "#30363d",
            "layout": "classic",
        }
    return {**defaults, **scene}


def _variance_pct(pca_explained_variance: dict[str, Any], component: str) -> float:
    for row in pca_explained_variance.get("components", []):
        if row.get("component") == component:
            return float(row.get("explained_variance_ratio", 0.0)) * 100.0
    return 0.0


def _cumulative_3d_pct(pca_explained_variance: dict[str, Any]) -> float:
    return sum(_variance_pct(pca_explained_variance, name) for name in ("PC1", "PC2", "PC3"))


def _origin_inclusive_axis_range(values: pd.Series, pad_ratio: float = 0.14) -> tuple[float, float]:
    vmin = float(values.min())
    vmax = float(values.max())
    lo = min(0.0, vmin)
    hi = max(0.0, vmax)
    span = max(hi - lo, 1e-6)
    pad = span * pad_ratio
    return lo - pad, hi + pad


def _map_axis(value: float, lo: float, hi: float) -> float:
    span = max(hi - lo, 1e-6)
    return ((value - lo) / span) * 2.0 - 1.0


def _merge_coords_and_rankings(artifacts: VizArtifacts) -> pd.DataFrame:
    coords = artifacts.pca_coordinates.copy()
    rankings = artifacts.rankings.copy()
    rank_cols = [
        "player_id",
        "score_l2",
        "score_mahalanobis",
        "score_pca_whitened_l2",
        "rank_l2",
        "rank_mahalanobis",
        "rank_pca_whitened_l2",
        "championships",
        "playoff_seasons",
        "playoff_performance",
        "stat_outlier_z",
        "team_strength_index",
        "clutch_penalty",
        "score_goat_index",
    ]
    rank_cols = [c for c in rank_cols if c in rankings.columns]
    merged = coords.merge(rankings[rank_cols], on="player_id", how="left")
    if "rank_pca_whitened_l2" not in merged.columns:
        merged["rank_pca_whitened_l2"] = merged["score_pca_whitened_l2"].rank(
            method="min", ascending=True
        ).astype(int)
    return merged.sort_values("rank_pca_whitened_l2")


def _initials(display_name: str) -> str:
    parts = display_name.replace(".", "").split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _write_fallback_headshot(path: Path, display_name: str, scene: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(2, 2), dpi=120)
    fig.patch.set_facecolor(scene["background"])
    ax.set_facecolor(scene["background"])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    circle = Circle((0.5, 0.5), 0.42, facecolor=scene["accent"], edgecolor=scene["text"], linewidth=2)
    ax.add_patch(circle)
    ax.text(
        0.5,
        0.5,
        _initials(display_name),
        ha="center",
        va="center",
        fontsize=28,
        fontweight="bold",
        color=scene["background"],
    )
    fig.savefig(path, bbox_inches="tight", pad_inches=0.02, facecolor=scene["background"])
    plt.close(fig)


def _download_headshot(url: str, dest: Path) -> bool:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GoatProject-viz/1.0 (local stat-space explorer)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
    if len(payload) < 800 or not payload.startswith(b"\xff\xd8") and not payload.startswith(b"\x89PNG"):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(payload)
    return True


def _ensure_player_image(
    paths: VizPaths,
    player_id: str,
    display_name: str,
    scene: dict[str, str],
    image_cfg: dict[str, Any],
) -> Path:
    cache_dir = paths.viz_output / image_cfg.get("cache_dir", "assets/players")
    dest = cache_dir / f"{player_id}.jpg"
    if dest.exists() and dest.stat().st_size > 800:
        return dest

    url_template = image_cfg.get(
        "url_template",
        "https://www.basketball-reference.com/req/202106291/images/players/{player_id}.jpg",
    )
    url = url_template.format(player_id=player_id)
    if not _download_headshot(url, dest):
        _write_fallback_headshot(dest, display_name, scene)
    return dest


def _image_to_data_url(path: Path) -> str:
    payload = path.read_bytes()
    mime = "image/png" if payload.startswith(b"\x89PNG") else "image/jpeg"
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _build_threejs_html(
    *,
    scene: dict[str, str],
    disclaimer: str,
    cumulative_3d: float,
    pc1_pct: float,
    pc2_pct: float,
    pc3_pct: float,
    players: list[dict[str, Any]],
    show_origin_lines: bool,
    pool_size: int,
    default_count: int,
    alchemy_meta: dict[str, Any] | None = None,
) -> str:
    payload = json.dumps(players)
    disclaimer_json = json.dumps(disclaimer)
    alchemy_json = json.dumps(alchemy_meta or {})
    alchemy_block = client_js(alchemy_json)
    alchemy_click = click_js()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GOAT 3D Stat-Space Explorer</title>
  <style>
    html, body {{
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: {scene["background"]};
      color: {scene["text"]};
      font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    #app {{
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      width: 100%;
      height: 100%;
    }}
    #chrome-top {{
      padding: 12px 20px 10px;
      border-bottom: 1px solid {scene["chrome_border"]};
      background: {scene["background"]};
      text-align: center;
      pointer-events: none;
    }}
    #chrome-top h1 {{
      margin: 0;
      font-size: 1.05rem;
      font-weight: 600;
      line-height: 1.3;
    }}
    #chrome-top .subtitle {{
      margin: 5px 0 0;
      font-size: 0.8rem;
      color: {scene["muted"]};
      line-height: 1.45;
      max-width: min(92vw, 880px);
      margin-inline: auto;
    }}
    #viewport {{
      position: relative;
      min-height: 0;
      overflow: hidden;
      background: {scene["background"]};
    }}
    #main {{
      display: grid;
      grid-template-columns: min(240px, 28vw) minmax(0, 1fr) min(300px, 30vw);
      min-height: 0;
    }}
    #player-picker {{
      border-right: 1px solid {scene["chrome_border"]};
      background: {scene["background"]};
      padding: 12px 12px 10px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}
    #player-picker .picker-header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 8px;
      margin-bottom: 8px;
      font-size: 0.82rem;
    }}
    #selection-count {{
      color: {scene["muted"]};
      font-size: 0.76rem;
    }}
    #player-filter {{
      width: 100%;
      box-sizing: border-box;
      margin-bottom: 8px;
      padding: 7px 10px;
      border-radius: 8px;
      border: 1px solid {scene["chrome_border"]};
      background: {scene["background"]};
      color: {scene["text"]};
      font-size: 0.8rem;
    }}
    .picker-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 8px;
    }}
    .picker-actions button {{
      flex: 1 1 auto;
      padding: 5px 8px;
      border-radius: 8px;
      border: 1px solid {scene["chrome_border"]};
      background: {scene["background"]};
      color: {scene["text"]};
      font-size: 0.74rem;
      cursor: pointer;
    }}
    #player-list {{
      overflow-y: auto;
      min-height: 0;
      padding-right: 2px;
    }}
    .player-option {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 2px;
      font-size: 0.78rem;
      color: {scene["text"]};
    }}
    .player-option input {{
      accent-color: {scene["accent"]};
    }}
    #profile-panel {{
      pointer-events: none;
    }}
    #profile-panel {{
      border-left: 1px solid {scene["chrome_border"]};
      background: {scene["background"]};
      padding: 14px 16px;
      overflow-y: auto;
    }}
    .profile-card h2 {{
      margin: 0 0 6px;
      font-size: 1.05rem;
      line-height: 1.25;
    }}
    .profile-card .profile-rank {{
      margin: 0 0 12px;
      color: {scene["muted"]};
      font-size: 0.8rem;
    }}
    .crown-badge {{
      display: inline-block;
      margin-bottom: 8px;
      padding: 4px 8px;
      border-radius: 999px;
      background: rgba(251, 191, 36, 0.18);
      border: 1px solid rgba(251, 191, 36, 0.55);
      color: #fbbf24;
      font-size: 0.78rem;
      font-weight: 600;
    }}
    .profile-card.is-crowned h2 {{
      color: #fbbf24;
    }}
    .aspect-row {{
      margin-bottom: 10px;
    }}
    .aspect-head {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 0.78rem;
      color: {scene["muted"]};
      margin-bottom: 4px;
    }}
    .aspect-track {{
      height: 8px;
      border-radius: 999px;
      background: rgba(139, 148, 158, 0.25);
      overflow: hidden;
    }}
    .aspect-fill {{
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, {scene["accent"]}, #fbbf24);
    }}
    .profile-empty {{
      color: {scene["muted"]};
      font-size: 0.82rem;
      line-height: 1.5;
    }}
    .legend-chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-right: 12px;
    }}
    .legend-dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: #fbbf24;
      box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.35);
    }}
    #viewport canvas {{
      display: block;
      width: 100%;
      height: 100%;
    }}
    #chrome-bottom {{
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 8px 20px 10px;
      border-top: 1px solid {scene["chrome_border"]};
      background: {scene["background"]};
      pointer-events: none;
    }}
    #hint {{
      font-size: 0.78rem;
      color: {scene["muted"]};
      text-align: center;
    }}
    #disclaimer {{
      margin: 0;
      font-size: 0.72rem;
      color: {scene["muted"]};
      text-align: center;
      line-height: 1.4;
      max-width: min(92vw, 880px);
      margin-inline: auto;
    }}
    #alchemy-toggle {{
      margin-top: 8px;
      width: 100%;
      padding: 8px 10px;
      border-radius: 8px;
      border: 1px solid {scene["chrome_border"]};
      background: rgba(249, 115, 22, 0.12);
      color: {scene["text"]};
      cursor: pointer;
      font-size: 0.8rem;
    }}
    #alchemy-toggle.active {{
      background: {scene["accent"]};
      color: {scene["background"]};
      font-weight: 600;
    }}
    .alchemy-pick {{
      outline: 2px solid #fbbf24;
      outline-offset: 2px;
    }}
    .alchemy-result {{
      margin-top: 10px;
      padding: 10px;
      border-radius: 8px;
      border: 1px solid {scene["chrome_border"]};
      background: rgba(249, 115, 22, 0.08);
      font-size: 0.82rem;
      line-height: 1.45;
    }}
      position: fixed;
      display: none;
      z-index: 20;
      padding: 10px 12px;
      border-radius: 8px;
      background: {scene["tooltip_bg"]};
      border: 1px solid {scene["tooltip_border"]};
      color: {scene["text"]};
      font-size: 0.85rem;
      line-height: 1.45;
      pointer-events: none;
      max-width: min(260px, calc(100vw - 24px));
      box-shadow: 0 8px 24px rgba(0,0,0,0.35);
    }}
  </style>
</head>
<body>
  <div id="app">
    <header id="chrome-top">
      <h1>Top-{pool_size} stat-space embedding (3D PCA)</h1>
      <p class="subtitle">PC1–PC3 retain {cumulative_3d:.1f}% of variance · photo orbs · size = overall impact (BPM/VORP/PER/WS z-avg)</p>
    </header>
    <div id="main">
      <aside id="player-picker">
        <div class="picker-header">
          <strong>Visible players</strong>
          <span id="selection-count"></span>
        </div>
        <input id="player-filter" type="search" placeholder="Filter players..." />
        <div class="picker-actions">
          <button type="button" id="reset-default">Default {default_count}</button>
          <button type="button" id="select-all">All</button>
          <button type="button" id="clear-all">None</button>
        </div>
        <button type="button" id="alchemy-toggle">⚗ Alchemy mode (pick 2 orbs)</button>
        <div id="player-list"></div>
      </aside>
      <div id="viewport"></div>
      <aside id="profile-panel" aria-live="polite"></aside>
    </div>
    <footer id="chrome-bottom">
      <div id="hint" title="Clutch adj penalizes players whose BPM/VORP/PER/WS z-scores exceed their playoff performance + MVP/All-NBA consensus."><span class="legend-chip"><span class="legend-dot"></span>Gold crown = #1 impact among visible players</span>Drag to rotate · scroll to zoom · Alchemy: toggle ⚗ then click two orbs</div>
      <p id="disclaimer"></p>
    </footer>
    <div id="tooltip"></div>
  </div>
  <script type="importmap">
    {{
      "imports": {{
        "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
        "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"
      }}
    }}
  </script>
  <script type="module">
    import * as THREE from 'three';
    import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';

    const sceneTheme = {json.dumps(scene)};
    const players = {payload};

{alchemy_block}
    const showOriginLines = {json.dumps(show_origin_lines)};
    const axisLabels = {{
      x: 'PC1 ({pc1_pct:.1f}%)',
      y: 'PC2 ({pc2_pct:.1f}%)',
      z: 'PC3 ({pc3_pct:.1f}%)',
    }};

    document.getElementById('disclaimer').textContent = {disclaimer_json};

    const viewport = document.getElementById('viewport');
    const chromeTop = document.getElementById('chrome-top');
    const chromeBottom = document.getElementById('chrome-bottom');
    const tooltip = document.getElementById('tooltip');

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(sceneTheme.background);

    const camera = new THREE.PerspectiveCamera(48, 1, 0.05, 100);
    camera.position.set(2.6, 1.9, 2.5);

    const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: false }});
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    viewport.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(0, 0, 0);
    controls.maxDistance = 8;
    controls.minDistance = 1.2;

    function resizeRenderer() {{
      const width = viewport.clientWidth;
      const height = viewport.clientHeight;
      if (width <= 0 || height <= 0) return;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    }}

    function addAxisLine(direction, color, length = 1.25) {{
      const points = [new THREE.Vector3(0, 0, 0), direction.clone().multiplyScalar(length)];
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const material = new THREE.LineBasicMaterial({{ color, transparent: true, opacity: 0.85 }});
      scene.add(new THREE.Line(geometry, material));
    }}

    if (sceneTheme.layout === 'desmos') {{
      const grid = new THREE.GridHelper(2.4, 12, sceneTheme.grid_major, sceneTheme.grid_minor);
      grid.position.y = -1.05;
      scene.add(grid);

      addAxisLine(new THREE.Vector3(1, 0, 0), sceneTheme.axis);
      addAxisLine(new THREE.Vector3(0, 1, 0), sceneTheme.axis);
      addAxisLine(new THREE.Vector3(0, 0, 1), sceneTheme.axis);

      const boxSize = 2.4;
      const boxGeometry = new THREE.BoxGeometry(boxSize, boxSize, boxSize);
      const boxEdges = new THREE.EdgesGeometry(boxGeometry);
      const boxLines = new THREE.LineSegments(
        boxEdges,
        new THREE.LineBasicMaterial({{ color: sceneTheme.box, transparent: true, opacity: 0.55 }}),
      );
      boxLines.position.y = -0.05;
      scene.add(boxLines);
    }} else {{
      const grid = new THREE.GridHelper(2.2, 10, sceneTheme.grid_major, sceneTheme.grid_minor);
      grid.position.y = -1.02;
      scene.add(grid);

      const axes = new THREE.AxesHelper(1.15);
      axes.material.transparent = true;
      axes.material.opacity = 0.55;
      scene.add(axes);
    }}

    const originMarker = new THREE.Mesh(
      new THREE.SphereGeometry(0.035, 16, 16),
      new THREE.MeshBasicMaterial({{ color: sceneTheme.accent }}),
    );
    scene.add(originMarker);

    const orbMeshes = [];
    const orbGroups = new Map();
    const spokeOpacity = sceneTheme.layout === 'desmos' ? 0.35 : 0.22;
    const lineMaterial = new THREE.LineBasicMaterial({{
      color: new THREE.Color(sceneTheme.spoke),
      transparent: true,
      opacity: spokeOpacity,
    }});

    const textureLoader = new THREE.TextureLoader();
    const profilePanel = document.getElementById('profile-panel');
    const playerList = document.getElementById('player-list');
    const selectionCount = document.getElementById('selection-count');
    const playerFilter = document.getElementById('player-filter');

    const selectedIds = new Set(
      players.filter((player) => player.selected_default).map((player) => player.id),
    );
    let pinnedPlayer = null;

    function visiblePlayers() {{
      return players.filter((player) => selectedIds.has(player.id));
    }}

    function cohortImpactLeader() {{
      const visible = visiblePlayers();
      if (visible.length === 0) return null;
      return visible.reduce((best, player) => (
        player.impact_z > best.impact_z ? player : best
      ));
    }}

    function isCohortImpactLeader(player) {{
      const leader = cohortImpactLeader();
      return Boolean(leader && leader.id === player.id);
    }}

    function cohortImpactRank(player) {{
      const visible = visiblePlayers();
      if (visible.length === 0) return null;
      const sorted = visible.slice().sort((a, b) => b.impact_z - a.impact_z);
      const index = sorted.findIndex((entry) => entry.id === player.id);
      return index >= 0 ? index + 1 : null;
    }}

    function defaultBestPlayer() {{
      return cohortImpactLeader();
    }}

    function aspectsForVisible(player) {{
      const visible = visiblePlayers();
      if (!player.aspects || visible.length === 0) return [];
      return player.aspects.map((aspect) => {{
        const values = visible.map((entry) => {{
          const match = entry.aspects.find((row) => row.key === aspect.key);
          return match ? match.z_avg : 0;
        }});
        const minVal = Math.min(...values);
        const maxVal = Math.max(...values);
        const span = Math.max(maxVal - minVal, 1e-9);
        const score = ((aspect.z_avg - minVal) / span) * 100;
        const rank = [...visible]
          .sort((a, b) => {{
            const az = a.aspects.find((row) => row.key === aspect.key)?.z_avg ?? 0;
            const bz = b.aspects.find((row) => row.key === aspect.key)?.z_avg ?? 0;
            return bz - az;
          }})
          .findIndex((entry) => entry.id === player.id) + 1;
        return {{
          ...aspect,
          score: Math.round(score * 10) / 10,
          rank,
        }};
      }});
    }}

    function renderAspectRows(aspects, cohortSize) {{
      if (!aspects || aspects.length === 0) {{
        return '<p class="profile-empty">Skill aspect data unavailable.</p>';
      }}
      return aspects.map((aspect) => `
        <div class="aspect-row">
          <div class="aspect-head">
            <span>${{aspect.label}}</span>
            <span>#${{aspect.rank}} of ${{cohortSize}}</span>
          </div>
          <div class="aspect-track">
            <div class="aspect-fill" style="width:${{aspect.score}}%"></div>
          </div>
        </div>
      `).join('');
    }}

    function renderProfilePanel(player) {{
      if (!player) {{
        profilePanel.innerHTML = '<p class="profile-empty">Select players on the left, then hover an orb for playmaking, defense, scoring, and overall impact within the visible cohort.</p>';
        return;
      }}
      const cohortSize = visiblePlayers().length;
      const cohortRank = cohortImpactRank(player);
      const crowned = isCohortImpactLeader(player);
      const bestBadge = crowned ? '<div class="crown-badge">👑 #1 overall impact (visible)</div>' : '';
      profilePanel.innerHTML = `
        <div class="profile-card ${{crowned ? 'is-crowned' : ''}}">
          ${{bestBadge}}
          <h2>${{player.name}}</h2>
          <p class="profile-rank">Impact #${{cohortRank}} of ${{cohortSize}} visible · impact z ${{player.impact_z.toFixed(2)}} · all-pool #${{player.rank_impact}}</p>
          <p class="profile-meta">${{player.championships}} titles (${{player.max_consecutive_championships}}-peat max) · ${{player.playoff_seasons}} playoff yrs · perf ${{player.playoff_performance.toFixed(2)}} · clutch adj +${{player.clutch_penalty.toFixed(2)}}</p>
          <p class="profile-rank">L2 #${{player.rank_l2}} · Mahalanobis #${{player.rank_mahalanobis}}</p>
          ${{renderAspectRows(aspectsForVisible(player), cohortSize)}}
        </div>
      `;
    }}

    function updateSelectionCount() {{
      selectionCount.textContent = `${{selectedIds.size}} / ${{players.length}} visible`;
    }}

    function updateCrownVisuals() {{
      const leaderId = cohortImpactLeader()?.id ?? null;
      for (const [playerId, group] of orbGroups.entries()) {{
        const showCrown = playerId === leaderId && selectedIds.has(playerId);
        group.crownMeshes.forEach((mesh) => {{ mesh.visible = showCrown; }});
      }}
    }}

    function applySelection() {{
      for (const [playerId, group] of orbGroups.entries()) {{
        const visible = selectedIds.has(playerId);
        group.meshes.forEach((mesh) => {{ mesh.visible = visible; }});
        group.spokes.forEach((mesh) => {{ mesh.visible = visible; }});
      }}
      updateCrownVisuals();
      updateSelectionCount();
      if (pinnedPlayer && !selectedIds.has(pinnedPlayer.id)) {{
        pinnedPlayer = null;
      }}
      renderProfilePanel(pinnedPlayer || defaultBestPlayer());
    }}

    function buildPlayerPicker() {{
      const sorted = players.slice().sort((a, b) => a.rank_impact - b.rank_impact);
      playerList.innerHTML = sorted.map((player) => `
        <label class="player-option" data-name="${{player.name.toLowerCase()}}">
          <input type="checkbox" value="${{player.id}}" ${{selectedIds.has(player.id) ? 'checked' : ''}} />
          <span>#${{player.rank_impact}} ${{player.name}}</span>
        </label>
      `).join('');

      playerList.querySelectorAll('input[type="checkbox"]').forEach((input) => {{
        input.addEventListener('change', () => {{
          if (input.checked) selectedIds.add(input.value);
          else selectedIds.delete(input.value);
          applySelection();
        }});
      }});

      document.getElementById('reset-default').addEventListener('click', () => {{
        selectedIds.clear();
        players.filter((player) => player.selected_default).forEach((player) => selectedIds.add(player.id));
        playerList.querySelectorAll('input[type="checkbox"]').forEach((input) => {{
          input.checked = selectedIds.has(input.value);
        }});
        applySelection();
      }});
      document.getElementById('select-all').addEventListener('click', () => {{
        players.forEach((player) => selectedIds.add(player.id));
        playerList.querySelectorAll('input[type="checkbox"]').forEach((input) => {{ input.checked = true; }});
        applySelection();
      }});
      document.getElementById('clear-all').addEventListener('click', () => {{
        selectedIds.clear();
        playerList.querySelectorAll('input[type="checkbox"]').forEach((input) => {{ input.checked = false; }});
        applySelection();
      }});
      playerFilter.addEventListener('input', () => {{
        const query = playerFilter.value.trim().toLowerCase();
        playerList.querySelectorAll('.player-option').forEach((row) => {{
          row.style.display = row.dataset.name.includes(query) ? 'flex' : 'none';
        }});
      }});
      updateSelectionCount();
    }}

    async function buildOrbs() {{
      for (const player of players) {{
        const position = new THREE.Vector3(player.x, player.y, player.z);
        const spokes = [];
        if (showOriginLines) {{
          const geometry = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(0, 0, 0),
            position.clone(),
          ]);
          const line = new THREE.Line(geometry, lineMaterial);
          scene.add(line);
          spokes.push(line);
        }}

        const texture = await textureLoader.loadAsync(player.image);
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.wrapS = THREE.ClampToEdgeWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;

        const material = new THREE.MeshBasicMaterial({{ map: texture }});
        const orb = new THREE.Mesh(new THREE.SphereGeometry(player.radius, 48, 48), material);
        orb.position.copy(position);
        orb.userData = player;
        scene.add(orb);
        const meshes = [orb];
        orbMeshes.push(orb);

        const crownMeshes = [];
        const glow = new THREE.Mesh(
          new THREE.SphereGeometry(player.radius * 1.12, 32, 32),
          new THREE.MeshBasicMaterial({{ color: 0xfbbf24, transparent: true, opacity: 0.18 }}),
        );
        glow.position.copy(position);
        glow.visible = false;
        scene.add(glow);
        crownMeshes.push(glow);

        const halo = new THREE.Mesh(
          new THREE.SphereGeometry(player.radius * 1.22, 24, 24),
          new THREE.MeshBasicMaterial({{ color: 0xfbbf24, transparent: true, opacity: 0.45, wireframe: true }}),
        );
        halo.position.copy(position);
        halo.visible = false;
        scene.add(halo);
        crownMeshes.push(halo);

        orbGroups.set(player.id, {{ player, meshes, spokes, crownMeshes }});
      }}
      buildPlayerPicker();
      applySelection();
    }}
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    function positionTooltip(clientX, clientY) {{
      tooltip.style.display = 'block';
      tooltip.style.visibility = 'hidden';
      tooltip.style.left = '0px';
      tooltip.style.top = '0px';

      const pad = 12;
      const offset = 16;
      const headerBottom = chromeTop.getBoundingClientRect().bottom;
      const footerTop = chromeBottom.getBoundingClientRect().top;
      const maxLeft = window.innerWidth - tooltip.offsetWidth - pad;
      const maxTop = footerTop - tooltip.offsetHeight - pad;
      const minTop = headerBottom + pad;

      let left = clientX + offset;
      let top = clientY + offset;

      if (left > maxLeft) left = clientX - tooltip.offsetWidth - offset;
      if (top > maxTop) top = clientY - tooltip.offsetHeight - offset;

      left = Math.max(pad, Math.min(left, maxLeft));
      top = Math.max(minTop, Math.min(top, maxTop));

      tooltip.style.left = `${{left}}px`;
      tooltip.style.top = `${{top}}px`;
      tooltip.style.visibility = 'visible';
    }}

    function showTooltip(player, clientX, clientY) {{
      const cohortRank = cohortImpactRank(player);
      const cohortSize = visiblePlayers().length;
      const crownNote = isCohortImpactLeader(player) ? '<br>👑 #1 impact (visible)' : '';
      tooltip.innerHTML = `
        <strong>${{player.name}}</strong>${{crownNote}}<br>
        Impact: z=${{player.impact_z.toFixed(2)}} (#${{cohortRank}} of ${{cohortSize}} visible · #${{player.rank_impact}} all-pool)<br>
        L2: ${{player.score_l2.toFixed(2)}} (#${{player.rank_l2}})<br>
        Mahalanobis: ${{player.score_mahalanobis.toFixed(2)}} (#${{player.rank_mahalanobis}})<br>
        PC1: ${{player.pc1.toFixed(2)}}, PC2: ${{player.pc2.toFixed(2)}}, PC3: ${{player.pc3.toFixed(2)}}
      `;
      positionTooltip(clientX, clientY);
    }}

    function onPointerMove(event) {{
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(orbMeshes);
      if (hits.length > 0) {{
        document.body.style.cursor = 'pointer';
        const active = hits[0].object.userData;
        showTooltip(active, event.clientX, event.clientY);
        pinnedPlayer = active;
        renderProfilePanel(active);
      }} else {{
        document.body.style.cursor = 'default';
        tooltip.style.display = 'none';
        pinnedPlayer = null;
        renderProfilePanel(defaultBestPlayer());
      }}
    }}


{alchemy_click}

    renderer.domElement.addEventListener('pointermove', onPointerMove);

    function onResize() {{
      resizeRenderer();
    }}
    window.addEventListener('resize', onResize);
    resizeRenderer();

    function animate() {{
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }}

    buildOrbs().then(() => animate()).catch((error) => {{
      console.error('Failed to load player textures', error);
      animate();
    }});
  </script>
</body>
</html>
"""


def render_embed_3d_html(paths: VizPaths, artifacts: VizArtifacts) -> Path:
    """Interactive 3D PCA embedding with photo-textured player orbs."""
    config = artifacts.config
    embed_cfg = config.get("embed_3d", {})
    image_cfg = config.get("player_images", {})
    scene = _embed_scene_theme(config)
    disclaimer = config.get("captions", {}).get("exploratory_disclaimer", "")

    if not embed_cfg.get("enabled", True):
        raise ValueError("embed_3d is disabled in config/viz.yaml")

    merged = _merge_coords_and_rankings(artifacts)
    for col in ("PC1", "PC2", "PC3"):
        if col not in merged.columns:
            raise ValueError(f"pca_coordinates.csv missing {col} for 3D embedding")

    pc1_pct = _variance_pct(artifacts.pca_explained_variance, "PC1")
    pc2_pct = _variance_pct(artifacts.pca_explained_variance, "PC2")
    pc3_pct = _variance_pct(artifacts.pca_explained_variance, "PC3")
    cumulative_3d = _cumulative_3d_pct(artifacts.pca_explained_variance)

    x_lo, x_hi = _origin_inclusive_axis_range(merged["PC1"])
    y_lo, y_hi = _origin_inclusive_axis_range(merged["PC2"])
    z_lo, z_hi = _origin_inclusive_axis_range(merged["PC3"])

    min_radius = float(embed_cfg.get("orb_radius_min", 0.08))
    max_radius = float(embed_cfg.get("orb_radius_max", 0.16))

    profiles = {}
    if artifacts.career_vectors is not None:
        profiles = compute_player_profiles(
            artifacts.career_vectors,
            artifacts.rankings,
            config,
        )

    size_metric = embed_cfg.get("marker_size_metric", "impact_z")
    if size_metric == "impact_z":
        size_values = merged["player_id"].map(
            lambda pid: float(profiles.get(str(pid), {}).get("impact_z", 0.0))
        ).astype(float)
    else:
        size_values = merged[size_metric].astype(float)
    size_min, size_max = float(size_values.min()), float(size_values.max())
    size_span = max(size_max - size_min, 1e-6)


    z_cols: list[str] = []
    cv_lookup = None
    if artifacts.career_vectors is not None:
        z_cols = [c for c in artifacts.career_vectors.columns if c.endswith("_z")]
        cv_lookup = artifacts.career_vectors.set_index("player_id")

    alchemy_cfg_path = paths.goat_root / "config" / "alchemy.yaml"
    alchemy_cfg = yaml.safe_load(alchemy_cfg_path.read_text(encoding="utf-8")) if alchemy_cfg_path.exists() else {}
    alchemy_meta = {
        "alpha": float(alchemy_cfg.get("blend", {}).get("alpha", 0.5)),
        "beta": float(alchemy_cfg.get("blend", {}).get("beta", 0.5)),
        "disclaimer": alchemy_cfg.get("framing", {}).get("disclaimer", ""),
        "config_hash": "local",
    }
    cache_path = paths.modeling_output / "alchemy_cache.json"
    if cache_path.exists():
        cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
        alchemy_meta["config_hash"] = cache_payload.get("config_hash", "local")

    default_viz_ids = _default_viz_player_ids(paths, merged)

    size_by_player = {
        str(pid): float(val) for pid, val in zip(merged["player_id"], size_values, strict=True)
    }

    players: list[dict[str, Any]] = []
    for row in merged.itertuples(index=False):
        pid = str(row.player_id)
        t = (size_by_player[pid] - size_min) / size_span
        radius = min_radius + t * (max_radius - min_radius)
        image_path = _ensure_player_image(
            paths,
            str(row.player_id),
            str(row.display_name),
            scene,
            image_cfg,
        )
        players.append(
            {
                "id": row.player_id,
                "name": row.display_name,
                "x": _map_axis(float(row.PC1), x_lo, x_hi),
                "y": _map_axis(float(row.PC2), y_lo, y_hi),
                "z": _map_axis(float(row.PC3), z_lo, z_hi),
                "pc1": float(row.PC1),
                "pc2": float(row.PC2),
                "pc3": float(row.PC3),
                "radius": radius,
                "image": _image_to_data_url(image_path),
                "rank_pca": int(row.rank_pca_whitened_l2),
                "rank_impact": int(profiles.get(str(row.player_id), {}).get("rank_impact", len(merged))),
                "impact_z": float(profiles.get(str(row.player_id), {}).get("impact_z", 0.0)),
                "rank_l2": int(row.rank_l2),
                "rank_mahalanobis": int(row.rank_mahalanobis),
                "score_l2": float(row.score_l2),
                "score_mahalanobis": float(row.score_mahalanobis),
                "score_pca": profiles.get(str(row.player_id), {}).get(
                    "score_pca",
                    float(row.score_pca_whitened_l2),
                ),
                "score_goat_index": profiles.get(str(row.player_id), {}).get(
                    "score_goat_index",
                    float(getattr(row, "score_goat_index", row.score_pca_whitened_l2)),
                ),
                "championships": profiles.get(str(row.player_id), {}).get(
                    "championships", int(getattr(row, "championships", 0))
                ),
                "playoff_seasons": profiles.get(str(row.player_id), {}).get(
                    "playoff_seasons", int(getattr(row, "playoff_seasons", 0))
                ),
                "playoff_performance": profiles.get(str(row.player_id), {}).get(
                    "playoff_performance", float(getattr(row, "playoff_performance", 0.0))
                ),
                "stat_outlier_z": profiles.get(str(row.player_id), {}).get(
                    "stat_outlier_z", float(getattr(row, "stat_outlier_z", 0.0))
                ),
                "team_strength_index": profiles.get(str(row.player_id), {}).get(
                    "team_strength_index", float(getattr(row, "team_strength_index", 0.0))
                ),
                "clutch_penalty": profiles.get(str(row.player_id), {}).get(
                    "clutch_penalty", float(getattr(row, "clutch_penalty", 0.0))
                ),
                "max_consecutive_championships": profiles.get(str(row.player_id), {}).get(
                    "max_consecutive_championships", int(getattr(row, "max_consecutive_championships", 0))
                ),
                "repeat_titles_score": profiles.get(str(row.player_id), {}).get(
                    "repeat_titles_score", float(getattr(row, "repeat_titles_score", 0.0))
                ),
                "is_impact_crown": profiles.get(str(row.player_id), {}).get(
                    "is_impact_crown",
                    False,
                ),
                "selected_default": str(row.player_id) in default_viz_ids,
                "aspects": profiles.get(str(row.player_id), {}).get("aspects", []),
                "z": cv_lookup.loc[pid, z_cols].tolist() if cv_lookup is not None and pid in cv_lookup.index and z_cols else [],
            }
        )

    html = _build_threejs_html(
        scene=scene,
        disclaimer=disclaimer,
        cumulative_3d=cumulative_3d,
        pc1_pct=pc1_pct,
        pc2_pct=pc2_pct,
        pc3_pct=pc3_pct,
        players=players,
        show_origin_lines=bool(embed_cfg.get("show_origin_lines", True)),
        pool_size=len(players),
        default_count=sum(1 for player in players if player.get("selected_default")),
        alchemy_meta=alchemy_meta,
    )

    out_path = paths.viz_output / "embed_3d.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
