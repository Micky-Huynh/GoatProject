from __future__ import annotations

from html import escape

DEFAULT_CORE_COLUMNS: tuple[str, ...] = (
    "bpm_z",
    "vorp_z",
    "per_z",
    "ws_z",
    "ts_percent_z",
    "usg_percent_z",
    "ast_percent_z",
    "stl_percent_z",
    "blk_percent_z",
    "tov_percent_z",
    "x3p_ar_z",
)

DEFAULT_ALCHEMY_COLUMNS: tuple[str, ...] = DEFAULT_CORE_COLUMNS + (
    "showman_z",
    "zone_0_3_z",
    "zone_3_10_z",
    "zone_10_16_z",
    "zone_16_3p_z",
    "zone_3p_z",
    "zone_corner3_z",
)


def _column_list_html(columns: list[str]) -> str:
    items = "".join(f"<li><code>{escape(col)}</code></li>" for col in columns)
    return f"<ul class='math-col-list'>{items}</ul>"


def build_math_modal_html(
    *,
    vector_dim: int,
    pca_core_dim: int,
    cumulative_3d: float,
    alpha_default: float,
    core_columns: list[str] | None = None,
    alchemy_columns: list[str] | None = None,
) -> str:
    core = list(core_columns or DEFAULT_CORE_COLUMNS)
    alchemy = list(alchemy_columns or DEFAULT_ALCHEMY_COLUMNS)
    alchemy_only = [c for c in alchemy if c not in core]
    beta_default = 1.0 - alpha_default

    return f"""
  <div id="math-modal" class="math-modal" hidden aria-hidden="true">
    <div class="math-modal-backdrop" data-math-close></div>
    <div class="math-modal-panel" role="dialog" aria-modal="true" aria-labelledby="math-modal-title">
      <header class="math-modal-header">
        <h2 id="math-modal-title">How Alchemy Lab calculates</h2>
        <button type="button" class="math-modal-close" data-math-close aria-label="Close">×</button>
      </header>
      <div class="math-modal-body">
        <section class="math-section">
          <h3>What this tool does</h3>
          <p>
            Alchemy Lab blends two players into a <strong>hypothetical stat profile</strong> in
            ℝ<sup>{vector_dim}</sup>, then finds the <strong>nearest real allowlist player</strong>
            by Euclidean distance. This is exploratory — it does <em>not</em> change GOAT rankings.
          </p>
        </section>

        <section class="math-section">
          <h3>Two spaces (do not mix them up)</h3>
          <table class="math-table">
            <thead><tr><th>Space</th><th>Dimension</th><th>Used for</th></tr></thead>
            <tbody>
              <tr>
                <td>Ranking / display</td>
                <td>ℝ<sup>{pca_core_dim}</sup> core stats</td>
                <td>Orb positions (PCA of core), 3D Explorer layout</td>
              </tr>
              <tr>
                <td>Alchemy blend + discovery</td>
                <td>ℝ<sup>{vector_dim}</sup></td>
                <td>Combine <em>C</em>, nearest neighbor <em>D</em>, reported L2 distance</td>
              </tr>
            </tbody>
          </table>
          <p class="math-note">
            Orbs sit in PCA space ({pca_core_dim} core dims, ~{cumulative_3d:.1f}% variance in 3D).
            The ghost orb animates along a straight line between A and B in <em>display</em> space.
            Discovery distance is always computed in the full {vector_dim}-dim alchemy vector.
          </p>
        </section>

        <section class="math-section">
          <h3>Step 1 — Build career vectors</h3>
          <p>
            Each player has an era-adjusted z-score vector. Values are career means of season z-scores
            (grouped by season + position), then aggregated for the allowlist.
          </p>
          <p><strong>Core {pca_core_dim} dimensions</strong> (ranking geometry):</p>
          {_column_list_html(core)}
          <p><strong>Alchemy-only extensions ({len(alchemy_only)} dims)</strong>:</p>
          {_column_list_html(alchemy_only)}
          <p class="math-note">
            <code>showman_z</code> blends dunk rate, and-1 rate, All-Star rate, MVP share, and heaves.
            Zone columns are z-scored shot-location shares (rim, mid, three, corner, etc.).
          </p>
        </section>

        <section class="math-section">
          <h3>Step 2 — Combine (operator <em>C</em>)</h3>
          <p class="math-formula-block">
            C(<strong>u</strong>, <strong>v</strong>) = α·<strong>u</strong> + (1−α)·<strong>v</strong>
            &nbsp; in &nbsp; ℝ<sup>{vector_dim}</sup>
          </p>
          <p>
            <strong>u</strong> = Player A vector, <strong>v</strong> = Player B vector,
            α ∈ [0, 1] from the slider (default {alpha_default:.2f}, so β = 1−α = {beta_default:.2f}).
            Each coordinate blends independently:
          </p>
          <p class="math-formula-block">
            C<sub>i</sub> = α·u<sub>i</sub> + (1−α)·v<sub>i</sub>
            &nbsp; for i = 1 … {vector_dim}
          </p>
          <p class="math-note">
            This is a convex combination in stat space — not “creating” a roster player.
            Shot-zone <em>display</em> charts renormalize raw FGA shares after blending for readability.
          </p>
        </section>

        <section class="math-section">
          <h3>Step 3 — Discovery (operator <em>D</em>)</h3>
          <p class="math-formula-block">
            D(<strong>w</strong>) = argmin<sub>p ∈ allowlist</sub> ‖ <strong>w</strong> − <strong>z</strong><sub>p</sub> ‖₂
          </p>
          <p>
            <strong>w</strong> = C(<strong>u</strong>, <strong>v</strong>).
            For every allowlist player <em>p</em>, compute Euclidean distance in ℝ<sup>{vector_dim}</sup>:
          </p>
          <p class="math-formula-block">
            d<sub>p</sub> = √( Σ<sub>i=1</sub><sup>{vector_dim}</sup> (w<sub>i</sub> − z<sub>p,i</sub>)² )
          </p>
          <p>
            The player with the smallest d<sub>p</sub> is the <strong>nearest neighbor</strong>
            shown in the result panel. At default α, precomputed pairs may load from the server cache;
            other α values compute client-side (with localStorage cache).
          </p>
        </section>

        <section class="math-section">
          <h3>Step 4 — What you see on screen</h3>
          <ol class="math-steps">
            <li><strong>Blend ⚗</strong> — animates a ghost orb along PC-lerp between A and B (~800 ms, or instant if skipped).</li>
            <li><strong>Focus trio</strong> — after blend, view can isolate A, B, and the nearest match.</li>
            <li><strong>L2 distance</strong> — authoritative metric in ℝ<sup>{vector_dim}</sup>; may differ from visual orb spacing.</li>
          </ol>
        </section>

        <section class="math-section math-worked-section">
          <h3>Worked calculation (your current blend)</h3>
          <div id="math-worked-example">
            <p class="muted">Pick Player A and B, then blend — or move the α slider — to see coordinates and distance here.</p>
          </div>
        </section>
      </div>
    </div>
  </div>
"""
