from __future__ import annotations

import json
import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

PRE_THREE_POINT_LINE_SEASON = 1980


@dataclass(frozen=True)
class GoatContext:
    root: Path
    raw_data_dir: Path
    processed_dir: Path
    output_dir: Path
    scoring_cfg: dict[str, Any]
    features_cfg: dict[str, Any]
    paths_cfg: dict[str, Any]
    pipeline_cfg: dict[str, Any]
    allowlist_cfg: dict[str, Any]


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().split())


def find_goat_root(start: Path | None = None) -> Path:
    env = os.environ.get("GOAT_ROOT")
    if env:
        root = Path(env).expanduser().resolve()
        if (root / "config" / "paths.yaml").is_file():
            return root
        raise FileNotFoundError(f"GOAT_ROOT={root} missing config/paths.yaml")

    cursor = (start or Path.cwd()).resolve()
    for parent in (cursor, *cursor.parents):
        if (parent / "config" / "paths.yaml").is_file():
            return parent

    raise FileNotFoundError("Could not locate GoatProject root. Set GOAT_ROOT.")


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_context(goat_root: Path | None = None) -> GoatContext:
    root = goat_root or find_goat_root()
    scoring_cfg = load_yaml(root / "config" / "scoring.yaml")
    features_cfg = load_yaml(root / "config" / "features.yaml")
    paths_cfg = load_yaml(root / "config" / "paths.yaml")
    pipeline_cfg = load_yaml(root / "config" / "pipeline.yaml")
    allowlist_cfg = load_yaml(root / "config" / "allowlist.yaml")

    raw_data_dir = root / paths_cfg["paths"]["raw_data"]
    processed_dir = root / paths_cfg["paths"]["processed"]
    output_dir = root / paths_cfg["paths"]["model_output"]
    output_dir.mkdir(parents=True, exist_ok=True)

    return GoatContext(
        root=root,
        raw_data_dir=raw_data_dir,
        processed_dir=processed_dir,
        output_dir=output_dir,
        scoring_cfg=scoring_cfg,
        features_cfg=features_cfg,
        paths_cfg=paths_cfg,
        pipeline_cfg=pipeline_cfg,
        allowlist_cfg=allowlist_cfg,
    )


def _resolve_artifact_path(ctx: GoatContext, configured_path: str) -> Path:
    if configured_path.startswith("processed/"):
        return ctx.processed_dir / configured_path.split("/", 1)[1]
    return ctx.root / configured_path


def load_manifest(ctx: GoatContext) -> dict[str, Any]:
    manifest_rel = ctx.paths_cfg["artifacts"]["manifest"]
    path = _resolve_artifact_path(ctx, manifest_rel)
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_career_vectors(ctx: GoatContext, manifest: dict[str, Any]) -> pd.DataFrame:
    path = _resolve_artifact_path(ctx, manifest["artifacts"]["career_vectors"])
    return pd.read_parquet(path)


def load_season_vectors(ctx: GoatContext, manifest: dict[str, Any]) -> pd.DataFrame:
    path = _resolve_artifact_path(ctx, manifest["artifacts"]["season_vectors"])
    return pd.read_parquet(path)


def load_league_covariance(ctx: GoatContext, manifest: dict[str, Any]) -> np.ndarray:
    path = _resolve_artifact_path(ctx, manifest["artifacts"]["league_career_covariance"])
    return np.load(path)


def z_columns_from_manifest(manifest: dict[str, Any]) -> list[str]:
    return list(manifest["feature_columns"])


def alchemy_z_columns_from_manifest(manifest: dict[str, Any]) -> list[str]:
    return list(manifest["alchemy_feature_columns"])


def ensure_output_path(ctx: GoatContext, filename: str) -> Path:
    path = ctx.output_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _pick_advanced_row(group: pd.DataFrame) -> pd.Series:
    totals = group[group["team"].astype(str).str.endswith("TM", na=False)]
    if not totals.empty:
        return totals.iloc[0]
    return group.sort_values("mp", ascending=False).iloc[0]


def _pick_season_info_row(group: pd.DataFrame) -> pd.Series:
    totals = group[group["team"].astype(str).str.endswith("TM", na=False)]
    if not totals.empty:
        return totals.iloc[0]
    return group.iloc[0]


def _dedupe_player_season(frame: pd.DataFrame, pick_fn) -> pd.DataFrame:
    rows = [pick_fn(group) for _, group in frame.groupby(["player_id", "season"], sort=False)]
    return pd.DataFrame(rows).reset_index(drop=True)


def _zscore_values(values: pd.Series) -> pd.Series:
    valid = values.dropna()
    if valid.empty:
        return pd.Series(np.nan, index=values.index)
    std = valid.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(0.0, index=values.index)
    return (values - valid.mean()) / std


def _assign_group_zscores(
    frame: pd.DataFrame,
    group_cols: list[str],
    feature_names: list[str],
    name_to_column: dict[str, str],
) -> pd.DataFrame:
    adjusted = frame.copy()
    z_cols = [f"{name}_z" for name in feature_names]
    for col in z_cols:
        adjusted[col] = np.nan

    for _, group in adjusted.groupby(group_cols, dropna=False):
        for feature_name in feature_names:
            raw_col = name_to_column[feature_name]
            adjusted.loc[group.index, f"{feature_name}_z"] = _zscore_values(group[raw_col])
    return adjusted


def _load_raw_advanced_seasons(ctx: GoatContext) -> pd.DataFrame:
    features_cfg = ctx.features_cfg
    name_to_column = {name: meta["column"] for name, meta in features_cfg["features"].items()}
    raw_columns = sorted(set(name_to_column.values()))

    advanced = pd.read_csv(ctx.raw_data_dir / "Advanced.csv")
    keep = ["player_id", "player", "season", "team", "pos", "mp", *raw_columns]
    advanced = _dedupe_player_season(advanced[keep], _pick_advanced_row)

    season_info = pd.read_csv(ctx.raw_data_dir / "Player Season Info.csv")
    season_info = _dedupe_player_season(season_info, _pick_season_info_row)
    season_info = season_info[["player_id", "season", "age"]]

    merged = advanced.merge(season_info, on=["player_id", "season"], how="left")
    merged["season"] = merged["season"].astype(int)
    merged["mp"] = pd.to_numeric(merged["mp"], errors="coerce")
    for col in raw_columns:
        merged[col] = pd.to_numeric(merged[col], errors="coerce")
    return merged


def _resolve_pre_three_player_ids(raw_frame: pd.DataFrame, allowlist_cfg: dict[str, Any]) -> set[str]:
    wanted = {normalize_name(name) for name in allowlist_cfg.get("pre_three_point_line_players", [])}
    if not wanted:
        return set()
    lookup = (
        raw_frame[["player_id", "player"]]
        .dropna(subset=["player_id", "player"])
        .drop_duplicates("player_id")
        .assign(_norm=lambda d: d["player"].map(normalize_name))
    )
    matched = lookup[lookup["_norm"].isin(wanted)]
    return set(matched["player_id"].tolist())


def _filter_seasons(
    frame: pd.DataFrame,
    pipeline_cfg: dict[str, Any],
    min_minutes_override: int | None = None,
) -> pd.DataFrame:
    min_minutes = (
        int(min_minutes_override)
        if min_minutes_override is not None
        else int(pipeline_cfg["season_filter"]["min_minutes"])
    )
    core = list(pipeline_cfg["missing_features"]["core_features"])
    filtered = frame[frame["mp"] >= min_minutes].copy()
    for col in core:
        filtered = filtered[filtered[col].notna()]
    return filtered


def build_full_league_season_vectors(
    ctx: GoatContext,
    group_mode: str = "season_pos_fallback",
    min_minutes_override: int | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    feature_meta = ctx.features_cfg["features"]
    feature_names = list(feature_meta.keys())
    name_to_column = {name: meta["column"] for name, meta in feature_meta.items()}
    orientation = {name: int(meta["orient"]) for name, meta in feature_meta.items()}
    pre_three_excluded = [
        name for name, meta in feature_meta.items() if meta.get("exclude_when_pre_three_point_line")
    ]

    raw = _load_raw_advanced_seasons(ctx)
    pre_three_ids = _resolve_pre_three_player_ids(raw, ctx.allowlist_cfg)
    working = raw.copy()
    working["pre_three_point_line"] = working["player_id"].isin(pre_three_ids) & (
        working["season"] < PRE_THREE_POINT_LINE_SEASON
    )

    for feature_name in pre_three_excluded:
        raw_col = name_to_column[feature_name]
        working.loc[working["pre_three_point_line"], raw_col] = np.nan

    if group_mode == "season_only":
        adjusted = _assign_group_zscores(working, ["season"], feature_names, name_to_column)
    else:
        group_cols = list(ctx.pipeline_cfg["era_adjustment"]["group_by"])
        min_group_n = int(ctx.pipeline_cfg["era_adjustment"]["min_group_n"])
        adjusted = _assign_group_zscores(working, group_cols, feature_names, name_to_column)
        group_sizes = adjusted.groupby(group_cols, dropna=False)["player_id"].transform("count")
        fallback_mask = group_sizes < min_group_n
        if fallback_mask.any():
            season_only = _assign_group_zscores(
                working.loc[fallback_mask],
                ["season"],
                feature_names,
                name_to_column,
            )
            z_cols = [f"{name}_z" for name in feature_names]
            adjusted.loc[fallback_mask, z_cols] = season_only[z_cols].to_numpy()

    for feature_name, orient in orientation.items():
        adjusted[f"{feature_name}_z"] = adjusted[f"{feature_name}_z"] * orient

    filtered = _filter_seasons(adjusted, ctx.pipeline_cfg, min_minutes_override=min_minutes_override)
    return filtered, [f"{name}_z" for name in feature_names]


def aggregate_career_vectors(
    season_vectors: pd.DataFrame,
    z_cols: list[str],
    weight_by_minutes: bool = False,
) -> pd.DataFrame:
    if weight_by_minutes:
        rows = []
        for player_id, group in season_vectors.groupby("player_id", sort=False):
            weights = group["mp"].to_numpy(dtype=float)
            rows.append(
                {
                    "player_id": player_id,
                    **{col: float(np.average(group[col].to_numpy(dtype=float), weights=weights)) for col in z_cols},
                }
            )
        careers = pd.DataFrame(rows)
    else:
        careers = season_vectors.groupby("player_id", as_index=False)[z_cols].mean()

    counts = season_vectors.groupby("player_id", as_index=False).agg(season_count=("season", "count"))
    if "display_name" in season_vectors.columns:
        names = season_vectors[["player_id", "display_name"]].drop_duplicates("player_id")
    else:
        names = (
            season_vectors[["player_id", "player"]]
            .drop_duplicates("player_id")
            .rename(columns={"player": "display_name"})
        )
    careers = careers.merge(counts, on="player_id", how="left")
    careers = careers.merge(names, on="player_id", how="left")
    return careers
