# NBA GOAT Ranking System — Architecture (v1)

**Status:** Approved — canonical spec  
**Version:** 1.0.0  
**Approved:** 2026-06-14 (MLE amendments same date)  
**Player pool:** 21 (locked for v1)

**Memory index:** `MEMORY/MEMORY.md`  
**Build plan:** `plans/goat-nba-ranking-system.md`  
**Configuration:** `config/allowlist.yaml` · `config/paths.yaml` · `config/features.yaml` · `config/scoring.yaml` · `config/labels.yaml` · `config/pipeline.yaml` · `config/viz.yaml`

This document is the **single source of truth** for system design. Config YAML files implement parameters defined here; they do not override this spec.

---

## 1. Purpose and scope

### Epistemic status

The NBA GOAT Ranking System v1 produces a **21-player stat-space index** — a reproducible composite ranking over a curated shortlist of all-time candidates. It is **not** a claim of objective all-time GOAT truth, league-wide optimality, or playoff-adjusted greatness (v1).

| Claim | Allowed | Forbidden |
|-------|---------|-----------|
| "Composite index over 21 curated players using era-adjusted advanced stats" | ✅ | |
| "L2 / Mahalanobis norm of oriented career vector in z-scored feature space" | ✅ | |
| "Objective GOAT ranking" / "definitive all-time #1" | | ❌ |
| "League-wide ranking of all NBA players" | | ❌ (v1) |
| "Playoff-adjusted greatness" | | ❌ (deferred v1) |

**Public framing** (from `config/scoring.yaml` → `public_framing`):

- **Index name:** 21-player GOAT stat-space index
- **Required disclaimer:** Curated 21-player composite index; not league-wide or playoff-adjusted (v1). Career index = unweighted mean of era-adjusted seasons (mp ≥ 200), not peak-only.

Every published artifact (HTML, PNG captions, README) must carry the disclaimer. Visualization layout views (PCA scatter, similarity heatmaps) are **exploratory** and must not be presented as the headline rank unless explicitly labeled otherwise (see §9).

### Construct validity

PER, BPM, VORP, and WS measure overlapping latent "overall impact." L2 treats correlated z-features as independent dimensions; Mahalanobis and PCA-whitened L2 answer different geometric questions under the same vector. The index is a **transparent composite**, not a peak-vs-longevity adjudication or causal greatness measure. Sensitivity runs S1–S5 (§7.7) and the publish gate (§8.2) document stability before any public headline.

### In scope (v1)

- Rank **21 curated all-time players** using era-adjusted statistical embeddings.
- **Dual scores:** L2, Mahalanobis, and PCA-whitened L2 computed on every run; **public headline** chosen by publish gate (§8.2).
- **Exploration:** PCA, cosine similarity, vector hybrids, projection residuals.
- **Validation:** XGBoost + SHAP vs MVP vote share and All-NBA labels (sanity check only; §8.3).
- **Presentation:** Static leaderboard, vector-space exploration charts, and social-ready player profiles (see §9).

### Out of scope (v1)

- Playoff stats (no player-level playoff rows in source CSVs).
- League-wide ranking or dynamic pool expansion beyond the allowlist.
- Live data feeds, APIs, or web app deployment.
- Replacing index rank with supervised model output.
- `Per 100 Poss.csv` feature joins (deferred; schema reserved in `features.yaml`).

---

## 2. System map

```mermaid
flowchart TB
  subgraph config [Main repo — config only]
    Allowlist[config/allowlist.yaml]
    Paths[config/paths.yaml]
  end

  subgraph data_layer [GoatProject-data]
    direction TB
    D1[Load raw CSVs]
    D2[Merge + feature select]
    D3[Era adjust — full league z-scores]
    D4[Filter allowlist]
    D5[Aggregate career vectors]
    D6[Build season labels]
    D7[League covariance]
    D1 --> D2 --> D3 --> D4 --> D5
    D2 --> D6
    D5 --> D7
    Proc[(processed/)]
    D5 --> Proc
    D6 --> Proc
    D7 --> Proc
  end

  subgraph model_layer [GoatProject-modeling]
    M1[Dual-score + publish gate]
    M2[Analyze — PCA / cosine / residuals]
    M3[Validate — XGBoost / SHAP]
    M4[Sensitivity S1–S5]
    Out[(output/)]
    M1 --> Out
    M2 --> Out
    M3 --> Out
    M4 --> Out
  end

  subgraph viz_layer [GoatProject-viz]
    V1[Render — read only]
    Html[(output/)]
    V1 --> Html
  end

  Allowlist --> D4
  Paths --> data_layer
  Paths --> model_layer
  Paths --> viz_layer
  Proc --> M1
  Proc --> M2
  Proc --> M3
  Out --> V1
  Proc -. manifest .-> M1
```

**Rule:** Dependencies flow downward only. Viz never reads raw CSVs. Modeling never re-z-scores. Only the data layer writes `processed/`.

**Primary rank:** Evidence-gated headline score (`score_l2` or `score_mahalanobis` per publish gate). XGBoost and PCA distances are **never** the public headline rank.

---

## 3. Component responsibilities

Each component must pass the one-sentence test (no "and" joining unrelated jobs).

| Component | Worktree | Owns | Must not |
|-----------|----------|------|----------|
| **Allowlist config** | main | Who is in the 21-player pool | Resolve IDs, transform stats |
| **Loader** | data | Read Kaggle CSVs into typed frames | Z-score, rank, plot |
| **Merger** | data | Join on `(player_id, season)`; select features | Filter allowlist before z-score |
| **Era adjuster** | data | Z-score by `(season, position)` on **full league** | Use allowlist-only baselines |
| **Aggregator** | data | Career vector = mean of season vectors | Train ML models |
| **Label builder** | data | `season_labels.parquet` from award CSVs | Predict or rank |
| **Covariance builder** | data | `league_career_covariance.npy` + manifest stats | Score or rank |
| **Pipeline orchestrator** | data | Run stages; write `manifest.json` | Contain business logic inline |
| **Ranker** | modeling | `goat_rankings.csv`; dual scores + publish gate | Read raw CSVs; overwrite manifest |
| **Analyzer** | modeling | PCA, similarity, uniqueness artifacts + `pca_explained_variance.json` | Change canonical rank |
| **Validator** | modeling | Season-level sanity metrics per §8.3; SHAP diagnostics | Overwrite primary rank or publish gate |
| **Sensitivity runner** | modeling | `sensitivity_report.json` (S1–S5) | Block publish without recording results |
| **Renderer** | viz | HTML, PNG posts, charts from artifacts only | Process data; read raw CSVs |

---

## 4. State ownership

| State | Writer | Readers | Mutable by others? |
|-------|--------|---------|-------------------|
| Raw CSVs | external (Kaggle) | data Loader | No |
| `config/*.yaml` | human / main branch | all worktrees (read) | No |
| `processed/*` | data pipeline | modeling, viz (read-only) | No |
| `manifest.json` | data pipeline | all downstream | No |
| `output/goat_rankings.csv` | Ranker only | viz, Validator (read) | No |
| `output/sensitivity_report.json` | Sensitivity runner | viz (gate) | No |
| `output/*` (analysis) | Analyzer, Validator | viz | No |
| `viz/output/*` | Renderer | human | No |

**Invariant:** Exactly one writer per artifact. Violations are architecture bugs, not style issues.

---

## 5. Configuration

### 5.1 Allowlist — `config/allowlist.yaml`

Human-editable names only (21 players locked for v1). Pipeline resolves to `player_id` at run time and records results in `manifest.json`. Do not duplicate the player list elsewhere.

**Join key:** `player_id` from `Player Career Info.csv` / `Player Season Info.csv`. Display names are labels only (Unicode-safe).

**Pre-three-point-line flag:** Kareem Abdul-Jabbar and Moses Malone (`pre_three_point_line_players` in allowlist). For seasons before 1979-80, `x3p_ar` is excluded from the oriented vector per `features.yaml`.

### 5.2 Paths — `config/paths.yaml`

Single definition of cross-worktree paths. Override via `GOAT_ROOT` env var (optional; `config/pipeline.yaml`).

### 5.3 Features — `config/features.yaml`

Feature catalog: source CSV, column name, orientation (`+1` higher-is-better, `−1` lower-is-better), and exclusion flags. Pipeline applies orientation before career aggregation. v1: **Advanced.csv only**; `per_100_features: []`.

### 5.4 Scoring — `config/scoring.yaml`

Score definitions (L2, Mahalanobis, PCA-whitened L2), publish gate thresholds, S5 collinearity block (`s5_collinearity_block: [bpm, vorp, ws]`), and `public_framing` disclaimer text.

### 5.5 Labels — `config/labels.yaml`

Validator label contracts: `mvp_vote_share`, `all_nba_first`, `all_nba_any` with source files, filters, and defaults. Labels feed the validator only.

### 5.6 Visualization — `config/viz.yaml`

Theme, export DPI, social aspect ratios, pizza/radar feature subsets, optional UMAP flag, and caption strings. See §9.

---

## 6. Data contracts

All downstream code depends on **`manifest.json`**, not on implicit parquet columns.

### 6.1 `processed/manifest.json`

Pipeline provenance and QA metrics. Required fields:

```json
{
  "schema_version": "1.0.0",
  "pipeline_version": "1.0.0",
  "created_at": "<ISO-8601 UTC>",
  "player_count": 21,
  "players": [
    {
      "player_id": "jordami01",
      "display_name": "Michael Jordan",
      "season_count": 15
    }
  ],
  "artifacts": {
    "season_vectors": "processed/season_vectors.parquet",
    "career_vectors": "processed/career_vectors.parquet",
    "season_labels": "processed/season_labels.parquet",
    "league_career_covariance": "processed/league_career_covariance.npy"
  },
  "feature_columns": ["bpm_z", "vorp_z", "per_z"],
  "metadata_columns": ["player_id", "season", "position", "age", "pre_three_point_line"],
  "era_adjustment": {
    "method": "z_score",
    "group_by": ["season", "pos"],
    "baseline_population": "full_league",
    "fallback_group_count": 0
  },
  "missing_data": {
    "dropped_season_count": 0,
    "dropped_low_minutes": 0,
    "dropped_missing_core": 0
  },
  "config_hashes": {
    "pipeline.yaml": "sha256:...",
    "features.yaml": "sha256:...",
    "labels.yaml": "sha256:...",
    "allowlist.yaml": "sha256:..."
  },
  "raw_csv_checksums": {
    "Advanced.csv": "sha256:...",
    "Player Season Info.csv": "sha256:..."
  },
  "feature_correlation_max": 0.0,
  "covariance_condition_number": 0.0,
  "covariance_player_count": 0,
  "label_stats": {
    "mvp_rows": 0,
    "all_nba_first_rows": 0,
    "all_nba_any_rows": 0,
    "seasons_labeled": 0
  }
}
```

Implementations may include additional diagnostic fields; the fields above are **required** for v1 compliance. Increment `schema_version` if `feature_columns` or grain changes.

### 6.2 `processed/season_vectors.parquet`

**Grain:** one row per `(player_id, season)` for allowlist players only (after full-league era adjustment and filter).

| Column kind | Examples | Notes |
|-------------|----------|-------|
| Keys | `player_id`, `season`, `display_name` | Join key |
| Metadata | `position`, `age`, `mp`, `pre_three_point_line` | Not in score unless in `feature_columns` |
| Raw features | `bpm`, `vorp`, `per`, `ws`, … | From Advanced.csv |
| Era-adjusted | `*_z` suffix | Listed in manifest `feature_columns` |

**Row filters:** `mp ≥ 200`; drop season if core features missing (§7.3).

### 6.3 `processed/career_vectors.parquet`

**Grain:** one row per `player_id` (21 rows).

| Column kind | Examples |
|-------------|----------|
| Keys | `player_id`, `display_name`, `season_count` |
| Features | Same `feature_columns` as manifest — **unweighted mean** of season oriented z-vectors |

### 6.4 `processed/season_labels.parquet`

**Grain:** one row per `(player_id, season)` per `config/labels.yaml`.

| Column | Source | Use |
|--------|--------|-----|
| `mvp_vote_share` | `Player Award Shares.csv` | Validator primary metric |
| `all_nba_first` | `End of Season Teams.csv` | Validator primary metric |
| `all_nba_any` | All-NBA 1st/2nd/3rd | Secondary |

**Owner:** Label builder in data layer. Validator must not read award CSVs directly.

### 6.5 `output/goat_rankings.csv`

**Writer:** Ranker only.

| Column | Description |
|--------|-------------|
| `player_id`, `display_name` | Identity |
| `score_l2`, `score_mahalanobis`, `score_pca_whitened_l2` | Raw scores (lower = better rank position; sort ascending) |
| `rank_l2`, `rank_mahalanobis`, `rank_pca_whitened_l2` | Rank within 21 for each score |
| `public_headline_score` | `score_l2` or `score_mahalanobis` per publish gate (§8.2) |
| `rank_method_primary` | Score ID used for headline (`l2_career_vector_v1` or `mahalanobis_career_v2`) |

### 6.6 `output/sensitivity_report.json`

**Writer:** Sensitivity runner. Required before any social publish (viz gate).

| Field | Description |
|-------|-------------|
| `baseline` | Baseline score ID (e.g. `l2_career_vector_v1`) |
| `publish_gate_pass` | `bool` — both §8.2 criteria met |
| `publish_gate.spearman_l2_vs_mahalanobis` | Spearman ρ on ranks |
| `publish_gate.top5_overlap` | Overlap count (0–5) |
| `publish_gate.thresholds` | `min_spearman`, `min_top5_overlap` from config |
| `runs.S1_min_minutes` … `runs.S5_collinearity_drop` | Per-run Spearman and/or top-5 overlap vs baseline |
| `runs.*.soft_warning` | Optional flags for S1/S3 soft thresholds |

Illustrative example (compact):

```json
{
  "baseline": "l2_career_vector_v1",
  "publish_gate_pass": true,
  "publish_gate": {
    "spearman_l2_vs_mahalanobis": 0.91,
    "top5_overlap": 5,
    "thresholds": { "min_spearman": 0.85, "min_top5_overlap": 4 }
  },
  "runs": {
    "S5_collinearity_drop": {
      "dropped_features": ["bpm", "vorp", "ws"],
      "spearman_vs_baseline": 0.86
    }
  }
}
```

### 6.7 `output/validation_report.json`

Season-level test metrics (§8.3). Non-gating; must not modify `goat_rankings.csv`.

---

## 7. Processing rules (locked)

### 7.0 Mathematical definition

**Season z-score** (full league, not allowlist), for feature \(j\), season \(s\), position group \(g\):

\[
z_{i,s,j} = \frac{x_{i,s,j} - \mu_{s,g,j}}{\sigma_{s,g,j}}
\]

When \(\sigma_{s,g,j} = 0\), set \(z_{i,s,j} = 0\) and log in manifest/tests.

**Orientation** from `config/features.yaml`:

\[
\tilde{z}_{i,s,j} = o_j \cdot z_{i,s,j}, \quad o_j \in \{+1,-1\}
\]

**Career vector** (seasons with `mp ≥ 200`, unweighted mean):

\[
\bar{z}_{i,j} = \frac{1}{|S_i|}\sum_{s \in S_i} \tilde{z}_{i,s,j}
\]

**Scores** (all computed; headline chosen by publish gate §8.2):

| ID | Formula |
|----|---------|
| `l2_career_vector_v1` | \(\|\bar{z}_i\|_2\) |
| `mahalanobis_career_v2` | \(\sqrt{\bar{z}_i^\top \Sigma_\epsilon^{-1} \bar{z}_i}\) |
| `pca_whitened_l2_v1` | \(\|W_i\|_2\) where \(W_i\) are coordinates on first \(k\) PCs (≥90% cumulative variance) |

\(\Sigma\) is estimated from **full-league career vectors** (same season filter and feature set), with ridge \(\Sigma_\epsilon = \Sigma + \epsilon I\), \(\epsilon\) from `config/scoring.yaml`. **PCA fit and whitening** also use **full-league** career matrices — not the 21-player subset.

### 7.1 Pipeline rules

1. Z-score on **full league** by `(season, position)`, then filter allowlist (never the reverse).
2. Apply feature orientation (`config/features.yaml`) before career aggregation.
3. Kareem + Moses: `pre_three_point_line` for season < 1980; exclude `x3p_ar` per feature flags.
4. **Advanced.csv only for v1** — `Per 100 Poss.csv` deferred per `features.yaml`; `Player Per Game.csv` metadata-only.
5. Career vector = **unweighted** mean of season vectors (`weight_by_minutes: false`).
6. Exclude seasons where `mp < 200` before aggregation (`config/pipeline.yaml`).
7. Drop entire season if `bpm` or `vorp` is NA (`drop_season_if_core_missing`); log counts in manifest `missing_data`.
8. Era fallback ladder when group `n < min_group_n` (30): `(season, pos)` → `(season)`; record `fallback_group_count` in manifest.
9. Write `league_career_covariance.npy`, `feature_correlation_max`, and `covariance_condition_number` to manifest.

Feature set (v1, all from Advanced.csv):

| Feature | Column | Orient |
|---------|--------|--------|
| bpm | bpm | +1 |
| vorp | vorp | +1 |
| per | per | +1 |
| ws | ws | +1 |
| ts_percent | ts_percent | +1 |
| usg_percent | usg_percent | +1 |
| ast_percent | ast_percent | +1 |
| stl_percent | stl_percent | +1 |
| blk_percent | blk_percent | +1 |
| tov_percent | tov_percent | −1 |
| x3p_ar | x3p_ar | +1 (excluded pre-1979 for flagged players) |

### 7.2 Era adjustment — full league before allowlist

**Critical ordering:**

```
WRONG:  filter to 21 → z-score within subset
RIGHT:  z-score on FULL LEAGUE → then filter to 21 → aggregate
```

Without full-league baselines, "era adjustment" collapses to elite peer comparison, compressing cross-era signal and violating this spec.

### 7.3 Missing data policy (MLE amendment)

From `config/pipeline.yaml` → `missing_features`:

| Policy | Value |
|--------|-------|
| Rule | `drop_season_if_core_missing` |
| Core features | `bpm`, `vorp` |
| Logging | `log_dropped_seasons: true` → `missing_data.dropped_season_count` in manifest |

### 7.4 Career aggregation

Unweighted arithmetic mean of season oriented z-vectors per player. Minutes-weighted variant is sensitivity S2 only.

### 7.5 League covariance

Compute Σ from **full-league** career vectors (~3000+ careers). Store condition number and `feature_correlation_max` in manifest. Reject Mahalanobis if cond(Σ_ε) > `max_condition_number` in `scoring.yaml` (default 1e6).

### 7.6 Labels module

`labels.py` builds `season_labels.parquet` strictly per `config/labels.yaml`. Labels feed the validator only.

### 7.7 Sensitivity battery (required before public post)

| Run | Perturbation | Report |
|-----|--------------|--------|
| S1 | `min_minutes` alternate (document delta vs 200) | Spearman vs baseline L2 rank |
| S2 | Minutes-weighted vs unweighted career mean | Top-5 overlap |
| S3 | League-only z-score (no position stratification) | Top-5 overlap |
| S4 | L2 vs Mahalanobis primary order | Spearman + top-5 overlap (**publish gate**) |
| S5 | Drop `s5_collinearity_block` `[bpm, vorp, ws]` from `config/scoring.yaml` | Spearman vs baseline |

Output: `output/sensitivity_report.json`. **No social post without this file.**

**Soft warnings** (recorded, do not block v1): S1 Spearman vs baseline < 0.80; S3 top-5 overlap < 3.

---

## 8. Modeling rules (locked)

### 8.1 Score tiers

| Output | Role |
|--------|------|
| L2 / Mahalanobis / PCA-whitened L2 ranks | **Index scores** (dual computed) |
| PCA / cosine / hybrids / uniqueness | Exploratory |
| XGBoost / SHAP | Validation only (not rank) |

### 8.2 Publish gate (public headline)

From `config/scoring.yaml`:

| Criterion | Threshold | Action if pass | Action if fail |
|-----------|-----------|----------------|----------------|
| Spearman ρ (L2 vs Mahalanobis ranks) | ≥ **0.85** | L2 may be `public_headline_score` | Use Mahalanobis or dual-table presentation |
| Top-5 overlap (L2 vs Mahalanobis) | ≥ **4** players | (same) | (same) |

Both must pass for `publish_gate_pass: true` in `sensitivity_report.json`.

- **Pass:** L2 may headline the post (with disclaimer + footnote that Mahalanobis agrees).
- **Fail:** Lead with Mahalanobis **or** publish dual ranking table; never hide divergence.

Viz layer **must not** emit post assets without `sensitivity_report.json` present.

### 8.3 Validator contract (non-gating)

XGBoost + SHAP **never** overwrites index rank or publish gate. Split: train seasons ≤ 2014, test seasons ≥ 2015 (`config/pipeline.yaml`).

**Primary metrics (season-level, test seasons only):**

| Target | Metric | Purpose |
|--------|--------|---------|
| `mvp_vote_share` | Spearman (predicted vs actual) | Sanity — do advanced vectors track MVP voting? |
| `all_nba_first` | ROC-AUC or accuracy | Sanity — binary All-NBA First Team |

**Secondary metric (career-level, weak construct check):**

- Spearman between allowlist players' **public headline score** and mean test-era model output — **exploratory validation only**, not a promotion gate.

Output: `output/validation_report.json`. Primary rank and publish gate unchanged regardless of validator results.

**Framing:** "Validator" or "award-alignment check" — never "model rank" or "true GOAT score."

---

## 9. Visualization architecture

High-dimensional career vectors (N features) cannot be shown on one chart. Visualization shows **geometry** in the space — magnitude, angle, projection, and neighborhoods — not every axis at once.

Config: `config/viz.yaml`. Worktree: `GoatProject-viz`.

### 9.1 Canonical vs exploratory

| Tier | Meaning | Charts | Caption rule |
|------|---------|--------|--------------|
| **Canonical** | Public index order (headline score) | Ranking bar/table | Score named in `public_headline_score`; include disclaimer |
| **Exploratory** | Views of the same vectors | PCA, cosine, UMAP, radars | Must **not** imply exploratory distance = rank |

**Hard rule:** Never caption PCA/UMAP proximity as "better player." Only the **publish-gate headline score** is the post scoreboard.

### 9.2 What each view shows (vector-space abstraction)

| View | Geometric meaning | Dims shown |
|------|-------------------|------------|
| L2 ranking bar | Distance from origin (vector magnitude) | 1 scalar / player |
| Cosine similarity heatmap | Angle between vectors (play-style similarity) | 21×21 pairwise |
| PCA 2D scatter | Linear projection of R^N → R² | 2 (+ variance %) |
| PCA scree | How much variance each component captures | Per component |
| PCA loadings | What each PC axis is built from | Top features × PC |
| Projection residuals | What's unique after simple subspace fit | 1 scalar / player |
| Radar / pizza (mplsoccer) | Human-readable slice of the same vector | 8–12 chosen stats |
| Parallel coordinates (optional) | Full high-D profile for 3–5 players | All `feature_columns` |
| UMAP / t-SNE (optional) | Nonlinear neighborhood map | 2 (exploratory only) |

PCA is **not** limited to 3D — it **reduces** N dimensions to 2 (or 3) for display. Always ship variance metadata with PCA figures.

Pizza/radar display values may use **percentiles within cohort or league** for readability — not raw \(z\) without labeling.

### 9.3 Library stack (`GoatProject-viz`)

| Job | Library | Notes |
|-----|---------|-------|
| Player pizza / comparison radar | **mplsoccer** | Primary social "hero" visuals |
| Similarity heatmap | **seaborn** | 21×21 cosine matrix |
| PCA scatter, scree, loadings | **matplotlib** | Static PNG for posts |
| Optional interactive PCA / parallel coords | **plotly** + **kaleido** | Export PNG; not required v1 |
| Optional neighborhood map | **umap-learn** | Exploratory only; caption clearly |

Install targets live in `config/viz.yaml`. Viz layer imports modeling/data outputs only.

### 9.4 Analyzer outputs (modeling → viz inputs)

Analyzer **must** write these before Renderer runs:

| Artifact | Writer | Required fields / content |
|----------|--------|---------------------------|
| `output/pca_coordinates.csv` | Analyzer | `player_id`, `display_name`, `pc1`, `pc2`, optional `pc3` |
| `output/pca_explained_variance.json` | Analyzer | `pc1_variance_ratio`, `pc2_variance_ratio`, `cumulative_2d`, `n_features` |
| `output/pca_loadings.csv` | Analyzer | `feature`, `pc1_loading`, `pc2_loading`, … |
| `output/similarity_matrix.csv` | Analyzer | Square matrix keyed by `player_id` |
| `output/uniqueness.csv` | Analyzer | `player_id`, `residual_norm` |
| `output/goat_rankings.csv` | Ranker | (see §6.5) |

Any PNG using PCA **must** read `pca_explained_variance.json` for the subtitle (e.g. "PC1+PC2 = 68% of variance").

### 9.5 Renderer outputs (`GoatProject-viz/output/`)

| Output | Inputs | Format |
|--------|--------|--------|
| `index.html` | rankings + links to charts | Static HTML |
| `posts/goat_rankings.png` | `goat_rankings.csv` | PNG |
| `posts/pca_map.png` | `pca_coordinates.csv`, `pca_explained_variance.json` | PNG |
| `posts/pca_scree.png` | `pca_explained_variance.json` | PNG |
| `posts/pca_loadings.png` | `pca_loadings.csv` | PNG |
| `posts/similarity_heatmap.png` | `similarity_matrix.csv` | PNG |
| `posts/players/{player_id}_pizza.png` | `career_vectors` via manifest + `config/viz.yaml` | PNG |
| `posts/comparisons/{a}_vs_{b}_radar.png` | two rows from `career_vectors` | PNG |

Social sizes and DPI: `config/viz.yaml`. Default theme: **dark** (`#0d1117` background).

**Gate:** `sensitivity_report.json` must exist before generating `output/posts/` assets.

### 9.6 Required captions (social / HTML)

Every exploratory chart includes:

1. **Title** — what the view is (e.g. "PCA map of career vectors")
2. **Variance line** (PCA only) — cumulative explained variance for displayed components
3. **Disclaimer** (exploratory only) — from `viz.yaml` → `captions.exploratory_disclaimer`
4. **Method line** — from `viz.yaml` → `captions.era_adjustment`

### 9.7 Suggested post storyboard (5 slides)

1. Concept — N stats → one vector per player (diagram or text slide)
2. **Canonical rank** — headline bar chart top 21 (`public_headline_score`)
3. **Style space** — cosine heatmap or top similarity pairs
4. **Global layout** — PCA 2D + scree inset + variance caption
5. **Human face** — mplsoccer pizza for #1 or comparison radar (e.g. Jordan vs LeBron)

### 9.8 Viz invariants

- Renderer reads `manifest.json` + modeling `output/` + `processed/career_vectors.parquet` only
- No PCA/UMAP chart without accompanying `pca_explained_variance.json`
- `goat_rankings.csv` order unchanged by viz pipeline
- Re-render from same artifacts → identical PNG dimensions and rank order

### 9.9 Configuration — `config/viz.yaml`

Machine-readable theme, export sizes, pizza/radar feature subsets, optional UMAP flag. See file for defaults (`profile_features`, `post_formats`, `optional` blocks).

---

## 10. Module layout (implementation phase)

See blueprint Step 1–5. Anti-pattern: one script that loads, ranks, trains, and plots.

```
GoatProject/                          # main branch
  ARCHITECTURE.md
  config/
  MEMORY/MEMORY.md
  plans/

GoatProject-data/                     # data branch
  src/goat_data/
    load.py, merge.py, era_adjust.py, aggregate.py, labels.py, covariance.py
    run_pipeline.py
  tests/
  processed/             # generated
  data/                  # raw CSVs

GoatProject-modeling/                 # modeling branch
  src/goat_model/
    io.py, rank.py, analyze.py, validate.py, sensitivity.py
  tests/
  output/                # generated

GoatProject-viz/                      # viz branch
  src/goat_viz/
    io.py, render.py
  output/
```

**Pytest themes (local gate; no remote CI in v1):**

- Data: full-league z-score before allowlist; Kareem/Moses pre-1979 `x3p_ar` exclusion; BPM/VORP missing season drops; σ = 0 fallback; manifest field presence; 21 rows in `career_vectors.parquet`
- Modeling: deterministic re-run equality on rankings; publish gate logic; validator JSON schema; sensitivity report required fields

---

## 11. Invariants (testable before ship)

1. `manifest.player_count == 21` and `len(career_vectors) == 21`
2. Every allowlist `player_id` appears in player-scoped outputs
3. Era baselines computed on full league (not allowlist-only)
4. Only Ranker writes `goat_rankings.csv`; only data layer writes `processed/`
5. Validator and sensitivity outputs exist without modifying rank file order
6. Viz run succeeds with no access to `data/*.csv`
7. Same inputs + config hashes → identical `goat_rankings.csv` order
8. PCA figures require `pca_explained_variance.json` (see §9.4)
9. XGBoost validates; it does not replace L2/Mahalanobis as primary rank

---

## 12. Resolved decisions

These decisions are **closed for v1**. Reopening requires an ARCHITECTURE.md version bump and plan mutation log entry.

| # | Decision | Resolution | Rationale / audit |
|---|----------|------------|-------------------|
| 1 | Player pool size | **21 locked** | Matches GOAT shortlist intent; readable viz |
| 2 | Era adjustment population | **Full league before allowlist filter** | Subset z-scores = elite peer comparison, not era adjustment |
| 3 | Primary rank source | **L2 with Mahalanobis publish gate** | Simple interpretable default; gate ensures stability before L2 headlines |
| 4 | XGBoost role | **Validator only (§8.3), non-gating** | Avoids black-box rank; season-level award sanity |
| 5 | Dual-score architecture | **L2 + Mahalanobis + PCA-whitened L2; publish gate picks headline** | Council 2026-06-14 |
| 6 | Pipeline contracts | **Advanced.csv only v1; drop season if bpm/vorp NA; era fallback; labels.yaml; S5 block; PCA/Mahalanobis on full league** | MLE 2026-06-14 |

---

## 13. Document hierarchy

When documents conflict, resolve in this order (highest authority first):

1. **`ARCHITECTURE.md`** (this file) — design intent, contracts, gates
2. **`config/*.yaml`** — parameter values implementing §5–§9
3. **`plans/goat-nba-ranking-system.md`** — execution steps, worktree tasks, exit criteria
4. **`MEMORY/MEMORY.md`** — operator quick reference; must stay consistent with 1–3
5. **Worktree READMEs** — local run instructions only

**Change protocol:**

- Design change → edit ARCHITECTURE.md first, then sync config + plan + MEMORY
- Parameter-only change → edit relevant YAML, verify against ARCHITECTURE.md, update manifest hashes on next pipeline run
- MLE / adversarial review amendments → date-stamped entry in plan mutation log + MEMORY status line

**Audit provenance:** This spec was reviewed and amended through Santa Method (mathematical coherence), council (dual-score + publish gate), MLE review (pipeline contracts, manifest fields, validator grain), and scholar evaluation (construct validity, doc consistency) — all 2026-06-14.

---

## Appendix A — Locked parameters quick reference

| Parameter | Value | Config key |
|-----------|-------|------------|
| Min minutes / season | 200 | `pipeline.yaml` → `season_filter.min_minutes` |
| Career weighting | Unweighted mean | `pipeline.yaml` → `career_vector.weight_by_minutes: false` |
| Era groups | `(season, pos)` → `(season)` fallback | `pipeline.yaml` → `era_adjustment` |
| Min group n | 30 | `pipeline.yaml` → `min_group_n` |
| Missing data | Drop season if bpm or vorp NA | `pipeline.yaml` → `missing_features` |
| Validator split | Train ≤ 2014, test ≥ 2015 | `pipeline.yaml` → `validator` |
| Publish gate | Spearman ≥ 0.85, top-5 ≥ 4 | `scoring.yaml` → `publish_gate` |
| S5 drop block | `[bpm, vorp, ws]` | `scoring.yaml` → `s5_collinearity_block` |
| PCA variance threshold | 0.90 cumulative | `scoring.yaml` → `pca_whitened_l2` |
| Mahalanobis ε | 1e-4 | `scoring.yaml` → `mahalanobis.regularization_epsilon` |

---

*End of ARCHITECTURE.md v1.0.0*
