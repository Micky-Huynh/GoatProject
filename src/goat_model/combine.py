from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

Metric = Literal["l2", "cosine"]


def canonical_pair_key(player_id_a: str, player_id_b: str) -> str:
    a, b = sorted([str(player_id_a), str(player_id_b)])
    return f"{a}|{b}"


def blend_vectors(
    u: np.ndarray,
    v: np.ndarray,
    alpha: float = 0.5,
    beta: float = 0.5,
) -> np.ndarray:
    return (alpha * u) + (beta * v)


def _normalize_rows(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms = np.clip(norms, a_min=1e-12, a_max=None)
    return values / norms


def nearest_neighbor(
    blend: np.ndarray,
    pool_vectors: np.ndarray,
    player_ids: list[str],
    display_names: list[str],
    metric: Metric = "l2",
) -> tuple[str, str, float]:
    if len(player_ids) != pool_vectors.shape[0]:
        raise ValueError("player_ids length must match pool_vectors rows")
    if metric == "l2":
        distances = np.linalg.norm(pool_vectors - blend.reshape(1, -1), axis=1)
        idx = int(np.argmin(distances))
        return player_ids[idx], display_names[idx], float(distances[idx])
    pool_norm = _normalize_rows(pool_vectors)
    blend_norm = blend / max(float(np.linalg.norm(blend)), 1e-12)
    similarities = pool_norm @ blend_norm
    idx = int(np.argmax(similarities))
    distance = float(1.0 - similarities[idx])
    return player_ids[idx], display_names[idx], distance


def alchemy_config_hash(alchemy_cfg: dict[str, Any], manifest: dict[str, Any]) -> str:
    manifest_hashes = manifest.get("config_hashes", {})
    payload = json.dumps(
        {
            "alchemy": alchemy_cfg,
            "alchemy_feature_columns": manifest.get("alchemy_feature_columns"),
            "manifest_hashes": manifest_hashes,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def combine_players(
    player_id_a: str,
    player_id_b: str,
    career_vectors: pd.DataFrame,
    z_cols: list[str],
    alchemy_cfg: dict[str, Any],
    metric: Metric | None = None,
) -> dict[str, Any]:
    if player_id_a == player_id_b:
        raise ValueError("Cannot combine a player with themselves")

    lookup = career_vectors.set_index("player_id")
    if player_id_a not in lookup.index or player_id_b not in lookup.index:
        raise KeyError("Both player_ids must exist in career_vectors")

    blend_cfg = alchemy_cfg.get("blend", {})
    alpha = float(blend_cfg.get("alpha", 0.5))
    beta = float(blend_cfg.get("beta", 0.5))
    chosen_metric: Metric = metric or alchemy_cfg.get("discovery", {}).get("metric", "l2")

    vec_a = lookup.loc[player_id_a, z_cols].to_numpy(dtype=float)
    vec_b = lookup.loc[player_id_b, z_cols].to_numpy(dtype=float)
    blended = blend_vectors(vec_a, vec_b, alpha=alpha, beta=beta)

    pool = career_vectors[["player_id", "display_name", *z_cols]].copy()
    pool_vectors = pool[z_cols].to_numpy(dtype=float)
    nearest_id, nearest_name, distance = nearest_neighbor(
        blended,
        pool_vectors,
        pool["player_id"].astype(str).tolist(),
        pool["display_name"].astype(str).tolist(),
        metric=chosen_metric,
    )

    name_a = str(lookup.loc[player_id_a, "display_name"])
    name_b = str(lookup.loc[player_id_b, "display_name"])
    pair_key = canonical_pair_key(player_id_a, player_id_b)

    return {
        "pair_key": pair_key,
        "player_a_id": str(player_id_a),
        "player_b_id": str(player_id_b),
        "player_a_name": name_a,
        "player_b_name": name_b,
        "blend_vector": blended.tolist(),
        "blend_alpha": alpha,
        "blend_beta": beta,
        "metric": chosen_metric,
        "nearest_player_id": nearest_id,
        "nearest_display_name": nearest_name,
        "nearest_distance": distance,
        "discovery_label": f"{name_a} + {name_b} → {nearest_name}",
    }


def build_alchemy_cache(
    career_vectors: pd.DataFrame,
    z_cols: list[str],
    alchemy_cfg: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    ids = career_vectors["player_id"].astype(str).tolist()
    entries: dict[str, Any] = {}
    for i, player_a in enumerate(ids):
        for player_b in ids[i + 1 :]:
            result = combine_players(player_a, player_b, career_vectors, z_cols, alchemy_cfg)
            pair_key = result.pop("pair_key")
            entries[pair_key] = result

    return {
        "schema_version": "2.0.0",
        "config_hash": alchemy_config_hash(alchemy_cfg, manifest),
        "player_count": len(ids),
        "feature_dimension": len(z_cols),
        "feature_columns": z_cols,
        "entries": entries,
    }


def load_alchemy_cache(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_alchemy_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def lookup_cached_combine(
    player_id_a: str,
    player_id_b: str,
    cache: dict[str, Any],
    expected_config_hash: str | None = None,
) -> dict[str, Any] | None:
    if expected_config_hash is not None and cache.get("config_hash") != expected_config_hash:
        return None
    pair_key = canonical_pair_key(player_id_a, player_id_b)
    entry = cache.get("entries", {}).get(pair_key)
    if entry is None:
        return None
    return {"pair_key": pair_key, **entry}
