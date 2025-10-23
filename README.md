# VibeMind — Voice AI Companion

VibeMind is a Streamlit-based talking AI assistant that blends Google Gemini Flash for reasoning with local RAG memory (ChromaDB + sentence-transformers) and voice I/O (gTTS + pygame). This repo contains a single orchestrator entrypoint: `app.py`.

Quick start
1. Copy `.env.example` to `.env` and fill your keys.
2. Create and activate a virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Start the app:

```bash
./start.sh
```

Key files
- `app.py` — Streamlit entrypoint and orchestrator
- `requirements.txt` — runtime deps (Streamlit, google-generativeai, sentence-transformers, chromadb, pymongo, gTTS, pygame)
- `chroma_db/` — persistent vector DB folder
- `model_cache/` — local cache for sentence-transformers
- `vibe/` — helper modules (config, audio, rag, db, watcher)

Environment variables (see `.env.example`)
- `GEMINI_API_KEY` — Google Gemini API key
- `MONGO_URI` — Optional MongoDB connection string
- `CHROMA_DB_PATH` — Path to ChromaDB folder
- `MODEL_CACHE_PATH` — Path to model cache

Verification checklist
- Open Streamlit URL printed in terminal (default http://localhost:8501)
- Test chat input: app should respond using RAG or Gemini
- Test voice output: click speak or trigger voice action; gTTS audio should play (pygame required)

Notes
- The app is modular; small helper modules provide safe fallbacks when external services are not available.
