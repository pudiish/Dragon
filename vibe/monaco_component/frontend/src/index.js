import React, {useEffect, useRef, useState} from "react";
import ReactDOM from "react-dom";
import { Streamlit } from "streamlit-component-lib";
import * as monaco from "monaco-editor";

function MonacoComponent(props) {
  const { value = "", height = 400 } = props;
  const containerRef = useRef(null);
  const editorRef = useRef(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;
    if (editorRef.current) return;

    editorRef.current = monaco.editor.create(containerRef.current, {
      value: value || "",
      language: props.language || "javascript",
      theme: "vs-dark",
      automaticLayout: true,
      minimap: { enabled: false }
    });

    // Debounced onChange -> streamlit
    let timeout = null;
    editorRef.current.onDidChangeModelContent(() => {
      if (timeout) clearTimeout(timeout);
      timeout = setTimeout(() => {
        const v = editorRef.current.getValue();
        Streamlit.setComponentValue(v);
      }, 250);
    });

    setMounted(true);

    return () => {
      try {
        editorRef.current && editorRef.current.dispose();
      } catch (e){}
    };
  }, [containerRef]);

  // Listen for incoming value changes from Python
  useEffect(() => {
    if (!mounted || !editorRef.current) return;
    const current = editorRef.current.getValue();
    if (value !== current) {
      const pos = editorRef.current.getPosition();
      editorRef.current.setValue(value || "");
      if (pos) editorRef.current.setPosition(pos);
    }
  }, [value, mounted]);

  return React.createElement(
    'div',
    { style: { height: height, width: '100%' } },
    React.createElement('div', { ref: containerRef, style: { height: '100%', width: '100%' } })
  );
}

function render(element) {
  const props = Streamlit.getComponentProps();
  ReactDOM.render(React.createElement(MonacoComponent, props), element);
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, (event) => {
  render(event.detail.node);
});

// Initial render for dev server contexts
document.addEventListener("DOMContentLoaded", () => {
  const mount = document.getElementById("root");
  if (mount) render(mount);
});
