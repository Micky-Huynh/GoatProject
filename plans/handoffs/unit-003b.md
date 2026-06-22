# Unit-003b Handoff: Alchemy Lab Integrate + Polish

**Worker:** unit-003b  
**Date:** 2026-06-21  
**Status:** Complete

## Summary

Wired `alchemy.html` to the full R¹⁸ server cache (schema v2, inlined at build time), added zone shot-profile mini charts in the result panel, dual geometry labels, live α slider with server-cache fallback, and optional Showman aspect in `embed_3d` profiles when data is present.

## Files changed

### Viz (`GoatProject-viz`)
- `src/goat_viz/scene_shared.py` — zone share constants; manifest helpers; `load_alchemy_meta` exposes `schema_version`, `pca_core_dim`, zone labels, full `cache_entries`; player payload adds `zone_shares`, `showman_z`
- `src/goat_viz/alchemy_js.py` — server cache lookup via `sortedPairKey` (α=0.5); localStorage fallback for other α; zone bar charts (A | blend renormalized | B | nearest); dual-label result copy; α slider live refresh
- `src/goat_viz/alchemy_page.py` — dual-label subtitle/math panel; zone chart CSS
- `src/goat_viz/profiles.py` — optional `showman` aspect when `showman_z` column exists (display only)
- `tests/test_viz.py` — asserts cache wiring, zone charts, dual labels

## Behavior notes

- **Server cache:** 4950 pair entries from `alchemy_cache.json` inlined into `alchemyMeta.cache_entries` at render time; keys are `playerA|playerB` (no α suffix, α=0.5 precomputed).
- **α slider:** At default α (0.5), uses server cache when `config_hash` matches; other α values compute client-side L2 NN with localStorage cache; slider updates result live after first blend.
- **Dual labels:** UI states “Orb positions = PCA(11-dim core); NN distance = L2 in R^18”.
- **Zone charts:** Raw FGA share columns blended with α, renormalized for display; four columns A / Blend / B / Nearest.
- **Showman profile:** Appended to skill aspects in embed when `showman_z` present; not used in ranking geometry.

## Test results

```bash
cd GoatProject-viz && GOAT_ROOT=.. PYTHONPATH=src python3.11 -m goat_viz.run_viz
```

Generated `output/alchemy.html` (~5.5 MB with inlined cache), `embed_3d.html`, `index.html` (2026-06-21)

```bash
cd GoatProject-viz && GOAT_ROOT=.. PYTHONPATH=src python3.11 -m pytest tests/test_viz.py -q
```

**3 passed** (2026-06-21)

## Verification snapshot

| Field | Value |
|-------|-------|
| `alchemyMeta.schema_version` | `2.0.0` |
| `alchemyMeta.config_hash` | `e316a4c1d56b971e` |
| `alchemyMeta.vector_dim` | 18 |
| `alchemyMeta.pca_core_dim` | 11 |
| Inlined cache entries | 4950 |
| Dual labels in subtitle | ✓ |
| `lookupCachedCombine` in page JS | ✓ |
| Showman aspect in embed payload | ✓ |

## Blockers / notes for downstream

1. **unit-004 (main merge):** Viz worktree ready; main may need worktree merge + allowlist regen.
2. **alchemy.html size** — ~5.5 MB due to inlined 4950-entry cache; acceptable for local static hosting; consider lazy-load or external JSON if deployed.
3. **Legacy players** with zero zone shares show “No zone data” bars (pre-1979 shooting gaps).
