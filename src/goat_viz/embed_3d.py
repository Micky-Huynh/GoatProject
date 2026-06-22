from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .alchemy_js import inline_click_js, inline_client_js
from .io import VizArtifacts, VizPaths
from .site_shell import SITE_EMBED_HEAD, SITE_NAV_MESSAGE_JS
from .scene_shared import (
    build_players_payload,
    cumulative_3d_pct,
    embed_scene_theme,
    load_alchemy_meta,
    merge_coords_and_rankings,
    variance_pct,
)




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
    alchemy_inline: bool = False,
) -> str:
    payload = json.dumps(players)
    disclaimer_json = json.dumps(disclaimer)
    alchemy_json = json.dumps(alchemy_meta or {})
    alchemy_block = inline_client_js(alchemy_json) if alchemy_inline else ""
    alchemy_click = inline_click_js() if alchemy_inline else ""
    alchemy_toggle_row = (
        '<button type="button" id="alchemy-toggle">⚗ Alchemy mode (pick 2 orbs)</button>'
        if alchemy_inline else ''
    )
    alchemy_hint = (
        'Drag to rotate · scroll to zoom · Alchemy: toggle ⚗ then click two orbs'
        if alchemy_inline else 'Drag to rotate · scroll to zoom · hover orbs for profiles'
    )
    alchemy_mode_stub = '' if alchemy_inline else '    const alchemyMode = false;'
    embed_head = SITE_EMBED_HEAD
    nav_js = SITE_NAV_MESSAGE_JS
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GOAT 3D Stat-Space Explorer</title>
{embed_head}
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
    .top-nav {{ display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }}
    .top-nav a {{ color: {scene["accent"]}; font-size: 0.8rem; text-decoration: none; }}
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
    #crown-toggle.active {{
      background: rgba(251, 191, 36, 0.18);
      border-color: rgba(251, 191, 36, 0.55);
      color: #fbbf24;
      font-weight: 600;
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
      border-left: 1px solid {scene["chrome_border"]};
      background: {scene["background"]};
      padding: 14px 16px;
      overflow-y: auto;
      min-height: 0;
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
    #tooltip {{
      display: none !important;
    }}
    .profile-stats {{
      margin: 0 0 12px;
      color: {scene["muted"]};
      font-size: 0.78rem;
      line-height: 1.45;
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
          <button type="button" id="crown-toggle" class="active" title="Show gold halo on #1 impact among visible players">👑 Crown</button>
        </div>
        {alchemy_toggle_row}
        <div id="player-list"></div>
      </aside>
      <div id="viewport"></div>
      <aside id="profile-panel" aria-live="polite"></aside>
    </div>
    <footer id="chrome-bottom">
      <div id="hint" title="Clutch adj penalizes players whose BPM/VORP/PER/WS z-scores exceed their playoff performance + MVP/All-NBA consensus."><span class="legend-chip"><span class="legend-dot"></span>Gold crown = #1 impact among visible players</span>{alchemy_hint}</div>
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
{nav_js}
  <script type="module">
    import * as THREE from 'three';
    import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';

    const sceneTheme = {json.dumps(scene)};
    const players = {payload};

{alchemy_mode_stub}
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
    let crownEnabled = true;

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
      const crowned = crownEnabled && isCohortImpactLeader(player);
      const bestBadge = crowned ? '<div class="crown-badge">👑 #1 overall impact (visible)</div>' : '';
      profilePanel.innerHTML = `
        <div class="profile-card ${{crowned ? 'is-crowned' : ''}}">
          ${{bestBadge}}
          <h2>${{player.name}}</h2>
          <p class="profile-rank">Impact #${{cohortRank}} of ${{cohortSize}} visible · impact z ${{player.impact_z.toFixed(2)}} · all-pool #${{player.rank_impact}}</p>
          <p class="profile-meta">${{player.championships}} titles (${{player.max_consecutive_championships}}-peat max) · ${{player.playoff_seasons}} playoff yrs · perf ${{player.playoff_performance.toFixed(2)}} · clutch adj +${{player.clutch_penalty.toFixed(2)}}</p>
          <p class="profile-stats">L2: ${{player.score_l2.toFixed(2)}} (#${{player.rank_l2}}) · Mahalanobis: ${{player.score_mahalanobis.toFixed(2)}} (#${{player.rank_mahalanobis}})</p>
          <p class="profile-stats">PC1: ${{player.pc1.toFixed(2)}}, PC2: ${{player.pc2.toFixed(2)}}, PC3: ${{player.pc3.toFixed(2)}}</p>
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
        const showCrown = crownEnabled && playerId === leaderId && selectedIds.has(playerId);
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

      document.getElementById('crown-toggle').addEventListener('click', () => {{
        crownEnabled = !crownEnabled;
        const btn = document.getElementById('crown-toggle');
        btn.classList.toggle('active', crownEnabled);
        updateCrownVisuals();
        if (pinnedPlayer) {{
          renderProfilePanel(pinnedPlayer);
        }} else {{
          renderProfilePanel(defaultBestPlayer());
        }}
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

        const material = new THREE.MeshBasicMaterial({{ map: texture, transparent: true }});
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
      const crownNote = crownEnabled && isCohortImpactLeader(player) ? '<br>👑 #1 impact (visible)' : '';
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
        pinnedPlayer = active;
        renderProfilePanel(active);
      }} else if (!alchemyMode) {{
        document.body.style.cursor = 'default';
        pinnedPlayer = null;
        renderProfilePanel(defaultBestPlayer());
      }} else {{
        document.body.style.cursor = 'default';
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
    scene = embed_scene_theme(config)
    disclaimer = config.get("captions", {}).get("exploratory_disclaimer", "")
    alchemy_inline = bool(config.get("alchemy_inline", False))

    if not embed_cfg.get("enabled", True):
        raise ValueError("embed_3d is disabled in config/viz.yaml")

    merged = merge_coords_and_rankings(artifacts)
    for col in ("PC1", "PC2", "PC3"):
        if col not in merged.columns:
            raise ValueError(f"pca_coordinates.csv missing {col} for 3D embedding")

    pc1_pct = variance_pct(artifacts.pca_explained_variance, "PC1")
    pc2_pct = variance_pct(artifacts.pca_explained_variance, "PC2")
    pc3_pct = variance_pct(artifacts.pca_explained_variance, "PC3")
    cumulative_3d = cumulative_3d_pct(artifacts.pca_explained_variance)

    alchemy_meta = load_alchemy_meta(paths)
    players = build_players_payload(paths, artifacts, scene=scene, merged=merged)

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
        alchemy_inline=alchemy_inline,
    )

    out_path = paths.viz_output / "embed_3d.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
