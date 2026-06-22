# Unit-003a Handoff: scene_shared + alchemy_page Scaffold

**Worker:** unit-003a  
**Date:** 2026-06-21  
**Status:** Complete

## Summary

Extracted shared Three.js scene helpers into `scene_shared.py`, added standalone `alchemy.html` via `alchemy_page.py`, and disabled inline alchemy in `embed_3d.html` when `alchemy_inline: false`. Alchemy Lab includes searchable A/B pickers, α slider, collapsible math panel, ghost-orb PC-lerp animation with skip/snap, and a result panel (discovery label, L2 in R^n, partial badge).

## Files changed

### Config (main worktree)
- `config/viz.yaml` — `alchemy_inline: false`, `alchemy_page.enabled: true`

### Viz (`GoatProject-viz`)
- `src/goat_viz/scene_shared.py` — theme, player payload (`z_vec` from manifest `alchemy_feature_columns` when available), Three.js JS snippets (scene bootstrap, grid, resize, orb factory, render loop)
- `src/goat_viz/alchemy_page.py` — renders `output/alchemy.html`
- `src/goat_viz/alchemy_js.py` — split inline vs page JS; α-aware blend lookup, localStorage + server cache stub, PC-lerp animation, skip mode
- `src/goat_viz/embed_3d.py` — uses `scene_shared`; omits alchemy toggle/click handler when `alchemy_inline` false
- `src/goat_viz/render.py` — builds alchemy page; links from `index.html`
- `tests/test_viz.py` — asserts `alchemy.html` exists; embed has no alchemy toggle when disabled

## Behavior notes

- **Player payload:** `z_vec` built from `manifest.alchemy_feature_columns` when present in `career_vectors`; falls back to all `*_z` columns. Includes `showman_partial` when column exists.
- **Blend:** `C(u,v) = α·u + (1−α)·v`; cache key includes α. Server cache read from `alchemy_cache.json` entries when present (stub until unit-002).
- **Display vs distance:** Ghost orb animates along PCA 3D positions; NN L2 computed in full alchemy vector space (dim from manifest or 18 default).
- **Inline alchemy:** Removed from explorer UI when `alchemy_inline: false` (default). CSS for toggle may remain but button/handler omitted.

## Test results

```bash
cd GoatProject-viz && GOAT_ROOT=.. PYTHONPATH=src python3.11 -m pytest tests/test_viz.py -q
```

**3 passed** (2026-06-21)

## Demo

```bash
cd GoatProject && ./run.sh   # or run_viz from GoatProject-viz
open GoatProject-viz/output/index.html    # link → Alchemy Lab
open GoatProject-viz/output/alchemy.html  # pick A + B, α slider, blend
```

## Blockers / notes for downstream

1. **unit-002 (alchemy cache):** Client-side NN + localStorage stub works; replace with full `alchemy_cache.json` pair entries when modeling worktree merges.
2. **Manifest on main** may not yet expose `alchemy_feature_columns`; viz falls back to 11-dim `_z` columns until unit-001 data lands on main.
3. **Zone charts** in result panel deferred — scaffold shows discovery + L2 + partial badge only.
4. **config/alchemy.yaml** on main still references R^11 disclaimer; page math panel labels R^18 when manifest dim known.
