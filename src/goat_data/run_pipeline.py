from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from goat_data.aggregate import aggregate_career_vectors
from goat_data.config import (
    PIPELINE_VERSION,
    SCHEMA_VERSION,
    config_hashes,
    feature_spec,
    load_yaml,
    resolve_paths,
    sha256_file,
    write_json,
    z_column,
)
from goat_data.covariance import build_league_covariance
from goat_data.era_adjust import era_adjust
from goat_data.labels import build_season_labels
from goat_data.excitement import build_career_excitement
from goat_data.load import load_advanced_seasons
from goat_data.players import resolve_allowlist
from goat_data.shooting_zones import build_career_shooting_zones
from goat_data.playoffs import build_playoff_context


def _filter_seasons(frame: pd.DataFrame, pipeline_cfg: dict) -> tuple[pd.DataFrame, dict[str, int]]:
    min_mp = int(pipeline_cfg["season_filter"]["min_minutes"])
    core = pipeline_cfg["missing_features"]["core_features"]

    before = len(frame)
    filtered = frame[frame["mp"] >= min_mp].copy()
    dropped_low_mp = before - len(filtered)

    before_core = len(filtered)
    for col in core:
        filtered = filtered[filtered[col].notna()]
    dropped_missing_core = before_core - len(filtered)

    return filtered, {
        "dropped_low_minutes": dropped_low_mp,
        "dropped_missing_core": dropped_missing_core,
    }


def _raw_csv_checksums(raw_data: Path) -> dict[str, str]:
    files = sorted(raw_data.glob("*.csv"))
    return {path.name: sha256_file(path) for path in files}


def _player_manifest_rows(career_vectors: pd.DataFrame) -> list[dict]:
    rows = []
    for _, row in career_vectors.sort_values("player_id").iterrows():
        rows.append(
            {
                "player_id": row["player_id"],
                "display_name": row["display_name"],
                "season_count": int(row["season_count"]),
            }
        )
    return rows

def _alchemy_columns(paths) -> tuple[list[str], list[str]]:
    zones_cfg = load_yaml(paths.root / "config" / "scoring_zones.yaml")
    zone_z_cols = [meta["z_column"] for meta in zones_cfg["zones"].values()]
    alchemy_z_cols = ["showman_z", *zone_z_cols]
    alchemy_meta_cols = ["showman_partial", *[meta["share_column"] for meta in zones_cfg["zones"].values()]]
    return alchemy_z_cols, alchemy_meta_cols


def run(paths=None) -> dict:
    goat_paths = resolve_paths(paths)
    pipeline_cfg = load_yaml(goat_paths.pipeline)
    features_cfg = load_yaml(goat_paths.features)
    feature_names, _, _, _ = feature_spec(features_cfg)
    z_cols = [z_column(name) for name in feature_names]

    allowlist = resolve_allowlist(goat_paths)

    raw = load_advanced_seasons(goat_paths)
    era_result = era_adjust(raw, goat_paths, allowlist.pre_three_point_line_players)

    filtered, drop_counts = _filter_seasons(era_result.frame, pipeline_cfg)

    league_display = (
        filtered[["player_id", "player"]]
        .drop_duplicates("player_id")
        .set_index("player_id")["player"]
        .to_dict()
    )

    allowlist_seasons = filtered[filtered["player_id"].isin(allowlist.player_ids)].copy()

    metadata_cols = ["player_id", "player", "season", "pos", "age", "mp", "pre_three_point_line"]
    season_vectors = allowlist_seasons[metadata_cols + z_cols].rename(columns={"pos": "position", "player": "display_name"})

    career_vectors = aggregate_career_vectors(
        allowlist_seasons.assign(display_name=allowlist_seasons["player_id"].map(allowlist.display_names)),
        feature_names,
        allowlist.display_names,
    )

    excitement_result = build_career_excitement(
        goat_paths,
        allowlist_seasons,
        allowlist.player_ids,
    )
    zones_result = build_career_shooting_zones(goat_paths, allowlist_seasons)
    alchemy_z_cols, alchemy_meta_cols = _alchemy_columns(goat_paths)

    excitement_cols = ["player_id", "showman_z", "showman_raw", "showman_partial"]
    career_vectors = career_vectors.merge(excitement_result.career[excitement_cols], on="player_id", how="left")
    career_vectors = career_vectors.merge(zones_result.career, on="player_id", how="left")
    career_vectors[alchemy_z_cols] = career_vectors[alchemy_z_cols].fillna(0.0)
    career_vectors["showman_partial"] = career_vectors["showman_partial"].fillna(False).astype(bool)

    playoff_result = build_playoff_context(
        goat_paths,
        allowlist.player_ids,
        allowlist.display_names,
    )
    playoff_context = playoff_result.player_context

    labels, label_stats = build_season_labels(
        goat_paths,
        season_vectors[["player_id", "season"]],
    )

    cov_path = goat_paths.processed / "league_career_covariance.npy"
    cov_result = build_league_covariance(
        filtered.assign(display_name=filtered["player"].where(filtered["player"].notna(), filtered["player_id"])),
        feature_names,
        league_display,
        cov_path,
    )

    goat_paths.processed.mkdir(parents=True, exist_ok=True)
    season_vectors.to_parquet(goat_paths.processed / "season_vectors.parquet", index=False)
    career_vectors.to_parquet(goat_paths.processed / "career_vectors.parquet", index=False)
    labels.to_parquet(goat_paths.processed / "season_labels.parquet", index=False)
    playoff_context.to_parquet(goat_paths.processed / "playoff_context.parquet", index=False)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "player_count": len(career_vectors),
        "players": _player_manifest_rows(career_vectors),
        "artifacts": {
            "season_vectors": "processed/season_vectors.parquet",
            "career_vectors": "processed/career_vectors.parquet",
            "season_labels": "processed/season_labels.parquet",
            "playoff_context": "processed/playoff_context.parquet",
            "league_career_covariance": "processed/league_career_covariance.npy",
        },
        "feature_columns": z_cols,
        "alchemy_feature_columns": z_cols + alchemy_z_cols,
        "alchemy_metadata_columns": alchemy_meta_cols,
        "metadata_columns": ["player_id", "season", "position", "age", "pre_three_point_line"],
        "era_adjustment": {
            "method": "z_score",
            "group_by": pipeline_cfg["era_adjustment"]["group_by"],
            "baseline_population": pipeline_cfg["era_adjustment"]["baseline_population"],
            "fallback_row_count": era_result.fallback_row_count,
            "group_levels_used": era_result.group_levels_used,
        },
        "missing_data_drops": drop_counts,
        "config_hashes": config_hashes(goat_paths),
        "raw_csv_checksums": _raw_csv_checksums(goat_paths.raw_data),
        "feature_correlation_max": cov_result.max_correlation,
        "covariance_condition_number": cov_result.condition_number,
        "covariance_player_count": cov_result.player_count,
        "label_stats": {
            "mvp_rows": label_stats.mvp_rows,
            "all_nba_first_rows": label_stats.all_nba_first_rows,
            "all_nba_any_rows": label_stats.all_nba_any_rows,
            "seasons_labeled": label_stats.seasons_labeled,
        },
        "vector_space": {
            "ambient_space": "R^d_standard",
            "field": "R",
            "feature_dimension": len(z_cols),
            "alchemy_feature_dimension": len(z_cols) + len(alchemy_z_cols),
            "embeddings_are_subspace": False,
            "embedding_map": "Phi: player career data -> bar{z}_i in R^d (nonlinear pipeline)",
            "x3p_ar_career_coordinate": "mean of finite season x3p_ar_z values (skip-NA)",
        },
    }

    write_json(goat_paths.processed / "manifest.json", manifest)
    return manifest


def main() -> None:
    manifest = run()
    print(f"Pipeline complete: {manifest['player_count']} players, {len(manifest['feature_columns'])} features")


if __name__ == "__main__":
    main()
