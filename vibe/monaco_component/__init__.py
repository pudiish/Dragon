from __future__ import annotations

import os
from pathlib import Path
import streamlit.components.v1 as components
from typing import Optional

_COMPONENT_NAME = "monaco_component"

# Build directory (frontend static files). If the user runs the build step this
# folder should contain an index.html that wires the Streamlit component API.
_HERE = Path(__file__).parent
_BUILD_DIR = _HERE / "frontend" / "build"


def _has_build() -> bool:
    return _BUILD_DIR.exists() and (_BUILD_DIR / "index.html").exists()


def monaco_editor(value: str = "", key: Optional[str] = None, height: int = 400) -> Optional[str]:
    """Render a Monaco editor.

    If the frontend build is present (run the frontend build step), this will
    use a Streamlit custom component and return the current editor contents.

    If the build is missing this function falls back to embedding a simple
    textarea using `components.html` and returns None.
    """

    if _has_build():
        # The build exists — prefer declaring a proper Streamlit component
        # so we can support two-way binding (editor -> Python and vice versa).
        # If declaring the component fails for any reason, fall back to
        # embedding the static index.html so the editor still renders.
        try:
            _component = components.declare_component(name=_COMPONENT_NAME, path=str(_BUILD_DIR))
            # When built as a proper component, the returned value will be the
            # editor contents. We call the component and return its value.
            try:
                return _component(value=value, height=height, key=key)
            except TypeError:
                # Some older Streamlit versions may not accept height/key; call without them
                return _component(value=value)
        except Exception:
            # If declare_component fails, embed the static index.html but
            # inject the current `value` into the HTML. On each rerun this
            # HTML will be re-rendered with the fresh `value`, which lets us
            # update the embedded Monaco editor without a separate postMessage
            # bridge. Return the sentinel so the caller doesn't render a
            # second textarea editor.
            try:
                index_path = _BUILD_DIR / "index.html"
                html = index_path.read_text(encoding='utf-8')
                # Inject a small script that sets a known global with the
                # JSON-escaped editor contents. Place it right after <head> so
                # the page's scripts can read it during initialization.
                import json
                injected = f"<script>window.__EMBEDDED_INITIAL = {json.dumps(value or '')};</script>"
                # Insert injected script after the opening <head> tag if present,
                # otherwise prefix the HTML.
                if '<head>' in html:
                    html = html.replace('<head>', '<head>' + injected, 1)
                else:
                    html = injected + html

                components.html(html, height=height, scrolling=True)
                return "__EMBEDDED__"
            except Exception:
                # Fall back to None so the caller will render the textarea.
                return None

    # Fallback: embed a plain textarea inside an iframe-like HTML snippet so the
    # app doesn't break. This fallback doesn't return an updated value.
    fallback_html = f"""
    <div style="font-family: sans-serif;">
      <p><strong>Monaco component not built.</strong> Run the frontend build to enable the full editor.</p>
      <textarea style="width:100%; height: {height}px; font-family: monospace;">{value}</textarea>
    </div>
    """

    components.html(fallback_html, height=height)
    return None
