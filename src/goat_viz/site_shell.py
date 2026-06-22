from __future__ import annotations

"""Single-tab site shell: shared nav + iframe views."""

from html import escape

SITE_EMBED_HEAD = """
  <script>
    (function () {
      if (new URLSearchParams(location.search).get('embed') === '1') {
        document.documentElement.classList.add('site-embed');
      }
      window.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'goat-resize') {
          window.dispatchEvent(new Event('resize'));
        }
      });
    })();
  </script>
  <style>
    html.site-embed .site-chrome { display: none !important; }
    html.site-embed body { overflow: auto; }
  </style>
"""

SITE_NAV_MESSAGE_JS = """
  <script>
    function goatNavigate(view) {
      if (window.parent !== window) {
        window.parent.postMessage({ type: 'goat-nav', view: view }, '*');
      } else {
        window.location.href = 'index.html#' + view;
      }
    }
  </script>
"""

SITE_VIEWS: dict[str, tuple[str, str]] = {
    "home": ("home.html", "Overview"),
    "how": ("how_it_works.html?embed=1", "How It Works"),
    "explorer": ("embed_3d.html?embed=1", "3D Explorer"),
    "alchemy": ("alchemy.html?embed=1", "Alchemy Lab"),
    "pca": ("pca_map.html?embed=1", "PCA Map"),
}


def render_site_shell_html(*, accent: str = "#f97316", background: str = "#0d1117", text: str = "#e6edf3") -> str:
    nav_buttons = "\n".join(
        f'      <button type="button" class="site-nav-btn" data-view="{key}">{escape(label)}</button>'
        for key, (_, label) in SITE_VIEWS.items()
    )
    views_json = {key: src for key, (src, _) in SITE_VIEWS.items()}

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GOAT Stat-Space Explorer</title>
  <style>
    :root {{ color-scheme: dark; }}
    html, body {{
      margin: 0; width: 100%; height: 100%; overflow: hidden;
      background: {background}; color: {text};
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    #site-app {{
      display: grid; grid-template-rows: auto minmax(0, 1fr);
      width: 100%; height: 100%;
    }}
    #site-nav {{
      display: flex; align-items: center; justify-content: center;
      flex-wrap: wrap; gap: 8px;
      padding: 10px 16px;
      border-bottom: 1px solid #30363d;
      background: {background};
      z-index: 10;
    }}
    #site-brand {{
      font-size: 0.9rem; font-weight: 600; margin-right: 12px;
      color: {text};
    }}
    .site-nav-btn {{
      padding: 7px 14px; border-radius: 999px;
      border: 1px solid #30363d; background: #161b22; color: {text};
      font-size: 0.82rem; cursor: pointer;
    }}
    .site-nav-btn:hover {{ border-color: {accent}; }}
    .site-nav-btn.active {{
      background: {accent}; color: {background}; border-color: {accent}; font-weight: 600;
    }}
    #site-frame {{
      width: 100%; height: 100%; border: 0; display: block; background: {background};
    }}
  </style>
</head>
<body>
  <div id="site-app">
    <nav id="site-nav" aria-label="Main">
      <span id="site-brand">GOAT Explorer</span>
{nav_buttons}
    </nav>
    <iframe id="site-frame" title="GOAT view" src="home.html"></iframe>
  </div>
  <script>
    const VIEWS = {views_json!r};
    const frame = document.getElementById('site-frame');
    const buttons = document.querySelectorAll('.site-nav-btn');
    let currentView = 'home';

    function setView(view, {{ pushHash = true }} = {{}}) {{
      if (!VIEWS[view]) view = 'home';
      currentView = view;
      const src = VIEWS[view];
      if (frame.getAttribute('src') !== src) {{
        frame.src = src;
      }}
      buttons.forEach((btn) => btn.classList.toggle('active', btn.dataset.view === view));
      if (pushHash) {{
        const next = view === 'home' ? '#home' : '#' + view;
        if (location.hash !== next) history.pushState(null, '', next);
      }}
      const activeBtn = [...buttons].find((b) => b.dataset.view === view);
      document.title = 'GOAT — ' + (activeBtn ? activeBtn.textContent : 'Explorer');
    }}

    buttons.forEach((btn) => {{
      btn.addEventListener('click', () => setView(btn.dataset.view));
    }});

    window.addEventListener('message', (event) => {{
      if (event.data && event.data.type === 'goat-nav' && event.data.view) {{
        setView(event.data.view);
      }}
    }});

    frame.addEventListener('load', () => {{
      try {{ frame.contentWindow?.dispatchEvent(new Event('resize')); }} catch (_) {{}}
    }});

    function viewFromHash() {{
      const h = (location.hash || '#home').replace('#', '');
      return VIEWS[h] ? h : 'home';
    }}

    window.addEventListener('hashchange', () => setView(viewFromHash(), {{ pushHash: false }}));
    window.addEventListener('popstate', () => setView(viewFromHash(), {{ pushHash: false }}));
    setView(viewFromHash(), {{ pushHash: false }});
  </script>
</body>
</html>
"""
