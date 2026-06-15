from __future__ import annotations

from pathlib import Path

from goat_model.io import (
    aggregate_career_vectors,
    build_full_league_season_vectors,
    ensure_output_path,
    load_career_vectors,
    load_context,
    load_league_covariance,
    load_manifest,
    load_season_vectors,
    write_json,
    z_columns_from_manifest,
)
from goat_model.rank import build_rankings
from goat_model.playoff_scores import apply_playoff_and_clutch_scores, load_playoff_context, load_season_labels
from goat_model.sensitivity import run_sensitivity


def run(goat_root: Path | None = None) -> tuple:
    ctx = load_context(goat_root)
    manifest = load_manifest(ctx)
    z_cols = z_columns_from_manifest(manifest)
    career_vectors = load_career_vectors(ctx, manifest)
    season_vectors = load_season_vectors(ctx, manifest)
    covariance = load_league_covariance(ctx, manifest)

    full_seasons_default, _ = build_full_league_season_vectors(ctx, group_mode="season_pos_fallback")
    full_league_careers = aggregate_career_vectors(full_seasons_default, z_cols=z_cols, weight_by_minutes=False)

    rankings = build_rankings(
        career_vectors=career_vectors,
        z_cols=z_cols,
        covariance=covariance,
        full_league_careers=full_league_careers,
        scoring_cfg=ctx.scoring_cfg,
    )
    playoff_context = load_playoff_context(ctx)
    season_labels = load_season_labels(ctx)
    rankings = apply_playoff_and_clutch_scores(
        ctx,
        rankings,
        playoff_context,
        season_labels,
        career_vectors,
    )
    sensitivity_report = run_sensitivity(
        ctx=ctx,
        baseline_rankings=rankings,
        baseline_career_vectors=career_vectors[["player_id", "display_name", *z_cols]].copy(),
        season_vectors_allowlist=season_vectors,
        z_cols=z_cols,
    )

    rankings_path = ensure_output_path(ctx, "goat_rankings.csv")
    sensitivity_path = ensure_output_path(ctx, "sensitivity_report.json")
    rankings.to_csv(rankings_path, index=False)
    write_json(sensitivity_path, sensitivity_report)
    return rankings, sensitivity_report


def main() -> None:
    rankings, sensitivity_report = run()
    top_five = rankings.nsmallest(5, "rank_pca_whitened_l2")[["rank_pca_whitened_l2", "display_name", "score_pca_whitened_l2", "championships"]]
    print(top_five.to_string(index=False))
    crown = rankings.nsmallest(1, "rank_pca_whitened_l2")[["display_name", "score_pca_whitened_l2"]]
    print("pca_crown:", crown.to_string(index=False))


if __name__ == "__main__":
    main()
