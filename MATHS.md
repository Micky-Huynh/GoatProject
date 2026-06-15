# Mathematics of the GOAT Stat-Space Model

This document explains **how numbers are produced** in GoatProject: from raw season rows to rankings, PCA maps, and the composite GOAT index. For usage instructions see `README.md`; for system design see `ARCHITECTURE.md`.

---

## 1. Pipeline overview

Each player is represented by a **career vector** \(\mathbf{x} \in \mathbb{R}^{d}\) with \(d = 11\) era-adjusted z-scored features.

```text
Season rows (full league)
    → era-adjusted z-scores per (season, position) group
    → unweighted mean across seasons → career vector x
    → distances, PCA, playoff layer, composite index
```

The **allowlist** (100 curated players) is filtered *after* league-wide era adjustment, so z-scores are not recomputed only among legends.

---

## 2. Feature vector

Raw features come from `config/features.yaml` (mostly `Advanced.csv`). Each feature \(f\) has an **orientation** \(\omega_f \in \{+1, -1\}\):

\[
x_f^{\text{raw}} = \omega_f \cdot \text{stat}_f
\]

Turnover rate uses \(\omega = -1\) (lower turnovers are better). Features marked `exclude_when_pre_three_point_line` are set to missing for designated pre-1979 players before z-scoring.

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

For each season row, each feature is converted to a within-group z-score. Primary grouping is **(season, position)** with fallback to **season-only** when group size \(< 30\) (`config/pipeline.yaml`).

For feature \(f\) in group \(g\):

\[
z_{f} = \frac{x_f^{\text{raw}} - \mu_{f,g}}{\sigma_{f,g}}
\]

where \(\mu_{f,g}, \sigma_{f,g}\) are the mean and (population) standard deviation over all qualified season rows in that group.

**Career aggregation** (`aggregate_career_vectors`):

\[
\bar{z}_{f}^{(\text{player})} = \frac{1}{N} \sum_{\text{seasons } s} z_{f,s}
\]

- \(N\) = count of seasons with \(\geq 200\) minutes (not minute-weighted).
- Missing feature dimensions after aggregation are imputed as **0** (neutral = league mean in z-space).

The career vector is:

\[
\mathbf{x} = (\bar{z}_1, \bar{z}_2, \ldots, \bar{z}_{11})^\top
\]

---

## 4. Distance scores (geometry in stat space)

All three scores use the same \(\mathbf{x}\) but measure “how extreme” the profile is in different geometries. **Lower rank** = smaller distance (closer to the origin in that metric). These are **not** impact rankings.

### 4.1 Euclidean (L2) norm

\[
\text{score\_l2} = \|\mathbf{x}\|_2 = \sqrt{\sum_{j=1}^{d} x_j^2}
\]

Treats every dimension as equally important and uncorrelated.

### 4.2 Mahalanobis distance

Let \(\Sigma\) be the **league career covariance** matrix over the same \(d\) features (regularized by \(\varepsilon I\)):

\[
\text{score\_mahalanobis} = \sqrt{\mathbf{x}^\top \Sigma^{-1} \mathbf{x}}
\]

Down-weights directions where many players vary together (e.g. correlated impact stats).

### 4.3 PCA-whitened L2

PCA is fit on **full-league** career vectors (not just the allowlist).

1. Center: \(\mathbf{X}_c = \mathbf{X} - \boldsymbol{\mu}\)
2. SVD: \(\mathbf{X}_c = \mathbf{U} \mathbf{S} \mathbf{V}^\top\)
3. Keep the smallest \(k\) components such that cumulative explained variance \(\geq 0.90\) (currently \(k = 6\)).
4. Project: \(\mathbf{p}_i = \mathbf{x}_i^\top \mathbf{V}_{1:k}^\top\)
5. Whiten: \(\tilde{p}_{ij} = p_{ij} / \sqrt{\lambda_j}\) where \(\lambda_j\) is explained variance along PC\(j\).
6. Score:

\[
\text{score\_pca\_whitened\_l2} = \|\tilde{\mathbf{p}}\|_2
\]

**Interpretation:** distance from the multivariate center in a rotated, variance-normalized space. High = unusual multi-stat profile; low = compact / near-average across PCs. **Not** the same as “best player.”

---

## 5. Principal component analysis (maps)

### Fitting

- **Training set:** all full-league career vectors (same \(d\) features).
- **Method:** PCA via SVD on centered data (same routine as §4.3).
- **Outputs:** `pca_coordinates.csv`, `pca_loadings.csv`, `pca_explained_variance.json`.

### Projection (allowlist players)

\[
\text{PC}_m^{(\text{player})} = (\mathbf{x} - \boldsymbol{\mu})^\top \mathbf{v}_m
\]

where \(\mathbf{v}_m\) is the \(m\)-th principal axis (row of \(\mathbf{V}\)).

### Current variance split (approximate)

| Component | Share of variance | Rough interpretation (from loadings) |
|-----------|-------------------|--------------------------------------|
| **PC1** | ~38% | Overall impact (BPM, VORP, PER, WS, usage, assists) |
| **PC2** | ~16% | Style / spacing (3PA rate, turnovers, blocks) |
| **PC3** | ~12% | Playmaking vs rim protection |
| **PC1 + PC2** | ~54% | Plane used by the **2D scatter** |

PC2 and PC3 are **style** axes, not universal “better/worse.”

---

## 6. Overall impact (3D crown)

Separate from PCA distance. Defined in `config/viz.yaml` → `skill_aspects.overall`:

\[
\text{impact\_z} = \frac{1}{4}\bigl(\bar{z}_{\text{bpm}} + \bar{z}_{\text{vorp}} + \bar{z}_{\text{per}} + \bar{z}_{\text{ws}}\bigr)
\]

**Gold crown (interactive 3D):** player with maximum `impact_z` among **currently visible** checkboxes. Championships do not enter this formula.

**Orb size** scales linearly with `impact_z` across the pool (larger = higher impact).

---

## 7. Playoff and championship layer

Built in `GoatProject-data` from finals results + team-season strength (team-level PCA on SRS, ratings, pace, shooting splits, etc.).

Per player-season on a playoff team:

- **Ring credit** — base + underdog bonus when team strength index \(< 0\)
- **Finals loss debit** — base + favorite penalty when team strength \(> 0\)
- **Depth score** — ring / finals / playoff-only weights, adjusted for underdog runs

Aggregated per career:

| Field | Meaning |
|-------|---------|
| `championships` | Count of title seasons |
| `championship_net` | \(\sum \text{ring credit} - \sum \text{finals loss debit}\) |
| `playoff_performance` | Mean depth score per playoff season |
| `max_consecutive_championships` | Longest back-to-back title streak |
| `repeat_titles_score` | Rings + consecutive bonuses + dynasty bonus (below) |

### Repeated titles score

From `config/playoffs.yaml` → `repeat_titles`:

\[
\text{repeat\_titles\_score} = R + \sum_{\text{streaks}} (L - 1) \cdot b + \mathbb{1}[\max\_\text{streak} \geq 3] \cdot B
\]

- \(R\) = ring count  
- \(L\) = length of each consecutive title streak  
- \(b = 0.75\) = `consecutive_bonus_per_ring`  
- \(B = 1.5\) = `dynasty_bonus` when max streak \(\geq 3\)

Example: six rings in two 3-peats → \(6 + 2(0.75) + 2(0.75) + 1.5 = 10.5\). One ring with no streak → \(1.0\).

---

## 8. Clutch / consensus adjustment

Penalizes players whose **stat dominance** exceeds **playoff success + peer recognition**.

Stat dominance (z-scored across allowlist):

\[
\text{stat\_outlier\_z} = z\!\left(\frac{1}{4}(\bar{z}_{\text{bpm}}+\bar{z}_{\text{vorp}}+\bar{z}_{\text{per}}+\bar{z}_{\text{ws}})\right)
\]

Playoff success (per player, then z-scored):

\[
\text{playoff\_success} = 1.25 \cdot \text{playoff\_performance} + 2.0 \cdot \text{championships} + 0.75 \cdot \text{finals\_appearances} - 0.35 \cdot \text{finals\_losses}
\]

Consensus:

\[
\text{consensus} = 3.0 \cdot \text{mvp\_peak} + 0.8 \cdot \text{all\_nba\_first\_count}
\]

Penalty (only when stats run ahead of results):

\[
\text{clutch\_gap} = \max\bigl(0,\; \text{stat\_outlier\_z} - z(\text{playoff\_success}) - 0.45 \cdot z(\text{consensus})\bigr)
\]

\[
\text{clutch\_penalty} = 0.55 \cdot \text{clutch\_gap}
\]

---

## 9. Composite GOAT index (bar chart)

\[
\text{score\_goat\_index} = 1.0 \cdot \text{score\_pca\_whitened\_l2} - 0.35 \cdot \text{championship\_net} + 0.45 \cdot \text{clutch\_penalty}
\]

**Lower is better** on the bar chart. Weights from `config/playoffs.yaml` → `goat_index`.

This mixes geometry (PCA distance), titles (net credit), and the clutch tax — so leaders on pure impact (e.g. Jokić) are not automatically #1 here.

---

## 10. Cosine similarity

For allowlist players, career vectors are L2-normalized:

\[
\hat{\mathbf{x}}_i = \frac{\mathbf{x}_i}{\|\mathbf{x}_i\|_2}
\]

\[
\text{similarity}(i, j) = \hat{\mathbf{x}}_i^\top \hat{\mathbf{x}}_j \in [-1, 1]
\]

Used for the **similarity heatmap** (play-style proximity, not greatness).

---

## 11. What each visualization encodes

| Artifact | Math object | Interactive? |
|----------|-------------|--------------|
| **2D PCA scatter** | \((\text{PC1}, \text{PC2})\) | No — static PNG |
| **3D embed** | \((\text{PC1}, \text{PC2}, \text{PC3})\) mapped to display cube; crown = max impact_z in selection | Yes |
| **Bar chart** | `score_goat_index` | No |
| **Heatmap** | Cosine similarity matrix | No |

See `README.md` → **Visualization guide** for how to read the 2D and 3D plots.

---

## 12. Important limitations (mathematical, not bugs)

1. **Correlated impact stats** — BPM, VORP, PER, WS overlap; PCA and Mahalanobis partially address this, impact_z does not deduplicate.
2. **Career mean ≠ peak** — one elite season is averaged with many good ones.
3. **Neutral imputation** — missing eras (e.g. pre-3PT line) become \(z = 0\), pulling vectors toward the center.
4. **Curated cohort** — ranks are within 100 selected players, not all NBA history.
5. **Multiple valid orderings** — impact, titles, geometry, and composite index optimize different objectives.

No single scalar is “the” GOAT; the model exposes **which question each number answers**.
