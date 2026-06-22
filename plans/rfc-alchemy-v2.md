# RFC: Alchemy v2 — Showman, Shot Zones, Alchemy Lab

**RFC ID:** goat-alchemy-v2  
**Date:** 2026-06-21  
**Status:** Accepted

## Goal

Extend GoatProject alchemy from R¹¹ to R¹⁸ with showman excitement score and favorite scoring zones; move alchemy interaction to a dedicated **Alchemy Lab** page with α slider, math explainer, and PC-lerp animation.

## Constraints

- Do not modify core 11-dim ranking geometry or publish-gate baseline.
- Static HTML outputs only (no new APIs or deployment).
- Preserve epistemic disclaimers; never caption alchemy discovery as GOAT rank.
- Python 3.11, existing pytest patterns, worktree layout.

## Out of scope

- Highlight views, social metrics, live shot-chart APIs
- α beyond [0,1] or non-linear blend operators
- Inline alchemy in `embed_3d.html`
- Adding showman/zones to L2/Mahalanobis/PCA scores

## Success metrics

- [ ] All 100 allowlist players have `showman_z` + 6 zone z-columns in `career_vectors.parquet`
- [ ] `alchemy_cache.json` schema v2.0.0, 18 dimensions, config-hash invalidates v1
- [ ] `alchemy.html` functional: pickers, α slider, math panel, lerp + skip, NN highlight
- [ ] `embed_3d.html` has no inline alchemy when disabled
- [ ] `./run.sh` green; data/modeling/viz pytest suites pass
- [ ] MATHS.md §13 + ARCHITECTURE.md §9.10 updated

## Risk register

| Risk | Level | Mitigation |
|------|-------|------------|
| Pre-1979 showman bias | 2 | Reweight + partial badge |
| PCA display ≠ R¹⁸ NN | 2 | Dual labeling in UI |
| Cache bloat in HTML | 1 | gzip-friendly JSON; monitor size |
| Worktree merge conflicts | 2 | Serial merge queue per board |
