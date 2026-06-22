# Unit-002 Handoff: R¹⁸ Alchemy Cache

**Worker:** unit-002  
**Date:** 2026-06-21  
**Status:** Complete

## Summary

Upgraded alchemy cache from R¹¹ to R¹⁸ using `manifest.alchemy_feature_columns` (11 core + showman + 6 zone z-scores). Core ranking geometry remains on 11-dim `feature_columns`. Alchemy display metadata (showman + zone shares) now pass through to `goat_rankings.csv`.

## Files changed

### Config (main worktree)
- `config/alchemy.yaml` — version `2.0.0`; disclaimer updated to R^18 with showman + shot zones

### Modeling (`GoatProject-modeling`)
- `src/goat_model/io.py` — added `alchemy_z_columns_from_manifest()`; kept `z_columns_from_manifest()` for 11 core columns
- `src/goat_model/combine.py` — `alchemy_config_hash` keys on `alchemy_feature_columns`; cache `schema_version` → `2.0.0`
- `src/goat_model/run_alchemy.py` — cache build uses alchemy columns
- `src/goat_model/rank.py` — pass-through `showman_z`, `showman_partial`, zone share columns to rankings CSV (display only; not used in scoring)

### Tests
- `tests/test_combine.py` — blend vector length 18; hash invalidates when alchemy columns change; schema_version assertion
- `tests/test_alchemy_features.py` — asserts alchemy columns (18) ≠ ranking columns (11); alchemy is strict superset

### Artifacts regenerated
- `output/alchemy_cache.json` — 4950 pairs, dim 18, schema `2.0.0`, config_hash `e316a4c1d56b971e`

## Behavior notes

- **Ranking scores** still computed from 11 core z-columns only (`z_columns_from_manifest`).
- **Alchemy cache** blends and nearest-neighbor search in R¹⁸ via `alchemy_z_columns_from_manifest`.
- **Config hash** invalidates when `alchemy_feature_columns` or alchemy.yaml changes (not when only `feature_columns` changes, if alchemy list unchanged).
- **goat_rankings.csv** now includes alchemy display columns for downstream viz; does not affect rank ordering.

## Test results

```bash
cd GoatProject-modeling && GOAT_ROOT=.. PYTHONPATH=src python3.11 -m pytest tests/ -q
```

**17 passed** in ~178s (2026-06-21)

```bash
cd GoatProject-modeling && GOAT_ROOT=.. PYTHONPATH=src python3.11 -m goat_model.run_alchemy
```

Wrote `output/alchemy_cache.json` (100 players → 4950 pairs)

## Verification snapshot

| Field | Value |
|-------|-------|
| `cache.schema_version` | `2.0.0` |
| `cache.feature_dimension` | 18 |
| `cache.config_hash` | `e316a4c1d56b971e` |
| `manifest.feature_columns` | 11 |
| `manifest.alchemy_feature_columns` | 18 |
| `blend_vector` length | 18 |

## Blockers / notes for orchestrator

1. **Downstream viz (`GoatProject-viz`)** — alchemy.html must consume R¹⁸ cache and display dual labels (11-dim PCA orb vs 18-dim L2 NN); out of scope here.
2. **Cache size** — 4950 pair entries at 100 players; scales O(n²); acceptable for allowlist.
3. **Prior cache** — v1.0.0 R¹¹ cache is obsolete; viz should check `schema_version` / `config_hash`.
