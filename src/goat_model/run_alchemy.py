from __future__ import annotations

from pathlib import Path

from .combine import alchemy_config_hash, build_alchemy_cache, save_alchemy_cache
from .io import load_career_vectors, load_context, load_manifest, load_yaml, z_columns_from_manifest


def run(goat_root: Path | None = None) -> Path:
    ctx = load_context(goat_root)
    manifest = load_manifest(ctx)
    career_vectors = load_career_vectors(ctx, manifest)
    z_cols = z_columns_from_manifest(manifest)
    alchemy_cfg = load_yaml(ctx.root / "config" / "alchemy.yaml")

    cache = build_alchemy_cache(career_vectors, z_cols, alchemy_cfg, manifest)
    cache["config_hash"] = alchemy_config_hash(alchemy_cfg, manifest)

    artifact_name = alchemy_cfg.get("cache", {}).get("artifact", "alchemy_cache.json")
    out_path = ctx.output_dir / artifact_name
    save_alchemy_cache(out_path, cache)
    return out_path


def main() -> None:
    path = run()
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
