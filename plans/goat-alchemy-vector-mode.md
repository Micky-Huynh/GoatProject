# ADR: Alchemy Mode — Vector Space + Combine Operator

**Status:** Accepted  
**Date:** 2026-06-21  
**Plan step:** 1  

## Decision

Two-layer model: ambient **V = R^11** (8 axioms hold) + game operators **C** (blend) and **D** (nearest neighbor). See `goat_model/combine.py` and `config/alchemy.yaml`.

## Axioms

| Layer | Closure under + |
|-------|-----------------|
| V = R^11 | pass |
| Player set E_allow | fail |
| C(u,v) in V | pass; not a real player id |

## Forbidden

Do not claim player merge is vector addition on the player set or equals GOAT rank.

## Acceptance

- [x] Axioms table
- [x] C and D defined in code
- [x] Epistemic rules match ARCHITECTURE
