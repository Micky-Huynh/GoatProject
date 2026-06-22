# ADR: Alchemy Mode — Vector Space + Combine Operator

**Status:** Accepted  
**Date:** 2026-06-21  
**Plan step:** 1  
**Supersedes:** R¹¹-only alchemy (cache schema `1.0.0`)

## Decision

Two-layer model:

1. **Ranking geometry** — ambient **V_rank = R^11** (`feature_columns`; §7.0.1 axioms hold for core stats).
2. **Alchemy operators** — extended **V_alchemy = R^18** (`alchemy_feature_columns` = 11 core + showman + 6 zone z) with game operators **C** (blend) and **D** (nearest neighbor).

Showman and shot zones are **alchemy-only**; they do not enter L2, Mahalanobis, PCA-whitened L2, or `score_goat_index`.

See `goat_model/combine.py`, `config/alchemy.yaml`, `config/showman.yaml`, `config/scoring_zones.yaml`.

## Axioms

| Layer | Closure under + |
|-------|-----------------|
| V_alchemy = R^18 | pass |
| V_rank = R^11 (ranking subset) | pass |
| Player set E_allow | fail |
| C(u,v) in V_alchemy | pass; not a real player id |

## Operators

- **C(u,v) = α·u + (1−α)·v** — α from Alchemy Lab slider (default 0.5)
- **D(w) = argmin_{p∈E} ‖w − p‖₂** in R^18

**Display vs distance:** 3D orb positions use PCA of 11-dim core; NN L2 uses full 18-dim alchemy vector.

## Forbidden

- Do not claim player merge is vector addition on the player set or equals GOAT rank.
- Do not add showman or zone columns to `feature_columns` or ranking scores.

## Acceptance

- [x] Axioms table (R^18 alchemy; R^11 ranking unchanged)
- [x] C and D defined in code
- [x] Epistemic rules match ARCHITECTURE §9.10
- [x] Partial showman reweight documented (`showman_partial`)
- [x] Alchemy Lab at `alchemy.html`; inline alchemy disabled (`alchemy_inline: false`)
