# Mathematics of the GOAT Stat-Space Model

This document explains **how numbers are produced** in GoatProject: from raw season rows to rankings, PCA maps, and the composite GOAT index. For usage instructions see `README.md`; for system design see `ARCHITECTURE.md`.

---

## 1. Pipeline overview

Each player is represented by a **career vector** $\mathbf{x} \in \mathbb{R}^{d}$ with $d = 11$ era-adjusted z-scored features.

```text
Season rows (full league)
    → era-adjusted z-scores per (season, position) group
    → unweighted mean across seasons → career vector x
    → distances, PCA, playoff layer, composite index
```

The **allowlist** (100 curated players) is filtered *after* league-wide era adjustment, so z-scores are not recomputed only among legends.

---

## 2. Feature vector

Raw features come from `config/features.yaml` (mostly `Advanced.csv`). Each feature $f$ has an **orientation** $\omega_f \in \{+1, -1\}$:

$$x_f^{\mathrm{raw}} = \omega_f \cdot \mathrm{stat}_f$$

Turnover rate uses $\omega = -1$ (lower turnovers are better). Features marked `exclude_when_pre_three_point_line` are set to missing for designated pre-1979 players before z-scoring.

**The 11 dimensions:**

| Feature | Meaning (higher oriented = better) |
|---------|----------------------------------|
| `bpm_z` | Box plus/minus |
| `vorp_z` | Value over replacement |
| `per_z` | Player efficiency rating |
| `ws_z` | Win shares |
| `ts_percent_z` | True shooting |
| `usg_percent_z` | Usage |
| `ast_percent_z` | Assist rate |
| `stl_percent_z` | Steal rate |
| `blk_percent_z` | Block rate |
| `tov_percent_z` | Turnover rate (inverted) |
| `x3p_ar_z` | 3-point attempt rate |

---

## 3. Era adjustment (z-scores)

For each season row, each feature is converted to a within-group z-score. Primary grouping is **(season, position)** with fallback to **season-only** when group size $< 30$ (`config/pipeline.yaml`).

For feature $f$ in group $g$:

$$z_{f} = \frac{x_f^{\mathrm{raw}} - \mu_{f,g}}{\sigma_{f,g}}$$

where $\mu_{f,g}, \sigma_{f,g}$ are the mean and (population) standard deviation over all qualified season rows in that group.

**Career aggregation** (`aggregate_career_vectors`):

$$\bar{z}_{f}^{(\mathrm{player})} = \frac{1}{N} \sum_{\mathrm{seasons} \, s} z_{f,s}$$

- $N$ = count of seasons with $\geq 200$ minutes (not minute-weighted).
- Missing feature dimensions after aggregation are imputed as **0** (neutral = league mean in z-space).

The career vector is:

$$\mathbf{x} = (\bar{z}_1, \bar{z}_2, \ldots, \bar{z}_{11})^\top$$

---

## 4. Distance scores (geometry in stat space)

All three scores use the same $\mathbf{x}$ but measure "how extreme" the profile is in different geometries. **Lower rank** = smaller distance (closer to the origin in that metric). These are **not** GOAT ranks by themselves; see §9.

### 4.1 Euclidean (L2) norm

$$\mathrm{score} = \|\mathbf{x}\|_2 = \sqrt{\sum_{j=1}^{d} x_j^2}$$

Treats every dimension as equally important and uncorrelated.

### 4.2 Mahalanobis distance

Let $\Sigma$ be the **league career covariance** matrix over the same $d$ features (regularized by $\varepsilon I$):

$$\mathrm{score} = \sqrt{\mathbf{x}^\top \Sigma^{-1} \mathbf{x}}$$

Down-weights directions where many players vary together (e.g. correlated impact stats).

### 4.3 PCA-whitened L2

PCA is fit on **full-league** career vectors (not just the allowlist).

1. Center: $\mathbf{X}_c = \mathbf{X} - \boldsymbol{\mu}$
2. SVD: $\mathbf{X}_c = \mathbf{U} \mathbf{S} \mathbf{V}^\top$
3. Keep the smallest $k$ components such that cumulative explained variance $\geq 0.90$ (currently $k = 6$).
4. Project: $\mathbf{p}_i = \mathbf{x}_i^\top \mathbf{V}_{1:k}^\top$
5. Whiten: $\tilde{p}_{ij} = p_{ij} / \sqrt{\lambda_j}$ where $\lambda_j$ is explained variance along PC$_j$.
6. Score:

$$\mathrm{score} = \|\tilde{\mathbf{p}}\|_2$$

**Interpretation:** distance from the multivariate center in a rotated, variance-normalized space. High = unusual multi-stat profile; low = compact / near-average across PCs. **Not** the same as "being impactful" (see §6).

---

## 5. Principal component analysis (maps)

### Fitting

- **Training set:** all full-league career vectors (same $d$ features).
- **Method:** PCA via SVD on centered data (same routine as §4.3).
- **Outputs:** `pca_coordinates.csv`, `pca_loadings.csv`, `pca_explained_variance.json`.

### Projection (allowlist players)

$$\mathrm{PC}_m^{(\mathrm{player})} = (\mathbf{x} - \boldsymbol{\mu})^\top \mathbf{v}_m$$

where $\mathbf{v}_m$ is the $m$-th principal axis (row of $\mathbf{V}$).

### Current variance split (approximate)

| Component | Share of variance | Rough interpretation (from loadings) |
|-----------|-------------------|--------------------------------------|
| **PC1** | ~38% | Overall impact (BPM, VORP, PER, WS, usage, assists) |
| **PC2** | ~16% | Style / spacing (3PA rate, turnovers, blocks) |
| **PC3** | ~12% | Playmaking vs rim protection |
| **PC1 + PC2** | ~54% | Plane used by the **2D scatter** |

PC2 and PC3 are **style** axes, not universal "better/worse."

---

## 6. Overall impact (3D crown)

Separate from PCA distance. Defined in `config/viz.yaml` → `skill_aspects.overall`:

$$\mathrm{impact} = \frac{1}{4}\bigl(\bar{z}_{\mathrm{bpm}} + \bar{z}_{\mathrm{vorp}} + \bar{z}_{\mathrm{per}} + \bar{z}_{\mathrm{ws}}\bigr)$$

**Gold crown (interactive 3D):** player with maximum `impact_z` among **currently visible** checkboxes. Championships do not enter this formula.

**Orb size** scales linearly with `impact_z` across the pool (larger = higher impact).

---

## 7. Playoff and championship layer

Built in `GoatProject-data` from finals results + team-season strength (team-level PCA on SRS, ratings, pace, shooting splits, etc.).

Per player-season on a playoff team:

- **Ring credit** — base + underdog bonus when team strength index $< 0$
- **Finals loss debit** — base + favorite penalty when team strength $> 0$
- **Depth score** — ring / finals / playoff-only weights, adjusted for underdog runs

Aggregated per career:

| Field | Meaning |
|-------|---------|
| `championships` | Count of title seasons |
| `championship_net` | $\sum \mathrm{ring\ credit} - \sum \mathrm{finals\ loss\ debit}$ |
| `playoff_performance` | Mean depth score per playoff season |
| `max_consecutive_championships` | Longest back-to-back title streak |
| `repeat_titles_score` | Rings + consecutive bonuses + dynasty bonus (below) |

### Repeated titles score

From `config/playoffs.yaml` → `repeat_titles`:

$$\mathrm{repeat\_titles} = R + \sum_{\mathrm{streaks}} (L - 1) \cdot b + \mathbb{1}[\mathrm{max\_streak} \geq 3] \cdot B$$

- $R$ = ring count  
- $L$ = length of each consecutive title streak  
- $b = 0.75$ = `consecutive_bonus_per_ring`  
- $B = 1.5$ = `dynasty_bonus` when max streak $\geq 3$

Example: six rings in two 3-peats → $6 + 2(0.75) + 2(0.75) + 1.5 = 10.5$. One ring with no streak → $1.0$.

---

## 8. Clutch / consensus adjustment

Penalizes players whose **stat dominance** exceeds **playoff success + peer recognition**.

Stat dominance (z-scored across allowlist):

$$\mathrm{stat\_outlier} = z\!\left(\frac{1}{4}(\bar{z}_{\mathrm{bpm}}+\bar{z}_{\mathrm{vorp}}+\bar{z}_{\mathrm{per}}+\bar{z}_{\mathrm{ws}})\right)$$

Playoff success (per player, then z-scored):

$$\mathrm{playoff\_success} = 1.25 \cdot \mathrm{playoff\_perf} + 2.0 \cdot \mathrm{championships} + 0.75 \cdot \mathrm{finals\_apps} - 0.35 \cdot \mathrm{finals\_losses}$$

Consensus:

$$\mathrm{consensus} = 3.0 \cdot \mathrm{mvp\_peak} + 0.8 \cdot \mathrm{all\_nba\_first\_count}$$

Penalty (only when stats run ahead of results):

$$\mathrm{clutch\_gap} = \max\bigl(0,\; \mathrm{stat\_outlier} - z(\mathrm{playoff\_success}) - 0.45 \cdot z(\mathrm{consensus})\bigr)$$

$$\mathrm{clutch\_penalty} = 0.55 \cdot \mathrm{clutch\_gap}$$

---

## 9. Composite GOAT index (bar chart)

$$\mathrm{score} = 1.0 \cdot \mathrm{pca\_whitened} - 0.35 \cdot \mathrm{champ\_net} + 0.45 \cdot \mathrm{clutch\_penalty}$$

**Lower is better** on the bar chart. Weights from `config/playoffs.yaml` → `goat_index`.

This mixes geometry (PCA distance), titles (net credit), and the clutch tax — so leaders on pure impact (e.g. Jokić) are not automatically #1 here.

---

## 10. Cosine similarity

For allowlist players, career vectors are L2-normalized:

$$\hat{\mathbf{x}}_i = \frac{\mathbf{x}_i}{\|\mathbf{x}_i\|_2}$$

$$\mathrm{similarity}(i, j) = \hat{\mathbf{x}}_i^\top \hat{\mathbf{x}}_j \in [-1, 1]$$

Used for the **similarity heatmap** (play-style proximity, not greatness).

---

## 11. What each visualization encodes

| Artifact | Math object | Interactive? |
|----------|-------------|--------------|
| **2D PCA scatter** | $({\mathrm{PC1}}, {\mathrm{PC2}})$ | No — static PNG |
| **3D embed** | $({\mathrm{PC1}}, {\mathrm{PC2}}, {\mathrm{PC3}})$ mapped to display cube; crown = max `impact_z` in selection | Yes |
| **Bar chart** | `score_goat_index` | No |
| **Heatmap** | Cosine similarity matrix | No |

See `README.md` → **Visualization guide** for how to read the 2D and 3D plots.

---

## 12. Section 12 reserved

(Placeholder for future content.)

---

## 13. Alchemy Mode (vector blend + discovery)

Separate from GOAT rank and from §2–§9 ranking geometry. Alchemy uses an **extended** vector space; core rankings stay on the 11-dim `feature_columns` only.

### 13.1 Two vector spaces (do not conflate)

| Space | Dimension | Used for |
|-------|-----------|----------|
| **Ranking geometry** | $\mathbb{R}^{11}$ | L2, Mahalanobis, PCA-whitened L2, `score_goat_index`, 3D orb positions |
| **Alchemy blend + NN** | $\mathbb{R}^{18}$ | Combine $C$, discovery $D$, L2 distance in Alchemy Lab |

Manifest fields: `feature_columns` (11 core) and `alchemy_feature_columns` (18 = 11 core + 7 alchemy-only). Showman and shot zones are **never** added to ranking scores.

**Alchemy extensions (7 dimensions):**

| Column | Meaning |
|--------|---------|
| `showman_z` | Era-adjusted excitement composite (see §13.2) |
| `zone_0_3_z` | Share of FGA from 0–3 ft (z-scored) |
| `zone_3_10_z` | Share from 3–10 ft |
| `zone_10_16_z` | Share from 10–16 ft |
| `zone_16_3p_z` | Share from 16 ft to 3P line |
| `zone_3p_z` | Share from beyond 3P |
| `zone_corner3_z` | Derived corner-3 share (`corner3_of_3pa × 3p_range`) |

Zone z-scores are **independent axes** (not constrained to sum to 1 in z-space). Raw zone shares sum ≈ 1.0 per player-season before z-scoring.

### 13.2 Showman score

Season-level components (era-adjusted z within `(season, position)` groups, same ladder as §3):

| Component | Source | Full weight |
|-----------|--------|-------------|
| Dunk frequency | `Player Play By Play.csv` | 30% |
| And-1 rate (and1 / FGA) | PBP + `Player Totals.csv` | 25% |
| All-Star selection rate | `All-Star Selections.csv` | 25% |
| MVP vote share (peak season) | Award shares | 15% |
| Heave rate (heave / FGA) | PBP + totals | 5% |

Career `showman_z` = weighted mean of available component z-scores (MVP uses peak share, then allowlist z-score).

**Full profile** (all components available):

$$\mathrm{showman} = 0.30\,z_{\mathrm{dunk}} + 0.25\,z_{\mathrm{and1}} + 0.25\,z_{\mathrm{ASG}} + 0.15\,z_{\mathrm{MVP}} + 0.05\,z_{\mathrm{heave}}$$

**Legacy partial profile** (`showman_partial = true`): when any qualifying season lacks reliable dunk or and-1 data (typical pre-1979), **reweight — do not impute**. Dunk and and-1 are excluded; remaining components renormalize to 100%.

| Component | Legacy partial weight |
|-----------|----------------------|
| All-Star rate | 45% |
| MVP share (peak) | 25% |
| Heave rate | 5% (if present; otherwise renormalize among available) |

Partial players never receive imputed dunk/and-1 at $z = 0$. The Alchemy Lab surfaces a `showman_partial` badge when either parent has the flag.

Weights: `config/showman.yaml`. Zones: `config/scoring_zones.yaml`.

### 13.3 Operators

Let $\mathbf{u}, \mathbf{v} \in \mathbb{R}^{18}$ be alchemy career vectors for players A and B. Slider $\alpha \in [0,1]$, $\beta = 1 - \alpha$ (default $\alpha = 0.5$ per `config/alchemy.yaml`).

1. **Combine** — convex blend in $\mathbb{R}^{18}$:

$$C(\mathbf{u}, \mathbf{v}) = \alpha\,\mathbf{u} + \beta\,\mathbf{v}$$

Linear in the ambient space; **not** player addition on the allowlist.

2. **Discovery** — nearest neighbor by L2 in $\mathbb{R}^{18}$:

$$D(\mathbf{w}) = \arg\min_{p \in E_{\mathrm{allow}}} \| \mathbf{w} - \mathbf{z}_p \|_2$$

where $\mathbf{z}_p$ uses `alchemy_feature_columns` only.

### 13.4 Display vs distance (dual labels)

| What | Space | Notes |
|------|-------|-------|
| Orb positions on screen | PCA of **11-dim core** | Same 3D layout as `embed_3d.html` |
| Ghost-orb blend animation | PC-lerp between A and B display positions | ~800 ms; **Skip animation** snaps to result |
| Nearest-neighbor L2 | **18-dim** alchemy vector | Authoritative discovery metric |

UI must label both: animation is honest for convex combination in **display** space; NN distance is computed in **full alchemy** space.

### 13.5 Artifacts and UI

- **Page:** `GoatProject-viz/output/alchemy.html` (Alchemy Lab) — linked from `index.html`
- **Inline alchemy:** disabled in `embed_3d.html` when `alchemy_inline: false` (`config/viz.yaml`)
- **Server cache:** `GoatProject-modeling/output/alchemy_cache.json` (schema `2.0.0`, dim 18)
- **Client cache:** localStorage keyed by sorted player pair + $\alpha$ + config hash

**Not GOAT rank.** Discovery labels the nearest allowlist player to a hypothetical blend — exploratory only.

---

## 14. Important limitations (mathematical, not bugs)

1. **Correlated impact stats** — BPM, VORP, PER, WS overlap; PCA and Mahalanobis partially address this, `impact_z` does not deduplicate.
2. **Career mean ≠ peak** — one elite season is averaged with many good ones.
3. **Neutral imputation** — missing eras (e.g. pre-3PT line) become $z = 0$, pulling vectors toward the center.
4. **Curated cohort** — ranks are within 100 selected players, not all NBA history.
5. **Multiple valid orderings** — impact, titles, geometry, and composite index optimize different objectives.

No single scalar is "the" GOAT; the model exposes **which question each number answers**.
