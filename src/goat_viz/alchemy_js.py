from __future__ import annotations


def inline_client_js(alchemy_json: str) -> str:
    return f"    const alchemyMeta = {alchemy_json};\n" + _INLINE_CLIENT_BODY


def inline_click_js() -> str:
    return _INLINE_CLICK_BODY


def page_client_js(alchemy_json: str) -> str:
    return f"    const alchemyMeta = {alchemy_json};\n" + _PAGE_CLIENT_BODY


def page_animation_js() -> str:
    return _PAGE_ANIMATION_BODY


def client_js(alchemy_json: str) -> str:
    return inline_client_js(alchemy_json)


def click_js() -> str:
    return inline_click_js()


_INLINE_CLIENT_BODY = r"""    let alchemyMode = false;
    let alchemyPick = null;
    const alchemyToggle = document.getElementById('alchemy-toggle');
    const ALCHEMY_STORAGE_KEY = 'goat_alchemy_cache_v1';

    function canonicalPairKey(a, b) {
      return [a, b].sort().join('|');
    }

    function l2Distance(a, b) {
      let sum = 0;
      for (let i = 0; i < a.length; i += 1) {
        const d = a[i] - b[i];
        sum += d * d;
      }
      return Math.sqrt(sum);
    }

    function blendVectors(u, v, alpha) {
      const beta = 1 - alpha;
      return u.map((val, idx) => alpha * val + beta * v[idx]);
    }

    function nearestNeighbor(blend) {
      let best = null;
      let bestDist = Infinity;
      for (const player of players) {
        if (!player.z_vec || player.z_vec.length === 0) continue;
        const dist = l2Distance(blend, player.z_vec);
        if (dist < bestDist) {
          bestDist = dist;
          best = player;
        }
      }
      return { player: best, distance: bestDist };
    }

    function loadAlchemyCache() {
      try {
        return JSON.parse(localStorage.getItem(ALCHEMY_STORAGE_KEY) || '{}');
      } catch (_) {
        return {};
      }
    }

    function saveAlchemyCacheEntry(key, value) {
      const cache = loadAlchemyCache();
      cache[key] = value;
      localStorage.setItem(ALCHEMY_STORAGE_KEY, JSON.stringify(cache));
    }

    function combinePlayers(playerA, playerB, alpha) {
      const blendAlpha = alpha ?? alchemyMeta.alpha_default ?? 0.5;
      const pairKey = canonicalPairKey(playerA.id, playerB.id) + '|' + blendAlpha.toFixed(3);
      const serverCache = alchemyMeta.cache_entries || {};
      const cached = serverCache[pairKey] || loadAlchemyCache()[pairKey];
      if (cached && cached.config_hash === alchemyMeta.config_hash) {
        return cached;
      }
      const blend = blendVectors(playerA.z_vec, playerB.z_vec, blendAlpha);
      const nearest = nearestNeighbor(blend);
      const result = {
        pair_key: pairKey,
        player_a_name: playerA.name,
        player_b_name: playerB.name,
        alpha: blendAlpha,
        discovery_label: playerA.name + ' + ' + playerB.name + ' → ' + (nearest.player?.name || '?'),
        nearest_display_name: nearest.player?.name || '?',
        nearest_player_id: nearest.player?.id || null,
        nearest_distance: nearest.distance,
        showman_partial: Boolean(playerA.showman_partial || playerB.showman_partial),
        config_hash: alchemyMeta.config_hash,
        vector_dim: alchemyMeta.vector_dim || (playerA.z_vec?.length ?? 0),
      };
      saveAlchemyCacheEntry(pairKey, result);
      return result;
    }

    function renderAlchemyResult(result) {
      const disclaimer = alchemyMeta.disclaimer || 'Stat-vector blend; not GOAT rank.';
      const dim = result.vector_dim || alchemyMeta.vector_dim || 11;
      const partialBadge = result.showman_partial
        ? '<span class="partial-badge">Legacy partial showman</span>'
        : '';
      profilePanel.innerHTML = '<div class="alchemy-result"><h2>⚗ Discovery</h2><p><strong>' +
        result.discovery_label + '</strong></p>' + partialBadge +
        '<p>Nearest neighbor distance (L2 in R^' + dim + '): ' +
        result.nearest_distance.toFixed(3) + '</p><p style="color:' + sceneTheme.muted + ';">' +
        disclaimer + '</p></div>';
    }

    function clearAlchemyPick() {
      alchemyPick = null;
      orbMeshes.forEach((mesh) => { if (mesh.material) { mesh.material.opacity = 1; } });
    }

    alchemyToggle.addEventListener('click', () => {
      alchemyMode = !alchemyMode;
      alchemyToggle.classList.toggle('active', alchemyMode);
      clearAlchemyPick();
      if (!alchemyMode) renderProfilePanel(defaultBestPlayer());
    });
"""

_INLINE_CLICK_BODY = r"""    function onOrbClick(event) {
      if (!alchemyMode) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(orbMeshes);
      if (hits.length === 0) return;
      const picked = hits[0].object.userData;
      if (!picked.z_vec || picked.z_vec.length === 0) return;
      if (!alchemyPick) {
        alchemyPick = picked;
        if (hits[0].object.material) hits[0].object.material.opacity = 0.55;
        profilePanel.innerHTML = '<p class="profile-empty">Alchemy: picked <strong>' + picked.name + '</strong>. Click a second orb.</p>';
        return;
      }
      if (alchemyPick.id === picked.id) return;
      const result = combinePlayers(alchemyPick, picked);
      clearAlchemyPick();
      renderAlchemyResult(result);
    }

    renderer.domElement.addEventListener('click', onOrbClick);
"""

_PAGE_CLIENT_BODY = r"""    const ALCHEMY_STORAGE_KEY = 'goat_alchemy_cache_v2';
    const ZONE_LABELS = alchemyMeta.zone_labels || ['0-3 ft', '3-10 ft', '10-16 ft', '16-3P', '3P', 'Corner 3'];
    const playerAFilter = document.getElementById('player-a-filter');
    const playerBFilter = document.getElementById('player-b-filter');
    const playerAList = document.getElementById('player-a-list');
    const playerBList = document.getElementById('player-b-list');
    const alphaSlider = document.getElementById('alpha-slider');
    const alphaValue = document.getElementById('alpha-value');
    const skipAnimation = document.getElementById('skip-animation');
    const blendButton = document.getElementById('blend-button');
    const resultPanel = document.getElementById('result-panel');
    const mathPanel = document.getElementById('math-panel');

    let selectedA = null;
    let selectedB = null;
    let ghostOrb = null;
    let highlightMeshes = [];
    let blendAnimFrame = null;
    let blendPreviewActive = false;

    let blendFocusActive = false;
    let focusedIds = null;
    let lastBlendTrio = null;

    function setOrbVisibility(visibleIds) {
      for (const [playerId, group] of orbGroups.entries()) {
        const visible = visibleIds === null || visibleIds.has(playerId);
        group.meshes.forEach((mesh) => { mesh.visible = visible; });
        group.spokes.forEach((spoke) => { spoke.visible = visible; });
      }
    }

    function showAllPlayers() {
      focusedIds = null;
      blendFocusActive = false;
      setOrbVisibility(null);
      orbMeshes.forEach((mesh) => { if (mesh.material) mesh.material.opacity = 1; });
    }

    function focusBlendTrio(playerA, playerB, nearestId) {
      lastBlendTrio = { playerA, playerB, nearestId };
      const keep = new Set([playerA.id, playerB.id, nearestId].filter(Boolean));
      focusedIds = keep;
      blendFocusActive = true;
      setOrbVisibility(keep);
      for (const [playerId, group] of orbGroups.entries()) {
        const dim = !keep.has(playerId);
        group.meshes.forEach((mesh) => {
          if (mesh.material) mesh.material.opacity = dim ? 0.12 : 1;
        });
      }
    }

    function renderExploreCopy(featureKey) {
      const exploreBody = document.getElementById('explore-body');
      if (!exploreBody) return;
      const copy = {
        all: 'All 100 allowlist players in PCA space. Pick A + B under Blend, then blend to focus on the trio (A, B, nearest match).',
        showman: 'Showman score (alchemy-only) blends dunk rate, and-1 rate, All-Star rate, MVP share, and heaves. Legacy players use reweighted All-Star/MVP when dunk/PBP data is missing.',
        zones: 'Shot-zone shares describe where each player takes attempts (rim, mid-range, three, corner). After blending, zone charts renormalize raw shares for display.',
        impact: 'Impact z is the mean of BPM, VORP, PER, and WS z-scores — same signal as the gold crown in the 3D explorer (ranking geometry, not alchemy).',
      };
      exploreBody.innerHTML = '<p class="muted">' + (copy[featureKey] || copy.all) + '</p>';
      document.querySelectorAll('.explore-feature').forEach((el) => {
        el.classList.toggle('active', el.dataset.feature === featureKey);
      });
    }

    function toggleAllPlayersPcaView() {
      const allBtn = document.querySelector('.explore-feature[data-feature="all"]');
      const wasActive = Boolean(allBtn?.classList.contains('active'));
      renderExploreCopy('all');
      if (!wasActive) return;
      if (blendFocusActive) {
        showAllPlayers();
        return;
      }
      if (lastBlendTrio) {
        const { playerA, playerB, nearestId } = lastBlendTrio;
        focusBlendTrio(playerA, playerB, nearestId);
      }
    }

    document.querySelectorAll('.explore-feature').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (btn.dataset.feature === 'all') {
          toggleAllPlayersPcaView();
        } else {
          renderExploreCopy(btn.dataset.feature);
        }
      });
    });
    renderExploreCopy('all');


    function currentAlpha() {
      return parseFloat(alphaSlider.value);
    }

    function sortedPairKey(a, b) {
      return [a, b].sort().join('|');
    }

    function storagePairKey(a, b, alpha) {
      return sortedPairKey(a, b) + '|' + alpha.toFixed(3);
    }

    function cacheAlphaDefault() {
      return alchemyMeta.cache_alpha_default ?? alchemyMeta.alpha_default ?? 0.5;
    }

    function l2Distance(a, b) {
      let sum = 0;
      for (let i = 0; i < a.length; i += 1) {
        const d = a[i] - b[i];
        sum += d * d;
      }
      return Math.sqrt(sum);
    }

    function blendVectors(u, v, alpha) {
      const beta = 1 - alpha;
      return u.map((val, idx) => alpha * val + beta * v[idx]);
    }

    function renormalizeShares(shares) {
      if (!shares || shares.length === 0) return [];
      const sum = shares.reduce((acc, val) => acc + Math.max(val, 0), 0);
      if (sum <= 1e-9) return shares.map(() => 0);
      return shares.map((val) => Math.max(val, 0) / sum);
    }

    function blendZoneShares(sharesA, sharesB, alpha) {
      const beta = 1 - alpha;
      const raw = (sharesA || []).map((val, idx) => alpha * (val || 0) + beta * ((sharesB || [])[idx] || 0));
      return renormalizeShares(raw);
    }

    function pcLerp(a, b, t) {
      return {
        x: a.x + (b.x - a.x) * t,
        y: a.y + (b.y - a.y) * t,
        z: a.z + (b.z - a.z) * t,
      };
    }

    function nearestNeighbor(blend) {
      let best = null;
      let bestDist = Infinity;
      for (const player of players) {
        if (!player.z_vec || player.z_vec.length === 0) continue;
        const dist = l2Distance(blend, player.z_vec);
        if (dist < bestDist) {
          bestDist = dist;
          best = player;
        }
      }
      return { player: best, distance: bestDist };
    }

    function loadAlchemyCache() {
      try {
        return JSON.parse(localStorage.getItem(ALCHEMY_STORAGE_KEY) || '{}');
      } catch (_) {
        return {};
      }
    }

    function saveAlchemyCacheEntry(key, value) {
      const cache = loadAlchemyCache();
      cache[key] = value;
      localStorage.setItem(ALCHEMY_STORAGE_KEY, JSON.stringify(cache));
    }

    function normalizeServerEntry(entry, playerA, playerB, alpha) {
      const pairKey = storagePairKey(playerA.id, playerB.id, alpha);
      return {
        pair_key: pairKey,
        player_a_id: playerA.id,
        player_b_id: playerB.id,
        player_a_name: entry.player_a_name || playerA.name,
        player_b_name: entry.player_b_name || playerB.name,
        alpha,
        discovery_label: entry.discovery_label,
        nearest_display_name: entry.nearest_display_name,
        nearest_player_id: entry.nearest_player_id,
        nearest_distance: entry.nearest_distance,
        showman_partial: Boolean(playerA.showman_partial || playerB.showman_partial),
        config_hash: alchemyMeta.config_hash,
        vector_dim: alchemyMeta.vector_dim || (playerA.z_vec?.length ?? 18),
        from_server_cache: true,
      };
    }

    function lookupCachedCombine(playerA, playerB, alpha) {
      const storageKey = storagePairKey(playerA.id, playerB.id, alpha);
      const localCached = loadAlchemyCache()[storageKey];
      if (localCached && localCached.config_hash === alchemyMeta.config_hash) {
        return localCached;
      }

      const defaultAlpha = cacheAlphaDefault();
      if (Math.abs(alpha - defaultAlpha) > 0.0005) {
        return null;
      }

      const serverEntry = (alchemyMeta.cache_entries || {})[sortedPairKey(playerA.id, playerB.id)];
      if (!serverEntry) return null;
      return normalizeServerEntry(serverEntry, playerA, playerB, alpha);
    }

    function combinePlayers(playerA, playerB, alpha) {
      const blendAlpha = alpha ?? currentAlpha();
      const cached = lookupCachedCombine(playerA, playerB, blendAlpha);
      if (cached) {
        return cached;
      }

      const blend = blendVectors(playerA.z_vec, playerB.z_vec, blendAlpha);
      const nearest = nearestNeighbor(blend);
      const result = {
        pair_key: storagePairKey(playerA.id, playerB.id, blendAlpha),
        player_a_id: playerA.id,
        player_b_id: playerB.id,
        player_a_name: playerA.name,
        player_b_name: playerB.name,
        alpha: blendAlpha,
        discovery_label: playerA.name + ' + ' + playerB.name + ' → ' + (nearest.player?.name || '?'),
        nearest_display_name: nearest.player?.name || '?',
        nearest_player_id: nearest.player?.id || null,
        nearest_distance: nearest.distance,
        showman_partial: Boolean(playerA.showman_partial || playerB.showman_partial),
        config_hash: alchemyMeta.config_hash,
        vector_dim: alchemyMeta.vector_dim || (playerA.z_vec?.length ?? 18),
        from_server_cache: false,
      };
      saveAlchemyCacheEntry(result.pair_key, result);
      return result;
    }

    function renderZoneBar(shares, title) {
      const normalized = renormalizeShares(shares || []);
      if (!normalized.length) {
        return '<div class="zone-col"><div class="zone-title">' + title + '</div><p class="zone-empty muted">No zone data</p></div>';
      }
      const segments = normalized.map((pct, idx) => {
        const label = ZONE_LABELS[idx] || ('Z' + idx);
        const widthPct = Math.max(pct * 100, 0.5);
        return '<span class="zone-seg zone-' + idx + '" style="width:' + widthPct.toFixed(1) + '%" title="' +
          label + ': ' + (pct * 100).toFixed(1) + '%"></span>';
      }).join('');
      return '<div class="zone-col"><div class="zone-title">' + title + '</div><div class="zone-bar">' + segments + '</div></div>';
    }

    function renderZoneCharts(playerA, playerB, alpha, nearestPlayer) {
      const blendShares = blendZoneShares(playerA.zone_shares, playerB.zone_shares, alpha);
      return '<div class="zone-charts">' +
        renderZoneBar(playerA.zone_shares, 'A') +
        renderZoneBar(blendShares, 'Blend') +
        renderZoneBar(playerB.zone_shares, 'B') +
        renderZoneBar(nearestPlayer?.zone_shares, 'Nearest') +
        '</div>';
    }

    function renderResult(result, playerA, playerB) {
      const nnDim = result.vector_dim || alchemyMeta.vector_dim || 18;
      const pcaDim = alchemyMeta.pca_core_dim || 11;
      const partialBadge = result.showman_partial
        ? '<span class="partial-badge">Legacy partial showman</span>'
        : '';
      const disclaimer = alchemyMeta.disclaimer || 'Exploratory blend; not GOAT rank.';
      const nearest = players.find((p) => p.id === result.nearest_player_id);
      const zoneBlock = (playerA && playerB)
        ? '<div class="zone-section"><h3>Shot profile (FGA share)</h3>' +
          renderZoneCharts(playerA, playerB, result.alpha, nearest) + '</div>'
        : '';
      resultPanel.innerHTML =
        '<h2>⚗ Discovery</h2>' +
        '<p class="discovery-label"><strong>' + result.discovery_label + '</strong></p>' +
        partialBadge +
        '<p class="geom-note">Orb positions = PCA(' + pcaDim + '-dim core); NN distance = L2 in R^' + nnDim + '</p>' +
        '<p>α = ' + result.alpha.toFixed(2) + ' · L2 distance: <strong>' + result.nearest_distance.toFixed(3) + '</strong></p>' +
        zoneBlock +
        '<button type="button" id="show-all-players" class="reset-btn">Show all players</button>' +
        '<p class="muted">' + disclaimer + '</p>';
      const resetBtn = document.getElementById('show-all-players');
      if (resetBtn) resetBtn.addEventListener('click', showAllPlayers);
      renderMathWorkedExample(playerA, playerB, result.alpha, result);
    }


    function renderMathWorkedExample(playerA, playerB, alpha, result) {
      const host = document.getElementById('math-worked-example');
      if (!host) return;
      if (!playerA || !playerB || !playerA.z_vec?.length || !playerB.z_vec?.length) {
        host.innerHTML = '<p class="muted">Pick Player A and B, then blend — or move the α slider — to see coordinates and distance here.</p>';
        return;
      }
      const blendAlpha = typeof alpha === 'number' ? alpha : currentAlpha();
      const beta = 1 - blendAlpha;
      const blend = blendVectors(playerA.z_vec, playerB.z_vec, blendAlpha);
      const cols = alchemyMeta.alchemy_feature_columns || [];
      const dim = cols.length || blend.length;
      const sampleIdx = [];
      for (let i = 0; i < Math.min(4, dim); i += 1) sampleIdx.push(i);
      if (dim > 4) sampleIdx.push(dim - 1);
      const uniqueIdx = [...new Set(sampleIdx)];
      const rows = uniqueIdx.map((i) => {
        const label = cols[i] || ('dim_' + (i + 1));
        const ui = playerA.z_vec[i] ?? 0;
        const vi = playerB.z_vec[i] ?? 0;
        const ci = blend[i] ?? 0;
        const calc = (blendAlpha * ui + beta * vi).toFixed(4);
        return '<tr><td><code>' + label + '</code></td><td>' + ui.toFixed(3) + '</td><td>' + vi.toFixed(3) +
          '</td><td>' + calc + '</td><td>' + ci.toFixed(3) + '</td></tr>';
      }).join('');
      const nn = result || combinePlayers(playerA, playerB, blendAlpha);
      const nearest = players.find((p) => p.id === nn.nearest_player_id);
      let sumSq = 0;
      if (nearest?.z_vec?.length) {
        for (let i = 0; i < blend.length; i += 1) {
          const d = blend[i] - (nearest.z_vec[i] ?? 0);
          sumSq += d * d;
        }
      }
      const computedDist = Math.sqrt(sumSq);
      host.innerHTML =
        '<p><strong>' + playerA.name + '</strong> (u) + <strong>' + playerB.name + '</strong> (v)</p>' +
        '<p class="math-formula-block">C = ' + blendAlpha.toFixed(2) + '·u + ' + beta.toFixed(2) + '·v</p>' +
        '<table class="math-worked-table"><thead><tr><th>Feature</th><th>u<sub>i</sub></th><th>v<sub>i</sub></th>' +
        '<th>α·u + β·v</th><th>C<sub>i</sub></th></tr></thead><tbody>' + rows + '</tbody></table>' +
        '<p class="math-worked-summary">Showing ' + uniqueIdx.length + ' of ' + dim + ' coordinates (first dims + last).</p>' +
        '<p><strong>Nearest:</strong> ' + (nn.nearest_display_name || '?') +
        ' &nbsp;·&nbsp; <strong>L2</strong> = ' + nn.nearest_distance.toFixed(4) +
        (nearest?.z_vec?.length ? ' (recomputed √(Σ(w−z)²) = ' + computedDist.toFixed(4) + ')' : '') +
        '</p>';
    }

    function openMathModal() {
      const modal = document.getElementById('math-modal');
      if (!modal) return;
      if (selectedA && selectedB) {
        const result = (selectedA.id !== selectedB.id && selectedA.z_vec?.length && selectedB.z_vec?.length)
          ? combinePlayers(selectedA, selectedB, currentAlpha())
          : null;
        renderMathWorkedExample(selectedA, selectedB, currentAlpha(), result);
      } else {
        renderMathWorkedExample(null, null, currentAlpha(), null);
      }
      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
    }

    function closeMathModal() {
      const modal = document.getElementById('math-modal');
      if (!modal) return;
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
    }

    function initMathModal() {
      document.querySelectorAll('[data-math-open], #math-explain-button').forEach((btn) => {
        btn.addEventListener('click', openMathModal);
      });
      document.querySelectorAll('[data-math-close]').forEach((el) => {
        el.addEventListener('click', closeMathModal);
      });
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeMathModal();
      });
    }

    initMathModal();

    function clearHighlights() {
      highlightMeshes.forEach((mesh) => scene.remove(mesh));
      highlightMeshes = [];
    }

    function highlightPlayer(player) {
      clearHighlights();
      if (!player) return;
      const group = orbGroups.get(player.id);
      if (!group) return;
      const pos = group.meshes[0].position;
      const halo = new THREE.Mesh(
        new THREE.SphereGeometry(player.radius * 1.35, 24, 24),
        new THREE.MeshBasicMaterial({ color: 0xfbbf24, transparent: true, opacity: 0.35, wireframe: true }),
      );
      halo.position.copy(pos);
      scene.add(halo);
      highlightMeshes.push(halo);
    }

    function refreshBlendPreview() {
      if (!selectedA || !selectedB || selectedA.id === selectedB.id) return;
      if (!selectedA.z_vec?.length || !selectedB.z_vec?.length) return;
      const result = combinePlayers(selectedA, selectedB, currentAlpha());
      renderResult(result, selectedA, selectedB);
      const nearest = players.find((p) => p.id === result.nearest_player_id);
      highlightPlayer(nearest);
      renderMathWorkedExample(selectedA, selectedB, currentAlpha(), result);
    }

    function buildPicker(listEl, filterEl, slot) {
      const sorted = players.slice().sort((a, b) => a.rank_impact - b.rank_impact);
      listEl.innerHTML = sorted.map((player) => `
        <button type="button" class="picker-option" data-id="${player.id}" data-name="${player.name.toLowerCase()}">
          #${player.rank_impact} ${player.name}
        </button>
      `).join('');

      listEl.querySelectorAll('.picker-option').forEach((btn) => {
        btn.addEventListener('click', () => {
          const player = players.find((p) => p.id === btn.dataset.id);
          if (!player) return;
          if (slot === 'A') {
            selectedA = player;
            playerAList.querySelectorAll('.picker-option').forEach((el) => el.classList.remove('selected'));
          } else {
            selectedB = player;
            playerBList.querySelectorAll('.picker-option').forEach((el) => el.classList.remove('selected'));
          }
          btn.classList.add('selected');
          if (blendPreviewActive && selectedA && selectedB) refreshBlendPreview();
        });
      });

      filterEl.addEventListener('input', () => {
        const query = filterEl.value.trim().toLowerCase();
        listEl.querySelectorAll('.picker-option').forEach((row) => {
          row.style.display = row.dataset.name.includes(query) ? 'block' : 'none';
        });
      });
    }

    function ensureGhostOrb() {
      if (ghostOrb) return ghostOrb;
      const material = new THREE.MeshBasicMaterial({
        color: sceneTheme.accent,
        transparent: true,
        opacity: 0.55,
      });
      ghostOrb = new THREE.Mesh(new THREE.SphereGeometry(0.1, 32, 32), material);
      ghostOrb.visible = false;
      scene.add(ghostOrb);
      return ghostOrb;
    }

    alphaSlider.addEventListener('input', () => {
      alphaValue.textContent = currentAlpha().toFixed(2);
      const alpha = currentAlpha();
      mathPanel.querySelector('.alpha-live').textContent = alpha.toFixed(2);
      mathPanel.querySelector('.beta-live').textContent = (1 - alpha).toFixed(2);
      if (blendPreviewActive) refreshBlendPreview();
      else if (selectedA && selectedB && selectedA.id !== selectedB.id) {
        renderMathWorkedExample(selectedA, selectedB, alpha, null);
      }
    });

    blendButton.addEventListener('click', () => {
      if (!selectedA || !selectedB) {
        resultPanel.innerHTML = '<p class="muted">Pick Player A and Player B first.</p>';
        blendPreviewActive = false;
        return;
      }
      if (selectedA.id === selectedB.id) {
        resultPanel.innerHTML = '<p class="muted">Choose two different players.</p>';
        blendPreviewActive = false;
        return;
      }
      if (!selectedA.z_vec?.length || !selectedB.z_vec?.length) {
        resultPanel.innerHTML = '<p class="muted">Alchemy vectors unavailable for this pair.</p>';
        blendPreviewActive = false;
        return;
      }
      blendPreviewActive = true;
      runBlend(selectedA, selectedB);
    });


    function initSidebarResize() {
      const main = document.getElementById('main');
      if (!main) return;

      function attach(handleId, side) {
        const handle = document.getElementById(handleId);
        if (!handle) return;
        const minWidth = side === 'left' ? 200 : 220;
        const maxWidth = side === 'left' ? 480 : 560;
        const varName = side === 'left' ? '--left-sidebar-width' : '--right-sidebar-width';

        handle.addEventListener('mousedown', (event) => {
          event.preventDefault();
          const startX = event.clientX;
          const startWidth = parseInt(getComputedStyle(main).getPropertyValue(varName), 10) || (side === 'left' ? 260 : 320);
          handle.classList.add('dragging');
          document.body.style.cursor = 'col-resize';
          document.body.style.userSelect = 'none';

          function onMove(ev) {
            const delta = side === 'left' ? ev.clientX - startX : startX - ev.clientX;
            const next = Math.min(maxWidth, Math.max(minWidth, startWidth + delta));
            main.style.setProperty(varName, next + 'px');
            window.dispatchEvent(new Event('resize'));
          }

          function onUp() {
            handle.classList.remove('dragging');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
          }

          document.addEventListener('mousemove', onMove);
          document.addEventListener('mouseup', onUp);
        });
      }

      attach('resize-left', 'left');
      attach('resize-right', 'right');
    }

    initSidebarResize();

    buildPicker(playerAList, playerAFilter, 'A');
    buildPicker(playerBList, playerBFilter, 'B');
    alphaValue.textContent = currentAlpha().toFixed(2);
"""

_PAGE_ANIMATION_BODY = r"""    function runBlend(playerA, playerB) {
      const alpha = currentAlpha();
      const result = combinePlayers(playerA, playerB, alpha);
      const ghost = ensureGhostOrb();
      ghost.visible = true;
      ghost.scale.setScalar((playerA.radius + playerB.radius) * 0.5 / 0.1);

      if (blendAnimFrame) cancelAnimationFrame(blendAnimFrame);

      const start = { x: playerA.x, y: playerA.y, z: playerA.z };
      const end = { x: playerB.x, y: playerB.y, z: playerB.z };
      const durationMs = 800;

      function finish() {
        ghost.visible = false;
        renderResult(result, playerA, playerB);
        const nearest = players.find((p) => p.id === result.nearest_player_id);
        highlightPlayer(nearest);
        focusBlendTrio(playerA, playerB, result.nearest_player_id);
      }

      if (skipAnimation.checked) {
        const mid = pcLerp(start, end, alpha);
        ghost.position.set(mid.x, mid.y, mid.z);
        finish();
        return;
      }

      const t0 = performance.now();
      function step(now) {
        const t = Math.min(1, (now - t0) / durationMs);
        const pos = pcLerp(start, end, t);
        ghost.position.set(pos.x, pos.y, pos.z);
        if (t < 1) {
          blendAnimFrame = requestAnimationFrame(step);
        } else {
          finish();
        }
      }
      ghost.position.set(start.x, start.y, start.z);
      blendAnimFrame = requestAnimationFrame(step);
    }
"""
