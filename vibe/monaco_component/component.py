from pathlib import Path
import streamlit.components.v1 as components

_COMPONENT_NAME = "monaco_component"

# This file provides a helper that can be imported to declare the compiled
# component when the frontend build is present. The function is intentionally
# small because the main `monaco_editor` function in `__init__.py` handles
# fallback embedding.

def declare_component(build_dir: str):
    return components.declare_component(name=_COMPONENT_NAME, path=build_dir)
