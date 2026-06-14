from __future__ import annotations

from pathlib import Path

from goat_model.analyze import (
    build_full_league_careers_for_pca,
    cosine_similarity_matrix,
    fit_pca_for_threshold,
    nearest_neighbor_uniqueness,
    pca_explained_variance_payload,
    pca_loadings,
    project_to_pca,
)
from goat_model.io import (
    ensure_output_path,
    load_career_vectors,
    load_context,
    load_manifest,
    write_json,
    z_columns_from_manifest,
)


def run(goat_root: Path | None = None) -> dict[str, Path]:
    ctx = load_context(goat_root)
    manifest = load_manifest(ctx)
    z_cols = z_columns_from_manifest(manifest)

    allowlist_careers = load_career_vectors(ctx, manifest)
    full_league_careers = build_full_league_careers_for_pca(ctx, z_cols=z_cols)
    threshold = float(ctx.scoring_cfg["scores"]["pca_whitened_l2"]["cumulative_variance_threshold"])
    pca = fit_pca_for_threshold(
        full_league_careers=full_league_careers,
        z_cols=z_cols,
        cumulative_variance_threshold=threshold,
    )

    similarity = cosine_similarity_matrix(allowlist_careers, z_cols=z_cols)
    coordinates = project_to_pca(allowlist_careers, z_cols=z_cols, pca=pca)
    loadings = pca_loadings(z_cols=z_cols, pca=pca)
    variance_payload = pca_explained_variance_payload(pca)
    uniqueness = nearest_neighbor_uniqueness(allowlist_careers, z_cols=z_cols)

    output_paths = {
        "similarity_matrix": ensure_output_path(ctx, "similarity_matrix.csv"),
        "pca_coordinates": ensure_output_path(ctx, "pca_coordinates.csv"),
        "pca_explained_variance": ensure_output_path(ctx, "pca_explained_variance.json"),
        "pca_loadings": ensure_output_path(ctx, "pca_loadings.csv"),
        "uniqueness": ensure_output_path(ctx, "uniqueness.csv"),
    }

    similarity.to_csv(output_paths["similarity_matrix"], index=True, index_label="player_id")
    coordinates.to_csv(output_paths["pca_coordinates"], index=False)
    write_json(output_paths["pca_explained_variance"], variance_payload)
    loadings.to_csv(output_paths["pca_loadings"], index=False)
    uniqueness.to_csv(output_paths["uniqueness"], index=False)

    return output_paths


def main() -> None:
    paths = run()
    for artifact, path in paths.items():
        print(f"{artifact}: {path}")


if __name__ == "__main__":
    main()
