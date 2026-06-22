from __future__ import annotations

import base64
import json
import re
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import yaml
from matplotlib.patches import Circle

from .io import VizArtifacts, VizPaths
from .profiles import compute_player_profiles


def theme_from_config(config: dict[str, Any]) -> dict[str, str]:
    theme = config.get("theme", {})
    return {
        "background": theme.get("background", "#0d1117"),
        "text": theme.get("text", "#e6edf3"),
        "accent": theme.get("accent", "#f97316"),
    }


def embed_scene_theme(config: dict[str, Any]) -> dict[str, str]:
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
        theme = theme_from_config(config)
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


def variance_pct(pca_explained_variance: dict[str, Any], component: str) -> float:
    for row in pca_explained_variance.get("components", []):
        if row.get("component") == component:
            return float(row.get("explained_variance_ratio", 0.0)) * 100.0
    return 0.0


def cumulative_3d_pct(pca_explained_variance: dict[str, Any]) -> float:
    return sum(variance_pct(pca_explained_variance, name) for name in ("PC1", "PC2", "PC3"))


def origin_inclusive_axis_range(values: pd.Series, pad_ratio: float = 0.14) -> tuple[float, float]:
    vmin = float(values.min())
    vmax = float(values.max())
    lo = min(0.0, vmin)
    hi = max(0.0, vmax)
    span = max(hi - lo, 1e-6)
    pad = span * pad_ratio
    return lo - pad, hi + pad


def map_axis(value: float, lo: float, hi: float) -> float:
    span = max(hi - lo, 1e-6)
    return ((value - lo) / span) * 2.0 - 1.0


def _normalize_display_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def default_viz_player_ids(paths: VizPaths, merged: pd.DataFrame) -> set[str]:
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


def merge_coords_and_rankings(artifacts: VizArtifacts) -> pd.DataFrame:
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


ZONE_SHARE_COLUMNS: tuple[str, ...] = (
    "zone_0_3_share",
    "zone_3_10_share",
    "zone_10_16_share",
    "zone_16_3p_share",
    "zone_3p_share",
    "zone_corner3_share",
)

ZONE_DISPLAY_LABELS: tuple[str, ...] = ("0–3 ft", "3–10 ft", "10–16 ft", "16–3P", "3P", "Corner 3")


def _load_manifest(paths: VizPaths) -> dict[str, Any] | None:
    for manifest_path in (
        paths.goat_root / "GoatProject-data" / "processed" / "manifest.json",
        paths.goat_root / "processed" / "manifest.json",
    ):
        if manifest_path.exists():
            return json.loads(manifest_path.read_text(encoding="utf-8"))
    return None


def load_manifest_core_dim(paths: VizPaths) -> int:
    manifest = _load_manifest(paths)
    if manifest is None:
        return 11
    cols = manifest.get("feature_columns")
    if isinstance(cols, list) and cols:
        return len(cols)
    return 11


def load_manifest_alchemy_columns(paths: VizPaths) -> list[str] | None:
    manifest = _load_manifest(paths)
    if manifest is None:
        return None
    cols = manifest.get("alchemy_feature_columns")
    if isinstance(cols, list) and cols:
        return [str(c) for c in cols]
    return None


def resolve_alchemy_z_columns(paths: VizPaths, career_vectors: pd.DataFrame | None) -> list[str]:
    manifest_cols = load_manifest_alchemy_columns(paths)
    if manifest_cols and career_vectors is not None:
        available = [c for c in manifest_cols if c in career_vectors.columns]
        if available:
            return available
    if career_vectors is None:
        return []
    return [c for c in career_vectors.columns if c.endswith("_z")]


def load_alchemy_meta(paths: VizPaths) -> dict[str, Any]:
    alchemy_cfg_path = paths.goat_root / "config" / "alchemy.yaml"
    alchemy_cfg = yaml.safe_load(alchemy_cfg_path.read_text(encoding="utf-8")) if alchemy_cfg_path.exists() else {}
    alpha_default = float(alchemy_cfg.get("blend", {}).get("alpha", 0.5))
    meta: dict[str, Any] = {
        "alpha_default": alpha_default,
        "cache_alpha_default": alpha_default,
        "disclaimer": alchemy_cfg.get("framing", {}).get("disclaimer", ""),
        "config_hash": "local",
        "schema_version": "1.0.0",
        "vector_dim": 18,
        "pca_core_dim": load_manifest_core_dim(paths),
        "zone_labels": list(ZONE_DISPLAY_LABELS),
        "zone_share_columns": list(ZONE_SHARE_COLUMNS),
    }
    cache_path = paths.modeling_output / "alchemy_cache.json"
    if cache_path.exists():
        cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
        meta["config_hash"] = cache_payload.get("config_hash", "local")
        meta["schema_version"] = cache_payload.get("schema_version", meta["schema_version"])
        meta["cache_entries"] = cache_payload.get("entries", {})
        if cache_payload.get("feature_dimension"):
            meta["vector_dim"] = int(cache_payload["feature_dimension"])
    else:
        meta["cache_entries"] = {}
    manifest = _load_manifest(paths)
    core_cols = None
    if manifest is not None:
        raw_core = manifest.get("feature_columns")
        if isinstance(raw_core, list) and raw_core:
            core_cols = [str(c) for c in raw_core]
    if core_cols:
        meta["core_feature_columns"] = core_cols
        meta["pca_core_dim"] = len(core_cols)

    manifest_cols = load_manifest_alchemy_columns(paths)
    if manifest_cols:
        meta["alchemy_feature_columns"] = manifest_cols
        meta["vector_dim"] = len(manifest_cols)
    else:
        from .alchemy_math import DEFAULT_ALCHEMY_COLUMNS, DEFAULT_CORE_COLUMNS

        meta["alchemy_feature_columns"] = list(DEFAULT_ALCHEMY_COLUMNS)
        if "core_feature_columns" not in meta:
            meta["core_feature_columns"] = list(DEFAULT_CORE_COLUMNS)
    return meta


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


def ensure_player_image(
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


def image_to_data_url(path: Path) -> str:
    payload = path.read_bytes()
    mime = "image/png" if payload.startswith(b"\x89PNG") else "image/jpeg"
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def build_players_payload(
    paths: VizPaths,
    artifacts: VizArtifacts,
    *,
    scene: dict[str, str],
    merged: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    config = artifacts.config
    embed_cfg = config.get("embed_3d", {})
    image_cfg = config.get("player_images", {})

    if merged is None:
        merged = merge_coords_and_rankings(artifacts)

    x_lo, x_hi = origin_inclusive_axis_range(merged["PC1"])
    y_lo, y_hi = origin_inclusive_axis_range(merged["PC2"])
    z_lo, z_hi = origin_inclusive_axis_range(merged["PC3"])

    min_radius = float(embed_cfg.get("orb_radius_min", 0.08))
    max_radius = float(embed_cfg.get("orb_radius_max", 0.16))

    profiles: dict[str, Any] = {}
    if artifacts.career_vectors is not None:
        profiles = compute_player_profiles(artifacts.career_vectors, artifacts.rankings, config)

    size_metric = embed_cfg.get("marker_size_metric", "impact_z")
    if size_metric == "impact_z":
        size_values = merged["player_id"].map(
            lambda pid: float(profiles.get(str(pid), {}).get("impact_z", 0.0))
        ).astype(float)
    else:
        size_values = merged[size_metric].astype(float)
    size_min, size_max = float(size_values.min()), float(size_values.max())
    size_span = max(size_max - size_min, 1e-6)

    alchemy_cols = resolve_alchemy_z_columns(paths, artifacts.career_vectors)
    cv_lookup = None
    if artifacts.career_vectors is not None:
        cv_lookup = artifacts.career_vectors.set_index("player_id")

    default_viz_ids = default_viz_player_ids(paths, merged)
    size_by_player = {
        str(pid): float(val) for pid, val in zip(merged["player_id"], size_values, strict=True)
    }

    players: list[dict[str, Any]] = []
    for row in merged.itertuples(index=False):
        pid = str(row.player_id)
        t = (size_by_player[pid] - size_min) / size_span
        radius = min_radius + t * (max_radius - min_radius)
        image_path = ensure_player_image(paths, pid, str(row.display_name), scene, image_cfg)

        z_vec: list[float] = []
        zone_shares: list[float] = []
        showman_z: float | None = None
        showman_partial = False
        if cv_lookup is not None and pid in cv_lookup.index:
            if alchemy_cols:
                z_vec = [float(cv_lookup.loc[pid, col]) for col in alchemy_cols]
            zone_shares = [
                float(cv_lookup.loc[pid, col]) if col in cv_lookup.columns else 0.0
                for col in ZONE_SHARE_COLUMNS
            ]
            if "showman_z" in cv_lookup.columns:
                showman_z = round(float(cv_lookup.loc[pid, "showman_z"]), 2)
            if "showman_partial" in cv_lookup.columns:
                showman_partial = bool(cv_lookup.loc[pid, "showman_partial"])

        players.append(
            {
                "id": row.player_id,
                "name": row.display_name,
                "x": map_axis(float(row.PC1), x_lo, x_hi),
                "y": map_axis(float(row.PC2), y_lo, y_hi),
                "z": map_axis(float(row.PC3), z_lo, z_hi),
                "pc1": float(row.PC1),
                "pc2": float(row.PC2),
                "pc3": float(row.PC3),
                "radius": radius,
                "image": image_to_data_url(image_path),
                "rank_pca": int(row.rank_pca_whitened_l2),
                "rank_impact": int(profiles.get(pid, {}).get("rank_impact", len(merged))),
                "impact_z": float(profiles.get(pid, {}).get("impact_z", 0.0)),
                "rank_l2": int(row.rank_l2),
                "rank_mahalanobis": int(row.rank_mahalanobis),
                "score_l2": float(row.score_l2),
                "score_mahalanobis": float(row.score_mahalanobis),
                "score_pca": profiles.get(pid, {}).get("score_pca", float(row.score_pca_whitened_l2)),
                "score_goat_index": profiles.get(pid, {}).get(
                    "score_goat_index",
                    float(getattr(row, "score_goat_index", row.score_pca_whitened_l2)),
                ),
                "championships": profiles.get(pid, {}).get(
                    "championships", int(getattr(row, "championships", 0))
                ),
                "playoff_seasons": profiles.get(pid, {}).get(
                    "playoff_seasons", int(getattr(row, "playoff_seasons", 0))
                ),
                "playoff_performance": profiles.get(pid, {}).get(
                    "playoff_performance", float(getattr(row, "playoff_performance", 0.0))
                ),
                "stat_outlier_z": profiles.get(pid, {}).get(
                    "stat_outlier_z", float(getattr(row, "stat_outlier_z", 0.0))
                ),
                "team_strength_index": profiles.get(pid, {}).get(
                    "team_strength_index", float(getattr(row, "team_strength_index", 0.0))
                ),
                "clutch_penalty": profiles.get(pid, {}).get(
                    "clutch_penalty", float(getattr(row, "clutch_penalty", 0.0))
                ),
                "max_consecutive_championships": profiles.get(pid, {}).get(
                    "max_consecutive_championships",
                    int(getattr(row, "max_consecutive_championships", 0)),
                ),
                "repeat_titles_score": profiles.get(pid, {}).get(
                    "repeat_titles_score", float(getattr(row, "repeat_titles_score", 0.0))
                ),
                "is_impact_crown": profiles.get(pid, {}).get("is_impact_crown", False),
                "selected_default": pid in default_viz_ids,
                "aspects": profiles.get(pid, {}).get("aspects", []),
                "z_vec": z_vec,
                "zone_shares": zone_shares,
                "showman_z": showman_z,
                "showman_partial": showman_partial,
                "z_dim": len(z_vec),
            }
        )

    return players


def three_importmap_html() -> str:
    return """  <script type="importmap">
    {
      "imports": {
        "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
        "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"
      }
    }
  </script>"""


def three_module_imports_js() -> str:
    return """    import * as THREE from 'three';
    import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
"""


def scene_bootstrap_js(*, viewport_id: str = "viewport") -> str:
    return f"""    const viewport = document.getElementById('{viewport_id}');

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
"""


def grid_and_origin_js() -> str:
    return r"""    function addAxisLine(direction, color, length = 1.25) {
      const points = [new THREE.Vector3(0, 0, 0), direction.clone().multiplyScalar(length)];
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const material = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.85 });
      scene.add(new THREE.Line(geometry, material));
    }

    if (sceneTheme.layout === 'desmos') {
      addAxisLine(new THREE.Vector3(1, 0, 0), sceneTheme.axis);
      addAxisLine(new THREE.Vector3(0, 1, 0), sceneTheme.axis);
      addAxisLine(new THREE.Vector3(0, 0, 1), sceneTheme.axis);

      const boxSize = 2.4;
      const boxGeometry = new THREE.BoxGeometry(boxSize, boxSize, boxSize);
      const boxEdges = new THREE.EdgesGeometry(boxGeometry);
      const boxLines = new THREE.LineSegments(
        boxEdges,
        new THREE.LineBasicMaterial({ color: sceneTheme.box, transparent: true, opacity: 0.55 }),
      );
      boxLines.position.y = -0.05;
      scene.add(boxLines);
    } else {
      const axes = new THREE.AxesHelper(1.15);
      axes.material.transparent = true;
      axes.material.opacity = 0.55;
      scene.add(axes);
    }

    const originMarker = new THREE.Mesh(
      new THREE.SphereGeometry(0.035, 16, 16),
      new THREE.MeshBasicMaterial({ color: sceneTheme.accent }),
    );
    scene.add(originMarker);
"""


def resize_handler_js() -> str:
    return """    function resizeRenderer() {
      const width = viewport.clientWidth;
      const height = viewport.clientHeight;
      if (width <= 0 || height <= 0) return;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    }

    function onResize() {
      resizeRenderer();
    }
    window.addEventListener('resize', onResize);
    resizeRenderer();
"""


def orb_factory_js(*, show_origin_lines_expr: str = "showOriginLines") -> str:
    return f"""    const orbMeshes = [];
    const orbGroups = new Map();
    const spokeOpacity = sceneTheme.layout === 'desmos' ? 0.35 : 0.22;
    const lineMaterial = new THREE.LineBasicMaterial({{
      color: new THREE.Color(sceneTheme.spoke),
      transparent: true,
      opacity: spokeOpacity,
    }});
    const textureLoader = new THREE.TextureLoader();

    async function buildOrbForPlayer(player, {{ withSpokes = {show_origin_lines_expr} }} = {{}}) {{
      const position = new THREE.Vector3(player.x, player.y, player.z);
      const spokes = [];
      if (withSpokes) {{
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

      orbGroups.set(player.id, {{ player, meshes, spokes }});
      return {{ orb, meshes, spokes }};
    }}

    async function buildAllOrbs(playersList, options = {{}}) {{
      for (const player of playersList) {{
        await buildOrbForPlayer(player, options);
      }}
    }}
"""


def render_loop_js() -> str:
    return """    function animate() {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }
"""
