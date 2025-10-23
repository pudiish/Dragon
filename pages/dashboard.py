import streamlit as st
import time
import datetime as _dt
import threading
import json
from vibe.config import settings
from pymongo import MongoClient
import requests
from pathlib import Path

st.set_page_config(page_title="Dragon Dashboard", page_icon="📊")

st.title("Dragon — Health Dashboard")

st.markdown("This dashboard shows the status of external services and continuous health checks.")

# Health check functions
def check_mongo(uri: str) -> dict:
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.server_info()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_genai_available() -> dict:
    try:
        import google.generativeai as genai
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_gtts() -> dict:
    try:
        from gtts import gTTS
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_external_url(url: str) -> dict:
    try:
        r = requests.head(url, timeout=3)
        return {"ok": r.status_code < 400, "status_code": r.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# health status path in ~/.config/dragon
config_dir = Path.home() / ".config" / "dragon"
config_dir.mkdir(parents=True, exist_ok=True)
health_file = config_dir / "health_status.json"


def _write_health(data: dict):
    try:
        health_file.write_text(json.dumps(data))
    except Exception:
        pass


def run_checks_once() -> dict:
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    result = {"timestamp": now, "checks": {}}
    # Mongo
    result["checks"]["mongo"] = check_mongo(settings.MONGO_URI) if settings.MONGO_URI else {"ok": False, "error": "MONGO_URI not set"}
    # GenAI import
    result["checks"]["genai"] = check_genai_available() if settings.GEMINI_API_KEY else {"ok": False, "error": "GEMINI_API_KEY not set"}
    # gTTS
    result["checks"]["gtts"] = check_gtts()
    # GROQ/OpenAI surfaces (use env if present)
    groq_url = getattr(settings, "GROQ_API_URL", "https://api.groq.com/openai/v1")
    result["checks"]["groq"] = check_external_url(groq_url)
    result["checks"]["openai"] = check_external_url(getattr(settings, "OPENAI_API_URL", "https://api.openai.com"))
    _write_health(result)
    return result


# Background worker management
_worker = None
_worker_stop = threading.Event()


def _worker_fn(interval: int):
    while not _worker_stop.is_set():
        run_checks_once()
        _worker_stop.wait(interval)


# UI
col1, col2 = st.columns(2)
with col1:
    st.subheader("MongoDB")
    if settings.MONGO_URI:
        r = run_checks_once()["checks"]["mongo"]
        if r.get("ok"):
            st.success("MongoDB reachable")
        else:
            st.error(f"MongoDB error: {r.get('error')}")
    else:
        st.warning("MONGO_URI not configured")

with col2:
    st.subheader("GenAI Client")
    if settings.GEMINI_API_KEY:
        r = run_checks_once()["checks"]["genai"]
        if r.get("ok"):
            st.success("google.generativeai import succeeded")
        else:
            st.error(f"GenAI import error: {r.get('error')}")
    else:
        st.warning("GEMINI_API_KEY not configured")

st.markdown("---")
st.subheader("Continuous Health Check")
interval = st.number_input("Check interval (seconds)", min_value=2, value=10)
start = st.button("Start background health checks")
stop = st.button("Stop background health checks")
manual = st.button("Run checks now")

if manual:
    res = run_checks_once()
    st.json(res)

if start:
    if _worker and _worker.is_alive():
        st.info("Health worker already running")
    else:
        _worker_stop.clear()
        _worker = threading.Thread(target=_worker_fn, args=(int(interval),), daemon=True)
        _worker.start()
        st.success("Background health checks started")

if stop:
    if _worker:
        _worker_stop.set()
        st.success("Stopping background health checks (may take up to interval seconds)")
    else:
        st.info("No health worker running")

if health_file.exists():
    try:
        data = json.loads(health_file.read_text())
        st.markdown(f"**Last run:** {data.get('timestamp')}")
        st.json(data.get('checks', {}))
    except Exception as e:
        st.error(f"Couldn't read health file: {str(e)}")
else:
    st.info("No health data yet. Run manual checks or start the background worker.")
