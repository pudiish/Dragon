Monaco Streamlit Component (scaffold)
===================================

This folder contains a minimal scaffold for a Streamlit custom component that
embeds the Monaco editor. It's intentionally simple so you can build it locally
and iterate.

Files added
- `__init__.py` — Python wrapper that declares the component and provides a
  small fallback when the frontend isn't built.
- `frontend/build/index.html` — a self-contained static page that loads Monaco
  from a CDN and posts editor updates via postMessage. This is meant as a
  lightweight build output so you can try the component without a full React
  build pipeline.

How to use
1. Start Streamlit in the project root:

```bash
streamlit run examples/monaco_demo.py
```

2. If you see the fallback message, the frontend build wasn't found. The
   provided `index.html` is already in `frontend/build` and should work without
   a build step because it loads Monaco from a CDN.

Notes and next steps
- For a production-ready component you may want to build a proper frontend
  using the official `streamlit-component-template` (React) and provide a
  message bridge using the Streamlit components SDK. This scaffold keeps
  things minimal so it can run without npm.
