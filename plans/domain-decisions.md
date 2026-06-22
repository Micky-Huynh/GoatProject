# Domain Decisions — Alchemy v2

**Date:** 2026-06-21  
**Status:** Locked (user + council)

## Facts

- `Player Shooting.csv`, `Player Play By Play.csv`, `All-Star Selections.csv` exist in `GoatProject-data/data/`.
- Current alchemy vector is R¹¹; cache schema `1.0.0` in `combine.py`.
- Core publish gate already fails at 100-player scale (Spearman 0.826) — unrelated to alchemy extensions.
- Pre-1979 players lack reliable dunk/PBP fields in Basketball-Reference exports.

## Assumptions

- Era-adjusted z-scores per zone (independent axes) are acceptable for linear blend operator.
- All-Star selection rate is a valid proxy for legacy "showmanship" when modern excitement proxies are missing.
- PC-lerp between orb positions is an honest visual for convex combination in display space; 18-dim L2 is the authoritative NN metric.
- α ∈ [0,1] with β = 1−α; no normalization of blend vector beyond component-wise linear mix.

## Locked product decisions

| # | Decision |
|---|----------|
| 1 | Showman + shot zones **alchemy-only** — excluded from `feature_columns` / ranking geometry |
| 2 | Alchemy Lab: **α slider** + side panel with math walkthrough |
| 3 | Legacy showmen: **elevated All-Star weight** in partial profile |
| 4 | **PC-lerp animation** + **Skip animation** checkbox for snap |
| 5 | **Reweight, don't impute** missing dunk/and1; `showman_partial=true` badge |

## Showman weights

| Component | Full | Legacy partial |
|-----------|------|----------------|
| Dunk freq | 30% | — |
| And-1 rate | 25% | — |
| All-Star rate | 25% | **45%** |
| MVP share peak | 15% | **25%** |
| Heave rate | 5% | 5% (if present) |

## Open questions

_None — all five council items resolved._

## Falsification / tests

- `test_excitement.py`: partial players never receive imputed dunk/and1 z=0 penalty; weights renormalize to 1.0
- `test_shooting_zones.py`: raw zone shares sum ≈ 1.0 per player-season
- `test_combine.py`: blend_vector length 18; cache hash changes when alchemy columns change
- `test_viz.py`: `alchemy.html` exists; embed_3d has no alchemy toggle when `alchemy_inline: false`
