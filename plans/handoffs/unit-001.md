# Unit-001 Handoff: Showman + Shot Zones Data Pipeline

**Worker:** unit-001  
**Date:** 2026-06-21  
**Status:** Complete

## Summary

Implemented alchemy-only Showman excitement score and shot-zone features in `GoatProject-data`, extending `career_vectors.parquet` and `manifest.json` with R¹⁸ alchemy columns while keeping core `feature_columns` at 11.

## Files changed

### Config (main worktree)
- `config/showman.yaml` — full vs `legacy_partial` weights; data-availability rule for partial flag
- `config/scoring_zones.yaml` — zone→CSV column map; `corner3` derived as `percent_corner_3s_of_3pa * percent_fga_from_x3p_range`

### Pipeline (`GoatProject-data`)
- `src/goat_data/load.py` — `load_shooting_seasons`, `load_play_by_play_seasons`, `load_player_totals_seasons` (FGA for and1/heave rates)
- `src/goat_data/excitement.py` — season components, era-adjusted z, career aggregate, `showman_raw`/`showman_z`, `showman_partial`
- `src/goat_data/shooting_zones.py` — season zone shares, era-adjusted zone z, career means
- `src/goat_data/run_pipeline.py` — merge alchemy into `career_vectors`; manifest `alchemy_feature_columns` (18), `alchemy_metadata_columns`

### Tests
- `tests/test_excitement.py` — partial reweight sums to 1; dunk/and1 excluded from partial composite
- `tests/test_shooting_zones.py` — base zone shares sum ≈ 1 (derived `corner3` excluded from sum)
- `tests/test_vector_space.py` — asserts `alchemy_feature_columns` length 18, `feature_columns` still 11

## Behavior notes

- **Showman components (season):** `dunk_freq`, `and1_rate` (= and1/fga), `all_star_rate`, `heave_rate`, `mvp_vote_share`
- **Career:** mean z for dunk/and1/all-star/heave; MVP uses **peak** share then allowlist z-score
- **Partial (54/100 players):** any qualifying season missing dunk or and1 → `showman_partial=true`; uses reweighted ASG/MVP/heave only (no dunk/and1 imputation); missing heave z renormalizes among available components
- **Zones:** five BBR range shares + derived corner3; era-adjust by `[season, pos]` with season fallback
- **Manifest:** `feature_columns` unchanged (11); `alchemy_feature_columns` = 11 core + `showman_z` + 6 zone z

## Test results

```bash
cd GoatProject-data && GOAT_ROOT=.. PYTHONPATH=src python3.11 -m pytest tests/ -q
```

**20 passed** in ~218s (2026-06-21)

## Blockers / notes for orchestrator

1. **`plans/handoffs/unit-001-spec.yaml` not found** — implemented from `domain-decisions.md`, `architecture-blueprint.md`, and user task spec.
2. **`config_hashes` in manifest** does not yet include `showman.yaml` / `scoring_zones.yaml` (out of scoped files: `config.py`).
3. **`load_player_totals_seasons`** added to `load.py` (not explicitly listed) for FGA denominator; no separate Per Game loader.
4. Downstream units (`GoatProject-modeling` combine cache, `GoatProject-viz` alchemy page) remain out of scope.

## Verification snapshot

- `manifest.feature_columns`: 11
- `manifest.alchemy_feature_columns`: 18
- `career_vectors.showman_partial` true count: 54
