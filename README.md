# NBA GOAT Stat-Space Index

An exploratory ranking and visualization project for comparing **100 curated all-time NBA players** using era-adjusted advanced stats, playoff context, and interactive 3D PCA maps.

**This is not a claim of objective GOAT truth.** It is a transparent composite index over a hand-picked shortlist. Different metrics answer different questions (impact vs titles vs statistical uniqueness).

---

## Clone and run (checkpoint)

Fresh clone — three commands:

```bash
git clone https://github.com/Micky-Huynh/GoatProject.git
cd GoatProject
./bootstrap.sh && ./open.sh
```

**What `bootstrap.sh` does:**

1. Adds git worktrees (`GoatProject-data`, `GoatProject-modeling`, `GoatProject-viz`)
2. Installs Python packages (`pip install -e .[dev]` in each worktree)
3. Verifies the **checkpoint** (`checkpoint.yaml`) — pre-built CSVs, parquet, rankings, and HTML on the `data` / `modeling` / `viz` branches

**Requirements:** Python **3.11+**, git, pip.

| Script | Purpose |
|--------|---------|
| `./bootstrap.sh` | First-time setup after clone |
| `./open.sh` | Open `index.html` in browser (`./open.sh alchemy` for Alchemy Lab) |
| `./run.sh` | Full rebuild from raw CSVs (~10+ min) |
| `./scripts/verify_checkpoint.py` | Check artifacts only |
| `./scripts/refresh_checkpoint.sh` | Maintainer: rebuild + commit checklist |

Checkpoint contract: **v2.0.0 (alchemy-v2)** — 100 players, R¹⁸ alchemy cache, `alchemy.html` included. See `checkpoint.yaml`.

---

## Quick start (view only)

If outputs are already built, open the visualization bundle in a browser:

```text
GoatProject-viz/output/index.html
```

Open **`index.html`** for the unified site — one tab with a nav bar to switch Overview, 3D Explorer, Alchemy Lab, and PCA Map without full page reloads.

The **3D embed** (`embed_3d.html`) is also available standalone: rotate the PCA space, pick players, and hover orbs for skill breakdowns.

The **Alchemy Lab** (`alchemy.html`) is a separate page for blending two players and discovering the nearest allowlist match in R¹⁸ stat space:

```bash
open GoatProject-viz/output/alchemy.html
# or from index.html → "Alchemy Lab" link
```

---

## What you get

| Output | Location | Purpose |
|--------|----------|---------|
| Interactive index | `GoatProject-viz/output/index.html` | Links to all charts |
| 3D PCA explorer | `GoatProject-viz/output/embed_3d.html` | Photo orbs in PC1–PC3 space, player picker, impact crown |
| Alchemy Lab | `GoatProject-viz/output/alchemy.html` | Blend two players (α slider), PC-lerp animation, nearest-neighbor discovery in R¹⁸ |
| Bar chart leaderboard | `GoatProject-viz/output/posts/goat_rankings.png` | Sorted by `score_goat_index` |
| PCA scatter | `GoatProject-viz/output/posts/pca_scatter.png` | Static 2D PCA view |
| Similarity heatmap | `GoatProject-viz/output/posts/similarity_heatmap.png` | Cosine similarity between careers |
| Rankings table | `GoatProject-modeling/output/goat_rankings.csv` | All scores and ranks |

---

## Ranking lenses (read this first)

The project intentionally uses **multiple scores**. They do not always agree — that is the point.

### Gold crown (3D view)

- **Meaning:** Highest **overall impact** among **currently visible** players.
- **Formula:** Mean career z-score of BPM, VORP, PER, and Win Shares.
- **Updates when** you check/uncheck players in the left panel (Default 21, All, None, or custom).
- **Not driven by championships.** A one-ring season does not win the crown.

### `score_goat_index` (bar chart)

Composite index combining:

- PCA-whitened distance (stat-space geometry)
- Team-weighted championship credit (`championship_net`)
- Clutch/consensus adjustment (penalty when elite box-score stats outrun playoff success + MVP/All-NBA recognition)

**Lower score = better** on this chart.

### Other geometry scores (tooltips / CSV)

| Score | Plain English |
|-------|----------------|
| **L2** | Straight-line distance from “average” across all 11 z-scored stats |
| **Mahalanobis** | Like L2, but accounts for correlated stats |
| **PCA score** | Distance in whitened principal-component space (not the same as impact) |
| **PC1 / PC2 / PC3** | Position on the 3D map axes (~impact, style, playmaking vs defense) |

### Profile skill bars

When you hover a player, aspect bars re-rank **within your visible selection**:

- **Overall impact** — BPM, VORP, PER, WS
- **Scoring** — TS%, usage, 3-point rate
- **Playmaking** — assist rate
- **Defense** — steal and block rates
- **Ball security** — turnover rate
- **Repeated titles** — ring count plus bonuses for back-to-back runs and 3+ peat dynasties

---

## Run the full pipeline

### Prerequisites

- Python **3.11+** recommended (viz package requires 3.11)
- Raw Basketball Reference CSVs in `GoatProject-data/data/` (not committed to git; lives on the `data` worktree branch)

### Environment

Point all packages at the repo root:

```bash
export GOAT_ROOT="/path/to/GoatProject"
```

### Install (once per machine)

```bash
cd GoatProject-data && pip install -e ".[dev]"
cd ../GoatProject-modeling && pip install -e ".[dev]"
cd ../GoatProject-viz && pip install -e ".[dev]"
```

### Build everything (one command)

From the repo root:

```bash
./run.sh
```

### Build everything (step by step)

```bash
export GOAT_ROOT="/path/to/GoatProject"

cd GoatProject-data
python3.11 -m goat_data.run_pipeline

cd ../GoatProject-modeling
python3.11 -m goat_model.run_ranking
python3.11 -m goat_model.run_analysis

cd ../GoatProject-viz
python3.11 -m goat_viz.run_viz
```

Then open `GoatProject-viz/output/index.html`.

### Run tests

```bash
cd GoatProject-data && pytest
cd ../GoatProject-modeling && pytest
cd ../GoatProject-viz && pytest
```

---


## Alchemy Lab (`alchemy.html`)

Infinite-Alchemy-style **exploratory** player merge — separate from GOAT rank and from the 3D explorer (inline alchemy is disabled; `config/viz.yaml` → `alchemy_inline: false`).

### How to open

After `./run.sh` or `python -m goat_viz.run_viz`:

```bash
open GoatProject-viz/output/alchemy.html
```

Or open `GoatProject-viz/output/index.html` and follow the **Alchemy Lab** link.

### What it does

1. **Pick player A and B** — searchable dropdowns (same pool as the 100-player allowlist).
2. **Adjust α** — slider controls the blend $C(\mathbf{u},\mathbf{v}) = \alpha\mathbf{u} + (1-\alpha)\mathbf{v}$ in **R¹⁸** (11 core stats + showman excitement + 6 shot-zone z-scores). Default α = 0.5.
3. **Blend** — ghost orb animates along a PC-lerp path between A and B display positions (~800 ms). Check **Skip animation** to snap directly to the result.
4. **Discovery** — highlights the nearest allowlist player by **L2 distance in R¹⁸** (not the same as visual orb proximity on the 11-dim PCA map).
5. **Math panel** — collapsible walkthrough of the blend formula and dimensions.
6. **Partial badge** — when either parent has `showman_partial=true` (legacy players missing dunk/and-1 data), a badge explains the reweighted showman profile.

**Important:** Core rankings (`score_goat_index`, L2, Mahalanobis) still use **11 dimensions only**. Showman and shot zones affect alchemy discovery, not the bar chart or crown.

Formulas: `MATHS.md` §13. Design: `ARCHITECTURE.md` §9.10.

## Visualization guide

All charts are linked from `GoatProject-viz/output/index.html`. Formulas and notation are in **`MATHS.md`**.

### 2D PCA scatter (`posts/pca_scatter.png`)

Static **bird’s-eye view** of the same stat-space as the 3D embed, using only the first two principal components.

| Element | Meaning |
|---------|---------|
| **X-axis (PC1)** | ~38% of variance; loads heavily on BPM, VORP, PER, WS — the main “impact” direction |
| **Y-axis (PC2)** | ~16% of variance; style mix (3-point rate, turnovers, blocks) |
| **Each dot** | One allowlist player at \((\text{PC1}, \text{PC2})\) |
| **Crosshairs at (0, 0)** | League-mean center in this rotated space |
| **Labels** | All 100 names annotated (offset by quadrant to reduce overlap) |
| **Footnote** | Reports PC1+PC2 cumulative variance (~54%) and exploratory disclaimer |

**How to read it:**

- **Right on PC1** → stronger on the shared impact bundle (Jordan, LeBron, Jokić cluster far right).
- **Up/down on PC2** → different *kinds* of profiles, not strictly better/worse.
- **Distance from center** in this 2D plane is **not** the GOAT index and **not** the impact crown — it is position in the first two PCA axes only.
- Use this chart for **overview and screenshots**; use the 3D embed for interaction and the crown.

PCA is fit on **full-league** careers; only the 100 allowlist players are plotted. See `MATHS.md` §5.

### 3D PCA embed (`embed_3d.html`)

Interactive view adding **PC3** (~12% variance; playmaking vs rim protection).

1. **Rotate / zoom** — drag and scroll on the viewport.
2. **Player picker** — search and toggle checkboxes; **Default 21** restores the curated shortlist in `config/allowlist.yaml`.
3. **Gold crown** — highest **impact z** among **visible** players (BPM/VORP/PER/WS mean); updates when selection changes.
4. **Orb size** — scales with overall impact (larger = stronger impact profile).
5. **Profile panel** — hover an orb for titles, playoff depth, clutch adjustment, and cohort-relative skill bars.
6. **Spokes** — lines from the origin to each orb (optional; `config/viz.yaml`).

Axes are **independently scaled** to fit the pool (origin forced into view), so visual distance in 3D ≠ whitened PCA score.

### Bar chart (`posts/goat_rankings.png`)

Horizontal leaderboard sorted by **`score_goat_index`** (PCA geometry − weighted titles + clutch penalty). **Lower bar = better.**

### Similarity heatmap (`posts/similarity_heatmap.png`)

**Cosine similarity** between career vectors (play-style proximity). Bright = similar statistical profiles; not a greatness ranking.

---

## Project layout

```text
GoatProject/
├── config/                 # Allowlist, features, scoring, playoffs, viz theme
├── GoatProject-data/       # Pipeline: CSV → parquet (worktree)
├── GoatProject-modeling/   # Rankings, PCA, sensitivity, validation (worktree)
├── GoatProject-viz/        # Charts + 3D HTML (worktree)
├── ARCHITECTURE.md         # Technical spec (design source of truth)
├── MATHS.md                # Formulas: z-scores, distances, PCA, GOAT index
└── plans/                  # Build history and notes
```

The repo uses **git worktrees** for `data`, `modeling`, and `viz`. Commit changes inside each worktree on its branch, not only from the main tree.

---

## Configuration

| File | What to edit |
|------|----------------|
| `config/allowlist.yaml` | 100-player pool and default 21 visible in the 3D viz |
| `config/features.yaml` | Stat features and orientation |
| `config/scoring.yaml` | L2 / Mahalanobis / PCA weights and framing |
| `config/playoffs.yaml` | Titles, playoff depth, clutch penalty, repeat-title bonuses |
| `config/viz.yaml` | Colors, orb sizes, skill aspects, captions, `alchemy_inline` / `alchemy_page` |
| `config/alchemy.yaml` | Alchemy cache version, default α, R¹⁸ disclaimer |
| `config/showman.yaml` | Showman excitement weights (full vs legacy partial) |
| `config/scoring_zones.yaml` | Shot-zone column map and corner-3 derivation |

After config changes, re-run the pipeline steps above.

---

## Data disclaimer

- Stats are **era-adjusted z-scores** against full-league season baselines (minutes threshold applies).
- Career vectors are **unweighted season means**, not peak-only seasons.
- Playoff team strength uses full-season team profiles for playoff teams (not separate postseason stat rows).
- Pool is **curated**, not league-wide.

---

## Further reading

- **Mathematics & formulas:** `MATHS.md`
- **System design:** `ARCHITECTURE.md`
- **Operator memory / session notes:** `MEMORY/MEMORY.md` (local, gitignored on main)

---

## Example questions this project helps answer

- Who has the strongest **statistical impact** profile in our pool?
- How do **rings and repeat dynasties** compare to raw production?
- Where do players sit in **multi-stat space** (PCA), and who looks similar?
- Does the ordering **change** when you swap metrics or shrink the comparison group?

It does **not** settle the cultural GOAT debate — it makes the tradeoffs visible.
