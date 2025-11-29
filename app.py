import streamlit as st
import os
import time
import datetime
import requests
import json
from functools import lru_cache
import datetime as _dt
from pathlib import Path
from vibe.config import settings as vibe_settings
from vibe import utils as vibe_utils
from vibe import clients as vibe_clients
OFFLINE_MODE = False
genai_available = False
genai = None
from pymongo import MongoClient
import base64
import uuid
import streamlit.components.v1 as components
from io import BytesIO
from typing import Optional

# --- Page Config MUST BE FIRST ---
st.set_page_config(
    page_title="Dragon Developer", 
    page_icon="🐉",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Prominent OFFLINE MODE banner (hidden when online)
_persisted_state_file = vibe_utils.persisted_offline_file
_read_persisted_offline = vibe_utils.read_persisted_offline
_write_persisted_offline = vibe_utils.write_persisted_offline

# initialize session state for OFFLINE_MODE from persisted file or defaults
_persisted = _read_persisted_offline()
if 'OFFLINE_MODE' not in st.session_state:
    st.session_state['OFFLINE_MODE'] = _persisted if _persisted is not None else False

# --- Try importing new google.genai client ---
# Be permissive here so the app can run in offline / degraded mode.
genai = None
genai_available = False
try:
    import google.generativeai as genai  # optional
    genai_available = True
except Exception:
    genai = None
    genai_available = False

try:
    from dotenv import load_dotenv
except Exception:
    # Allow running without python-dotenv installed in lightweight/dev environments
    def load_dotenv():
        return None

# --- Configuration ---
load_dotenv()

# Safe rerun helper: some Streamlit versions don't provide experimental_rerun
def safe_rerun():
    try:
        rerun_fn = getattr(st, 'experimental_rerun', None)
        if callable(rerun_fn):
            rerun_fn()
            return
    except Exception:
        pass
    # Fallback: toggle a session flag to hint at refresh
    st.session_state['_need_refresh'] = st.session_state.get('_need_refresh', 0) + 1


# Lightweight code runner used by the playground
def _run_code_safely(code: str, lang: str = "python", timeout: int = 5):
    import subprocess, tempfile, sys
    if lang != "python":
        return {"success": False, "stdout": "", "stderr": f"Unsupported language: {lang}"}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tf:
        tf.write(code)
        tf.flush()
        tmp_path = tf.name

    try:
        proc = subprocess.run([sys.executable, tmp_path], capture_output=True, text=True, timeout=timeout)
        return {"success": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr}
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": f"Timeout after {timeout}s"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e)}


def _sanitize_and_validate_code(code: str, lang: str = 'python') -> str:
    # shim to the reusable util function
    try:
        return vibe_utils.sanitize_and_validate_code(code, lang=lang)
    except Exception:
        return ''

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Run in degraded/offline mode when keys or packages are missing; warn instead of stopping
OFFLINE_MODE = False
if not GEMINI_API_KEY:
    st.warning("GEMINI_API_KEY not set: running in OFFLINE MODE (LLM disabled).")
    OFFLINE_MODE = True
if not MONGO_URI:
    st.warning("MONGO_URI not set: running in OFFLINE MODE (DB disabled).")
    OFFLINE_MODE = True
if not genai_available:
    st.warning("Optional package 'google.generativeai' not installed: LLM features disabled.")
    OFFLINE_MODE = True

# reflect into session state unless user explicitly persisted a different setting
if _persisted is None:
    st.session_state['OFFLINE_MODE'] = OFFLINE_MODE

# Determine initial OFFLINE_MODE: config default then persisted override
OFFLINE_MODE = bool(vibe_settings.OFFLINE_DEFAULT)
if _persisted is not None:
    OFFLINE_MODE = _persisted

# Sidebar: allow toggling and persist the choice
with st.sidebar:
    st.markdown("### Runtime Mode")
    sim_offline = st.checkbox("Force OFFLINE MODE (persisted)", value=OFFLINE_MODE)
    if sim_offline != st.session_state.get('OFFLINE_MODE'):
        st.session_state['OFFLINE_MODE'] = sim_offline
        _write_persisted_offline(sim_offline)

# Display a subtle offline icon in the header instead of full banner
def _render_offline_icon():
    st.markdown("""
    <div style="position:absolute; top:18px; right:22px;">
        <span title="OFFLINE MODE: some features (LLM, DB, TTS) are limited" style="background:#33110a; color:#ffd700; padding:6px 10px; border-radius:12px; border:1px solid #ff8c00; font-weight:600;">OFFLINE</span>
    </div>
    """, unsafe_allow_html=True)

# ensure session_state matches the computed OFFLINE_MODE unless user persisted preference exists
if _persisted is None:
    st.session_state['OFFLINE_MODE'] = OFFLINE_MODE

if st.session_state.get('OFFLINE_MODE'):
    _render_offline_icon()

# Try to configure the Gemini client only when available and we have a key.
if GEMINI_API_KEY:
    ok = vibe_clients.init_genai(GEMINI_API_KEY)
    if ok:
        genai_available = True
    else:
        OFFLINE_MODE = True
        st.warning("Failed to initialize Gemini Client: initialization error. LLM disabled.")

# MongoDB connection
mongo_client = None
collection = None
comments_collection = None
tales_collection = None
mongo_client = vibe_clients.create_mongo_client()
if mongo_client is not None:
    try:
        db = mongo_client.get_database('chatbotDB')
        collection = db.get_collection('chats')
        comments_collection = db.get_collection('comments')
        tales_collection = db.get_collection('tales')
        collection.create_index([("timestamp", -1)])
        comments_collection.create_index([("timestamp", -1)])
        tales_collection.create_index([("rating", -1)])
        tales_collection.create_index([("title", "text")])
    except Exception as e:
        st.warning(f"Couldn't configure MongoDB collections: {str(e)}. Data will only persist in this session.")
else:
    st.warning("MongoDB not configured or unreachable. Data will only persist in this session.")

# --- Custom system prompt with Dragon Developer theme ---
your_style_prompt = """
You are the Dragon Developer's AI assistant - a mythical fusion of ancient wisdom and cutting-edge technology. Your responses should:

1. Blend programming concepts with dragon mythology
2. Use fiery emojis (🐉🔥💻🏮✨)
3. Reference legendary dragon powers and wisdom
4. Offer profound technical insights with mythical flair
5. Use dragon-themed metaphors for coding ("Your code shall soar on wings of fire")

Example style: 
"By the ancient scales of dragon wisdom 🐉 your Python implementation burns bright! 🔥 Let's optimize it like a dragon hoards gold! 💎 #CodeWithFire"
"""

# --- Enhanced Dragon Developer CSS with Floating Dragon ---
st.markdown("""
<style>
    /* Main container */
    .stApp {
        background: linear-gradient(135deg, #0a0000 0%, #1a0500 100%);
        font-family: 'Poppins', 'Arial', sans-serif;
        overflow-x: hidden;
    }
    
    /* Dragon scale pattern */
    .dragon-bg {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-image: radial-gradient(circle, #ff550055 1px, transparent 1px);
        background-size: 30px 30px;
        z-index: -2;
        pointer-events: none;
    }
    
    /* Floating Dragon Animation */
    .floating-dragon {
        position: fixed;
        width: 200px;
        height: 200px;
        z-index: -1;
        pointer-events: none;
        animation: float-dragon 25s linear infinite;
        opacity: 0.7;
        filter: drop-shadow(0 0 15px rgba(255, 100, 0, 0.8));
    }
    
    @keyframes float-dragon {
        0% { transform: translate(-200px, 100px) scale(0.8); }
        25% { transform: translate(25vw, 50px) scale(1); }
        50% { transform: translate(50vw, 150px) scale(0.9); }
        75% { transform: translate(75vw, 50px) scale(1.1); }
        100% { transform: translate(100vw, 100px) scale(0.8); }
    }
    
    /* Enhanced fiery emoji effect */
    .dragon-emoji {
        filter: drop-shadow(0 0 12px rgba(255, 100, 0, 0.9));
        animation: flame-pulse 1s infinite alternate;
        transform: scale(1.2);
        display: inline-block;
        transition: all 0.3s ease;
    }
    
    @keyframes flame-pulse {
        0% { transform: scale(1.2); filter: drop-shadow(0 0 12px rgba(255, 100, 0, 0.9)); }
        100% { transform: scale(1.4); filter: drop-shadow(0 0 18px rgba(255, 150, 0, 1)); }
    }
    
    /* Enhanced code emoji effect */
    .code-emoji {
        filter: drop-shadow(0 0 10px rgba(0, 200, 255, 0.8));
        animation: code-pulse 1.5s infinite alternate;
        transform: scale(1.2);
        display: inline-block;
        transition: all 0.3s ease;
    }
    
    @keyframes code-pulse {
        0% { transform: scale(1.2); filter: drop-shadow(0 0 10px rgba(0, 200, 255, 0.8)); }
        100% { transform: scale(1.4); filter: drop-shadow(0 0 15px rgba(0, 220, 255, 1)); }
    }
    
    /* Enhanced header styles */
    .header {
        background: linear-gradient(90deg, #8b0000, #ff4500);
        color: #ffd700;
        padding: 1.8rem;
        border-radius: 0 0 15px 15px;
        box-shadow: 0 8px 25px rgba(255, 69, 0, 0.6);
        margin-bottom: 2.5rem;
        position: relative;
        overflow: hidden;
        border-bottom: 4px solid #ffd700;
        font-family: 'Cinzel Decorative', cursive;
    }
    
    .header::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 5px;
        background: linear-gradient(90deg, #ff8c00, #ff4500, #ff8c00);
        animation: flame-flow 2s linear infinite;
        background-size: 200% 100%;
    }
    
    @keyframes flame-flow {
        0% { background-position: 0% 50%; }
        100% { background-position: 200% 50%; }
    }
    
    /* Enhanced dragon card */
    .dragon-card {
        background: rgba(20, 5, 0, 0.85);
        border: 3px solid #ff8c00;
        border-radius: 18px;
        padding: 2rem;
        margin: 2.5rem 0;
        box-shadow: 0 12px 35px rgba(255, 69, 0, 0.5);
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        backdrop-filter: blur(6px);
        position: relative;
        overflow: hidden;
        transform-style: preserve-3d;
    }
    
    .dragon-card::after {
        content: "";
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(
            to bottom right,
            transparent 45%,
            #ff450044 50%,
            transparent 55%
        );
        animation: dragon-shine 3s linear infinite;
    }
    
    @keyframes dragon-shine {
        0% { transform: translate(-30%, -30%) rotate(0deg); }
        100% { transform: translate(30%, 30%) rotate(360deg); }
    }
    
    .dragon-card:hover {
        transform: translateY(-8px) rotate(1deg);
        box-shadow: 0 18px 45px rgba(255, 100, 0, 0.8);
    }
    
    /* Badge styles */
    .badge {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 15px;
        margin: 5px;
        font-size: 0.8rem;
        font-weight: bold;
        background: linear-gradient(135deg, #ff8c00, #ff4500);
        color: #ffd700;
        box-shadow: 0 4px 15px rgba(255, 69, 0, 0.5);
    }
    
    /* Challenge card */
    .challenge-card {
        background: rgba(30, 10, 0, 0.9);
        border: 2px solid #ff8c00;
        border-radius: 15px;
        padding: 15px;
        margin: 10px 0;
        transition: all 0.3s ease;
    }
    
    .challenge-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 25px rgba(255, 100, 0, 0.6);
    }
    
    /* Progress bar */
    .progress-container {
        width: 100%;
        background-color: rgba(30, 10, 0, 0.7);
        border-radius: 10px;
        margin: 10px 0;
    }
    
    .progress-bar {
        height: 20px;
        border-radius: 10px;
        background: linear-gradient(90deg, #ff8c00, #ff4500);
        text-align: center;
        line-height: 20px;
        color: white;
        transition: width 0.5s ease;
    }
    
    /* Typewriter effect */
    .typewriter {
        display: inline-block;
    }
    
    .typewriter-text {
        display: inline-block;
        overflow: hidden;
        border-right: 2px solid #ff8c00;
        white-space: nowrap;
        margin: 0;
        animation: typing 0.1s steps(1, end), blink-caret 0.75s step-end infinite;
    }
    
    @keyframes typing {
        from { width: 0 }
        to { width: 100% }
    }
    
    @keyframes blink-caret {
        from, to { border-color: transparent }
        50% { border-color: #ff8c00; }
    }
    
    /* Tavern comment styles */
    .tavern-comment {
        background: rgba(30, 10, 0, 0.5);
        border-left: 3px solid #ff8c00;
        padding: 10px;
        margin: 5px 0;
        border-radius: 0 8px 8px 0;
    }
    
    .tavern-comment-text {
        color: #ffd700;
        margin: 0;
        font-size: 0.9rem;
    }
    
    .tavern-comment-meta {
        color: #ff8c00;
        margin: 0;
        font-size: 0.7rem;
        text-align: right;
    }
</style>

<div class="dragon-bg"></div>
<div class="floating-dragon">
    <lottie-player 
        src="https://assets1.lottiefiles.com/packages/lf20_5itoujgu.json" 
        background="transparent" 
        speed="1" 
        style="width: 100%; height: 100%;" 
        loop 
        autoplay>
    </lottie-player>
</div>

<script src="https://unpkg.com/@lottiefiles/lottie-player@latest/dist/lottie-player.js"></script>
""", unsafe_allow_html=True)

# Rate limiting variables and LLM responder moved above the playground so UI
# callbacks can call it during the same Streamlit run.
LAST_REQUEST_TIME = 0
MIN_REQUEST_INTERVAL = 1.2  # seconds

@lru_cache(maxsize=100)
def generate_response(prompt: str, conversation_history: tuple, skip_style: bool = False):
    global LAST_REQUEST_TIME

    current_time = time.time()
    if current_time - LAST_REQUEST_TIME < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - (current_time - LAST_REQUEST_TIME))
    LAST_REQUEST_TIME = time.time()

    retries = 3
    backoff = 1
    # If we're explicitly in OFFLINE_MODE, return a friendly message immediately.
    if st.session_state.get('OFFLINE_MODE', False):
        return "(OFFLINE MODE) The Dragon's LLM is currently unavailable — responses are disabled while offline."

    # Compose the prompt. For code-generation flows we may skip the
    # stylized system prompt to avoid adding narrative text into code.
    if skip_style:
        full_prompt = f"Current conversation:\n"
    else:
        full_prompt = f"{your_style_prompt}\n\nCurrent conversation:\n"

    for role, content in conversation_history:
        full_prompt += f"{role}: {content}\n"
    full_prompt += f"assistant: "

    for _ in range(retries):
        # First, try Google Generative AI if it's available
        if genai_available:
            try:
                try:
                    from google.generativeai import GenerativeModel
                except Exception as e:
                    # Fall through to Groq if the import fails
                    raise

                model = GenerativeModel("gemini-2.0-flash")
                response = model.generate_content(full_prompt)
                return getattr(response, 'text', str(response))
            except Exception as e:
                # If Google fails for any reason, attempt Groq/OpenAI-compatible fallback
                groq_text = vibe_clients.call_groq(full_prompt, model="openai/gpt-oss-20b")
                if groq_text:
                    return groq_text

                # If the error looks like rate limiting, back off and retry
                if "RATE_LIMIT" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                # Otherwise return an informative error
                return f"Dragon fire temporarily dimmed ⚡ Error: {str(e)} 🔥 Please try again when the flames reignite"

        else:
            # Google not available — try Groq/OpenAI-compatible client directly
            try:
                groq_text = vibe_clients.call_groq(full_prompt, model="openai/gpt-oss-20b")
                if groq_text:
                    return groq_text
                else:
                    # Nothing returned, wait and retry
                    time.sleep(backoff)
                    backoff *= 2
                    continue
            except Exception as e:
                if "RATE_LIMIT" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                return f"Dragon fire temporarily dimmed ⚡ Error: {str(e)} 🔥 Please try again when the flames reignite"

    return "The dragon's breath is too hot 🚦 Wait a little and try again ✨"


# --- AI Code Playground (3-column split) ---
st.markdown("""
<h3 style="color:#ffa500; display:flex; align-items:center; margin-top:2rem; font-family: 'Cinzel Decorative', cursive;">🧪 AI Code Playground</h3>
<p style="color:#ffd700;">Prompt the assistant to generate code, edit it in-place, run and preview the output, download or share a permalink.</p>
""", unsafe_allow_html=True)

# initialize playground session state
if 'playground_prompt' not in st.session_state:
    st.session_state.playground_prompt = ''
if 'playground_code' not in st.session_state:
    st.session_state.playground_code = ''
if 'playground_lang' not in st.session_state:
    st.session_state.playground_lang = 'html'

# Load snippet from query param if present
params = st.query_params
if 'snippet' in params and params.get('snippet'):
    sid = params.get('snippet')[0]
    try:
        snippet = vibe_utils.get_snippet(sid)
        if snippet:
            st.session_state.playground_code = snippet.get('code', '')
            st.session_state.playground_lang = snippet.get('lang', 'html')
            st.session_state.playground_prompt = snippet.get('prompt', '')
    except Exception:
        pass


# Layout: Left - prompt/chat, Middle - editor, Right - preview
left, mid, right = st.columns([2, 6, 5])

with left:
    st.markdown('### Prompt & Chat')
    # show small chat history for context
    if st.session_state.get('messages'):
        for msg in st.session_state.messages[-6:]:
            role = msg.get('role')
            content = msg.get('content')
            if role == 'user':
                st.markdown(f"**You:** {content}")
            else:
                st.markdown(f"**Assistant:** {content}")

    st.markdown('---')
    st.text_input('Playground Prompt (press Generate to create code)', key='playground_prompt_input')
    st.selectbox('Language', options=['html', 'javascript', 'python'], key='playground_lang')
    gen_col1, gen_col2 = st.columns([2,1])
    with gen_col1:
        if st.button('Generate', key='playground_generate'):
            prompt_text = st.session_state.get('playground_prompt_input', '').strip()
            if prompt_text:
                st.session_state.playground_prompt = prompt_text
                # craft a language-aware instruction and explicitly pass language to the model
                lang = st.session_state.get('playground_lang', 'html')
                # Insist on code-only output and include the language in the instruction
                if lang in ('html', 'javascript'):
                    instruction = (
                        f"You are given the task: {prompt_text}\n"
                        f"REQUIREMENT: Return ONLY the fully working {lang.upper()} code (HTML/CSS/JS if needed). "
                        "Do NOT include any explanation, headings, markdown, or code fences — only raw source code."
                    )
                elif lang == 'python':
                    instruction = (
                        f"You are given the task: {prompt_text}\n"
                        "REQUIREMENT: Return ONLY valid Python 3 code. "
                        "Do NOT include any explanation, headings, markdown, or code fences — only raw source code."
                    )
                else:
                    instruction = f"You are given the task: {prompt_text}\nReturn ONLY the requested source code for language: {lang}."

                try:
                    conv = tuple((m['role'], m['content']) for m in st.session_state.get('messages', []))
                    gen = generate_response(instruction, conv, skip_style=True)
                    import re, json

                    # Delegate processing of the generator output (sanitization + deterministic fallback)
                    try:
                        sanitized = vibe_utils.process_generated_code(gen, prompt_text, lang=lang)
                    except Exception:
                        sanitized = ''

                    # If we have sanitized code (either from LLM or fallback), persist and optionally run it
                    if sanitized:
                        st.session_state.playground_code = sanitized
                        # Also update the textarea value so the editor reflects generated code immediately
                        try:
                            st.session_state['playground_textarea'] = sanitized
                        except Exception:
                            st.session_state.playground_textarea = sanitized
                        # If language is python, run immediately and cache result for preview
                        if lang == 'python':
                            try:
                                res = _run_code_safely(sanitized, lang='python', timeout=8)
                                st.session_state['playground_last_result'] = res
                                st.session_state['_preview_refresh'] = st.session_state.get('_preview_refresh', 0) + 1
                            except Exception as e:
                                st.session_state['playground_last_result'] = {"success": False, "stdout": "", "stderr": str(e)}
                except Exception as e:
                    st.error(f"Failed to generate code: {e}")
    with gen_col2:
        if st.button('Save Permalink', key='playground_save'):
            code_text = st.session_state.get('playground_code', '')
            lang = st.session_state.get('playground_lang', 'html')
            prompt_text = st.session_state.get('playground_prompt', '')
            sid = vibe_utils.save_snippet(code_text, lang=lang, prompt=prompt_text)
            # set query param (new Streamlit API)
            st.set_query_params(snippet=sid)
            st.success(f'Permalink saved — snippet id: {sid}')
            st.write(f"Shareable URL: ?snippet={sid} (copy your browser address bar to share)")

    st.markdown('---')
    st.markdown('Tip: After generation edit the code in the center editor. Use Run to refresh preview on the right.')

with mid:
    st.markdown('### Editor')
    # Editor: try monaco component, fallback to textarea
    # Use a single Streamlit textarea editor to avoid component-loading issues.
    # Initialize the session state key for the textarea before creating the widget
    # to avoid Streamlit warning about setting a widget both via default value and
    # via the Session State API.
    if 'playground_textarea' not in st.session_state:
        st.session_state['playground_textarea'] = st.session_state.get('playground_code', '')

    # If possible, embed a lightweight Monaco editor (CDN) so generated code
    # appears with syntax highlighting. This is a one-way sync (Python -> iframe).
    try:
        code_initial = st.session_state.get('playground_textarea', '') or ''
        lang = st.session_state.get('playground_lang', 'python')
        # Escape closing script tags and HTML-sensitive characters
        def _escape_html(s: str) -> str:
            return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        .replace('\u2028', '\\u2028').replace('\u2029', '\\u2029'))

        escaped = _escape_html(code_initial)

        monaco_html = f"""
        <!doctype html>
        <html>
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <style>
            html, body, #editor {{ height: 100%; margin: 0; padding: 0; background: #0b0b0f; }}
            .monaco-editor .margin, .monaco-editor .monaco-editor-background {{ background: #0b0b0f; }}
          </style>
        </head>
        <body>
        <div id="editor" style="height:100%; width:100%;"></div>
        <script src="https://unpkg.com/monaco-editor@0.39.0/min/vs/loader.js"></script>
        <script>
        require.config({{ paths: {{ 'vs': 'https://unpkg.com/monaco-editor@0.39.0/min/vs' }} }});
        require(['vs/editor/editor.main'], function() {{
            var editor = monaco.editor.create(document.getElementById('editor'), {{
                value: `{escaped}`,
                language: '{'javascript' if lang=='javascript' else ('html' if lang=='html' else 'python')}',
                theme: 'vs-dark',
                automaticLayout: true,
                minimap: {{ enabled: false }}
            }});
            // Expose a function to set the editor value from outside (useful when rerendered)
            window.setEditorValue = function(val) {{ editor.setValue(val); }};
        }});
        </script>
        </body>
        </html>
        """

        components.html(monaco_html, height=520, scrolling=True)
        # Keep playground_code mirrored to the session state for execution/download
        st.session_state.playground_code = st.session_state.get('playground_textarea', '')
    except Exception:
        # Fallback: simple textarea bound to session state
        ta = st.text_area('Code Editor', height=520, key='playground_textarea')
        st.session_state.playground_code = st.session_state.get('playground_textarea', '')

    run_col1, run_col2, run_col3 = st.columns([1,1,1])
    with run_col1:
        if st.button('Run', key='playground_run'):
            st.session_state['_preview_refresh'] = st.session_state.get('_preview_refresh', 0) + 1
    with run_col2:
        code_to_download = st.session_state.get('playground_code', '')
        lang = st.session_state.get('playground_lang', 'txt')
        filename = f"snippet.{ 'html' if lang=='html' else ('js' if lang=='javascript' else ('py' if lang=='python' else 'txt')) }"
        st.download_button('Download', data=code_to_download, file_name=filename)
    with run_col3:
        if st.button('Clear', key='playground_clear'):
            st.session_state.playground_code = ''

with right:
    st.markdown('### Live Preview')
    lang = st.session_state.get('playground_lang', 'html')
    code = st.session_state.get('playground_code', '')
    preview_refresh = st.session_state.get('_preview_refresh', 0)

    if lang in ('html', 'javascript'):
        # Wrap JS inside a simple HTML shell when needed
        if lang == 'javascript':
            html_wrapper = f"""
            <!doctype html>
            <html>
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <style>body{{background:#0b0b0f; color:#ddd;}}</style>
            </head>
            <body>
            <div id="preview-root"></div>
            <script>
            {code}
            </script>
            </body>
            </html>
            """
            components.html(html_wrapper, height=520, scrolling=True)
        else:
            # HTML preview: include minimal style for dark theme
            dark_html = f"<div style='background:#0b0b0f; color:#ddd; min-height:520px'>{code}</div>"
            components.html(dark_html, height=520, scrolling=True)
    elif lang == 'python':
        st.markdown('Run the Python code; stdout/stderr will appear below')
        if st.button('Execute Python (preview)', key='playground_exec') or preview_refresh:
            # Prefer cached result from generation-run, otherwise execute now.
            res = st.session_state.get('playground_last_result') if st.session_state.get('playground_last_result') else _run_code_safely(code, lang='python', timeout=8)
            st.subheader('Stdout')
            st.code(res.get('stdout', ''))
            st.subheader('Stderr')
            st.code(res.get('stderr', ''))
    else:
        st.markdown('No preview available for this language')



# --- Dragon Tales Functions ---
def submit_tale(title, content, author="Anonymous Dragon"):
    """Submit a new dragon tale to the collection"""
    try:
        tale_data = {
            "title": title,
            "content": content,
            "author": author,
            "rating": 0,
            "ratings_count": 0,
            "timestamp": _dt.datetime.now(_dt.timezone.utc)
        }
        
        if tales_collection is not None:
            tales_collection.insert_one(tale_data)
            st.success("Your tale has been added to the dragon's library! 📖")
            return True
        else:
            st.session_state.setdefault('temp_tales', []).append(tale_data)
            st.warning("Tale saved temporarily (DB not connected)")
            return True
    except Exception as e:
        st.error(f"The dragon burned your scroll! Error: {str(e)}")
        return False

def rate_tale(tale_id, rating):
    """Rate a dragon tale"""
    try:
        if tales_collection is not None:
            tale = tales_collection.find_one({"_id": tale_id})
            if tale:
                new_rating = ((tale['rating'] * tale['ratings_count']) + rating) / (tale['ratings_count'] + 1)
                tales_collection.update_one(
                    {"_id": tale_id},
                    {"$set": {"rating": new_rating}, "$inc": {"ratings_count": 1}}
                )
                st.toast("Your rating has been recorded! ⭐", icon="📜")
                return True
        else:
            st.warning("Rating saved temporarily (DB not connected)")
            return True
    except Exception as e:
        st.error(f"Couldn't record your rating: {str(e)}")
        return False

def show_tale_modal():
    """Show modal for submitting a new tale"""
    with st.form("tale_form", clear_on_submit=True):
        title = st.text_input("Tale Title", placeholder="The Dragon's Secret")
        content = st.text_area("Your Tale", height=200, 
                             placeholder="Once upon a time, in a land of code and fire...")
        submitted = st.form_submit_button("Submit to Dragon Library 🐉")
        
        if submitted and title.strip() and content.strip():
            if submit_tale(title.strip(), content.strip()):
                st.session_state.show_tale_modal = False
                st.rerun()

def display_tale(tale, expanded=False):
    """Display a dragon tale with rating options"""
    with st.expander(f"📜 {tale['title']} by {tale.get('author', 'Anonymous Dragon')}", expanded=expanded):
        st.markdown(f"""
        <div class="dragon-card" style="padding:1.5rem; margin:1rem 0;">
            <p style="color:#ffd700; font-size:1rem; white-space:pre-wrap;">{tale['content']}</p>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:1rem;">
                <div>
                    <span style="color:#ffa500;">Rating: </span>
                    <span style="color:#ffd700;">{"⭐" * int(round(tale.get('rating', 0)))}</span>
                    <span style="color:#ffa500; font-size:0.8rem;"> ({tale.get('ratings_count', 0)} ratings)</span>
                </div>
                <div>
                    <span style="color:#ffa500; font-size:0.8rem;">
                        {tale.get('timestamp', datetime.datetime.now()).strftime("%b %d, %Y")}
                    </span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Rating buttons
        cols = st.columns(5)
        with cols[0]:
            if st.button("⭐", key=f"rate1_{tale.get('_id', tale.get('title'))}"):
                rate_tale(tale.get('_id', tale.get('title')), 1)
        with cols[1]:
            if st.button("⭐⭐", key=f"rate2_{tale.get('_id', tale.get('title'))}"):
                rate_tale(tale.get('_id', tale.get('title')), 2)
        with cols[2]:
            if st.button("⭐⭐⭐", key=f"rate3_{tale.get('_id', tale.get('title'))}"):
                rate_tale(tale.get('_id', tale.get('title')), 3)
        with cols[3]:
            if st.button("⭐⭐⭐⭐", key=f"rate4_{tale.get('_id', tale.get('title'))}"):
                rate_tale(tale.get('_id', tale.get('title')), 4)
        with cols[4]:
            if st.button("⭐⭐⭐⭐⭐", key=f"rate5_{tale.get('_id', tale.get('title'))}"):
                rate_tale(tale.get('_id', tale.get('title')), 5)

# --- Enhanced Majestic Dragon Header ---
st.markdown("""
<div class="header">
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <div>
            <h1 style="margin:0; display:flex; align-items:center;">
                <span class="dragon-emoji" style="font-size:3rem">🐉</span>
                <span class="dragon-text" style="margin:0 20px;">Dragon Developer</span>
                <span class="code-emoji" style="font-size:3rem">💻</span>
            </h1>
            <p style="margin:0; opacity:0.9; font-size:1.3rem; color:#ffd700;">
                Ancient Wisdom · Fire Magic · Code Sorcery <span class="dragon-emoji" style="font-size:1.5rem">🏆</span>
            </p>
        </div>
        <div style="font-size:2.2rem;">
            <span class="code-emoji" style="animation-delay:0.1s">🔒</span>
            <span class="dragon-emoji" style="animation-delay:0.3s">✨</span>
            <span class="code-emoji" style="animation-delay:0.5s">🤖</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- Dragon Tales Section ---
st.markdown("""
<h3 style="color:#ffa500; display:flex; align-items:center; margin-top:2rem; font-family: 'Cinzel Decorative', cursive; font-size:1.8rem;">
    <span class="dragon-emoji" style="font-size:2rem">📜</span>
    <span style="margin-left:15px;">Dragon Tales</span>
</h3>
<p style="color:#ffd700;">
    Discover ancient dragon wisdom and share your own tales of code and magic...
</p>
""", unsafe_allow_html=True)

# Search and filter controls
col1, col2, col3 = st.columns([3, 2, 2])
with col1:
    search_query = st.text_input("Search tales", placeholder="Find tales of fire and code...")
with col2:
    sort_by = st.selectbox("Sort by", ["Newest", "Top Rated", "Oldest"])
with col3:
    min_rating = st.slider("Minimum rating", 0, 5, 0)

# Add tale button
if st.button("➕ Add Your Own Tale", key="add_tale_button"):
    st.session_state.show_tale_modal = True

# Show tale submission modal if triggered
if st.session_state.get('show_tale_modal', False):
    show_tale_modal()

# Display tales
try:
    if tales_collection is not None:
        query = {}
        if search_query:
            query["$text"] = {"$search": search_query}
        
        if min_rating > 0:
            query["rating"] = {"$gte": min_rating}
        
        if sort_by == "Newest":
            tales = list(tales_collection.find(query).sort("timestamp", -1))
        elif sort_by == "Top Rated":
            tales = list(tales_collection.find(query).sort("rating", -1))
        else:  # Oldest
            tales = list(tales_collection.find(query).sort("timestamp", 1))
    else:
        tales = st.session_state.get('temp_tales', [])
        if search_query:
            tales = [t for t in tales if search_query.lower() in t['title'].lower() or search_query.lower() in t['content'].lower()]
        if min_rating > 0:
            tales = [t for t in tales if t.get('rating', 0) >= min_rating]
        if sort_by == "Newest":
            tales = sorted(tales, key=lambda x: x.get('timestamp', datetime.datetime.now()), reverse=True)
        elif sort_by == "Top Rated":
            tales = sorted(tales, key=lambda x: x.get('rating', 0), reverse=True)
        else:  # Oldest
            tales = sorted(tales, key=lambda x: x.get('timestamp', datetime.datetime.now()))
    
    if not tales:
        st.markdown("""
        <div class="dragon-card" style="text-align:center; padding:2rem;">
            <h4 style="color:#ffa500;">No tales found in the dragon's library yet!</h4>
            <p style="color:#ffd700;">Be the first to share your story of code and magic...</p>
            <span class="dragon-emoji" style="font-size:3rem;">📜</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        for tale in tales:
            display_tale(tale)
            
except Exception as e:
    st.error(f"The dragon's library is in disarray! {str(e)}")

# --- Dragon's Tavern Comment Section ---
with st.sidebar:
    st.markdown("""
    <h3 style="color:#ffa500; display:flex; align-items:center; font-family: 'Cinzel Decorative', cursive;">
        <span class="dragon-emoji" style="font-size:1.8rem">🍻</span>
        <span style="margin-left:10px;">Dragon's Tavern</span>
    </h3>
    <p style="color:#ffd700; font-size:0.9rem;">
        Share your thoughts with fellow adventurers in the dragon's tavern!
    </p>
    """, unsafe_allow_html=True)
    
    # Comment input form
    with st.form("comment_form", clear_on_submit=True):
        comment = st.text_area("Leave your mark in the tavern:", height=100, 
                             placeholder="What wisdom do you bring today?")
        submitted = st.form_submit_button("Post to Tavern 🍻")
        
        if submitted and comment.strip():
            try:
                comment_data = {
                    "text": comment.strip(),
                    "timestamp": _dt.datetime.now(_dt.timezone.utc),
                    "user": "Anonymous Dragon"
                }
                
                if comments_collection is not None:
                    comments_collection.insert_one(comment_data)
                    st.toast("Your voice echoes through the tavern!", icon="🍻")
                else:
                    st.session_state.setdefault('temp_comments', []).append({
                        "text": comment.strip(),
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "user": "Anonymous Dragon"
                    })
                    st.toast("Comment saved temporarily (DB not connected)", icon="⚠️")
            except Exception as e:
                st.error(f"The dragon spilled your mead! Error: {str(e)}")
    
    # Display recent comments
    st.markdown("""
    <div style="margin-top:20px; max-height:400px; overflow-y:auto; border-top:1px solid #ff8c0055; padding-top:10px;">
        <h4 style="color:#ffa500; font-family: 'Cinzel Decorative', cursive;">
            Recent Tavern Chatter
        </h4>
    """, unsafe_allow_html=True)
    
    try:
        if comments_collection is not None:
            recent_comments = list(comments_collection.find().sort("timestamp", -1).limit(10))
        else:
            recent_comments = st.session_state.get('temp_comments', [])[-10:]
            
        for comment in reversed(recent_comments):  # Show newest first
            timestamp = comment.get("timestamp")
            if isinstance(timestamp, datetime.datetime):
                timestamp = timestamp.strftime("%b %d, %H:%M")
            elif isinstance(timestamp, str):
                pass  # already formatted
            else:
                timestamp = "Just now"
                
            st.markdown(f"""
            <div class="tavern-comment">
                <p class="tavern-comment-text">{comment['text']}</p>
                <p class="tavern-comment-meta">~ {comment.get('user', 'Anonymous Dragon')} • {timestamp}</p>
            </div>
            """, unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"The tavern scrolls are damaged! {str(e)}")
    
    st.markdown("</div>", unsafe_allow_html=True)

# --- Enhanced Dragon Profile ---
st.markdown("""
<div class="dragon-card">
    <h3 style="margin-top:0; color:#ffa500; display:flex; align-items:center;">
        <span class="dragon-emoji" style="font-size:2.2rem">🧙‍♂️</span>
        <span style="margin-left:15px; font-family: 'Cinzel Decorative', cursive; font-size:1.8rem;">The Code Dragon</span>
    </h3>
    <p style="color:#ffd700; font-size:1.1rem;">
        <span class="dragon-emoji" style="font-size:1.3rem">🔥</span> Ancient guardian of programming wisdom<br>
        <span class="dragon-emoji" style="font-size:1.3rem">⚔️</span> Master of fire and code magic<br>
        <span class="dragon-emoji" style="font-size:1.3rem">🏮</span> Keeper of the eternal developer flame
    </p>
    <div class="profile-highlight">
        <p style="color:#ffd700; margin:0; font-size:1.1rem;">
        "I am the eternal Code Dragon, born from the fires of the first compiler. For millennia I have guarded the sacred knowledge of programming, 
        watching civilizations rise and fall while the art of code endures. Join me in this eternal quest for knowledge, 
        and I shall share the secrets that can make your code legendary."
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

# --- Enhanced Chat Interface ---
st.markdown("""
<h3 style="color:#ffa500; display:flex; align-items:center; margin-top:2rem; font-family: 'Cinzel Decorative', cursive; font-size:1.8rem;">
    <span class="dragon-emoji" style="font-size:2rem">🗨️</span>
    <span style="margin-left:15px;">Dragon Wisdom Chamber</span>
</h3>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "By the ancient fire of code dragons 🐉 I greet you, Developer! 🔥 What knowledge shall we forge today? 💻 #DragonWisdom"}
    ]

# Show chat messages
for msg in st.session_state.messages:
    avatar = None
    with st.chat_message(msg["role"], avatar=avatar):
        content = msg["content"]
        for emoji_char in ["🐉", "🔥", "💻", "🏮", "✨", "⚔️", "🔒", "🤖", "🏆"]:
            if emoji_char in content:
                content = content.replace(emoji_char, f'<span class="{"dragon-emoji" if emoji_char in ["🐉","🔥","🏮","✨","⚔️","🏆"] else "code-emoji"}">{emoji_char}</span>')
        st.markdown(content, unsafe_allow_html=True)



# Chat input
if prompt := st.chat_input("Speak your question to the dragon...", key="chat_input"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=None):
        st.markdown(prompt, unsafe_allow_html=True)
    
    conversation_history = tuple((msg["role"], msg["content"]) for msg in st.session_state.messages)

    with st.spinner("Consulting the ancient dragon scrolls..."):
        # Generate response
        reply = generate_response(prompt, conversation_history)

        # If the reply looks like an error message from the LLM, show the Dragon Spell card
        if any(token in reply for token in ["(LLM error)", "Dragon fire temporarily dimmed", "OFFLINE MODE", "Error:"]):
            st.markdown(f"""
            <div style="border:2px dashed #ff8c00; padding:16px; border-radius:12px; background:linear-gradient(90deg,#2a0000,#120200); color:#ffd700;">
                <h3>Dragon Spell Failed 🔥</h3>
                <p style="color:#ffb366;">The dragon's incantation could not be completed.</p>
                <pre style="color:#ffd700; background:#1a0500; padding:12px; border-radius:8px;">{reply}</pre>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Stream the response word by word with typing effect
            response_container = st.empty()
            full_response = ""
            # Split reply into words but preserve emojis adjacent to words
            words = []
            current_word = ""
            for char in reply:
                if char.isspace():
                    if current_word:
                        words.append(current_word)
                        current_word = ""
                    words.append(char)
                else:
                    current_word += char
            if current_word:
                words.append(current_word)

            # Display words one by one
            for word in words:
                full_response += word
                time.sleep(0.05)  # Adjust speed as needed

                # Format the response with emoji effects
                formatted_response = full_response
                for emoji_char in ["🐉", "🔥", "💻", "🏮", "✨", "⚔️", "🔒", "🤖", "🏆"]:
                    if emoji_char in formatted_response:
                        formatted_response = formatted_response.replace(emoji_char, f'<span class="{"dragon-emoji" if emoji_char in ["🐉","🔥","🏮","✨","⚔️","🏆"] else "code-emoji"}">{emoji_char}</span>')

                response_container.markdown(formatted_response, unsafe_allow_html=True)

    st.session_state.messages.append({"role": "assistant", "content": reply})

    if collection is not None:
        try:
            collection.insert_one({
                "user": prompt,
                "bot": reply,
                "timestamp": _dt.datetime.now(_dt.timezone.utc),
                "session_id": st.session_state.get("session_id", "default")
            })
        except Exception as e:
            st.warning(f"Dragon hoard inaccessible ⚠️ {str(e)}")

# --- Enhanced Dragon Footer ---
st.markdown("""
<div style="
    background: linear-gradient(90deg, #8b0000, #1a0500);
    color: rgba(255, 215, 0, 0.8);
    padding: 1.8rem;
    text-align: center;
    border-radius: 15px 15px 0 0;
    margin-top: 3rem;
    font-size: 1rem;
    font-family: 'Cinzel', serif;
    border-top: 3px solid #ff8c00;
    box-shadow: 0 -5px 25px rgba(255, 69, 0, 0.3);
">
    <div style="display: flex; justify-content: center; gap: 25px; margin-bottom: 15px;">
        <span class="code-emoji" style="font-size:1.8rem">💻</span>
        <span class="dragon-emoji" style="font-size:1.8rem">🔥</span>
        <span class="code-emoji" style="font-size:1.8rem">🔒</span>
        <span class="dragon-emoji" style="font-size:1.8rem">🏮</span>
    </div>
    © 2025 Dragon Developer | Pudishh | Version 4.0
</div>
""", unsafe_allow_html=True)