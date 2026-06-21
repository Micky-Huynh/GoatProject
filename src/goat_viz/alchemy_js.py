from __future__ import annotations


def client_js(alchemy_json: str) -> str:
    return f"    const alchemyMeta = {alchemy_json};\n" + _CLIENT_BODY


def click_js() -> str:
    return _CLICK_BODY


_CLIENT_BODY = r"""    let alchemyMode = false;
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

    function blendVectors(u, v, alpha, beta) {
      return u.map((val, idx) => alpha * val + beta * v[idx]);
    }

    function nearestNeighbor(blend) {
      let best = null;
      let bestDist = Infinity;
      for (const player of players) {
        if (!player.z || player.z.length === 0) continue;
        const dist = l2Distance(blend, player.z);
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

    function combinePlayers(playerA, playerB) {
      const alpha = alchemyMeta.alpha ?? 0.5;
      const beta = alchemyMeta.beta ?? 0.5;
      const pairKey = canonicalPairKey(playerA.id, playerB.id);
      const cached = loadAlchemyCache()[pairKey];
      if (cached && cached.config_hash === alchemyMeta.config_hash) {
        return cached;
      }
      const blend = blendVectors(playerA.z, playerB.z, alpha, beta);
      const nearest = nearestNeighbor(blend);
      const result = {
        pair_key: pairKey,
        player_a_name: playerA.name,
        player_b_name: playerB.name,
        discovery_label: playerA.name + ' + ' + playerB.name + ' → ' + nearest.player.name,
        nearest_display_name: nearest.player.name,
        nearest_player_id: nearest.player.id,
        nearest_distance: nearest.distance,
        config_hash: alchemyMeta.config_hash,
      };
      saveAlchemyCacheEntry(pairKey, result);
      return result;
    }

    function renderAlchemyResult(result) {
      const disclaimer = alchemyMeta.disclaimer || 'Stat-vector blend; not GOAT rank.';
      profilePanel.innerHTML = '<div class="alchemy-result"><h2>⚗ Discovery</h2><p><strong>' +
        result.discovery_label + '</strong></p><p>Nearest neighbor distance (L2 in R^11): ' +
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

_CLICK_BODY = r"""    function onOrbClick(event) {
      if (!alchemyMode) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(orbMeshes);
      if (hits.length === 0) return;
      const picked = hits[0].object.userData;
      if (!picked.z || picked.z.length === 0) return;
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
