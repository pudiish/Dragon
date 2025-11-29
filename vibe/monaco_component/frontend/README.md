Monaco Streamlit Component (React)

This folder contains a minimal React-based Streamlit custom component that
wraps the Monaco editor and implements two-way sync using the Streamlit
components SDK.

How to build (local dev)

1. Install Node (>=16) and npm.
2. From this folder run:

   npm install
   npm run build

3. After building, restart your Streamlit app. The Python wrapper will
   declare the component using the `frontend/build` folder and enable
   two-way sync.

Notes
- The scaffold uses `streamlit-component-lib` and `monaco-editor`.
- The frontend currently uses a very small Webpack/Babel setup via the
  package.json scripts. You can replace with Create React App or Vite if
  you prefer.

Security
- The editor executes no code on the server. This component only sends the
  editor contents back to Python via the Streamlit component bridge.
- Keep in mind that rendering user-provided HTML/JS in the preview panel
  is potentially dangerous; sandbox or avoid for public deployments.
