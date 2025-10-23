"""Utility helpers: config path, persisted state helpers, and datetime helpers."""
from pathlib import Path
import json
import datetime as _dt


def config_dir() -> Path:
    p = Path.home() / ".config" / "dragon"
    p.mkdir(parents=True, exist_ok=True)
    return p


def persisted_offline_file() -> Path:
    return config_dir() / "offline_state.json"


def read_persisted_offline() -> bool | None:
    p = persisted_offline_file()
    if p.exists():
        try:
            return bool(json.loads(p.read_text()).get('offline', False))
        except Exception:
            return None
    return None


def write_persisted_offline(val: bool):
    p = persisted_offline_file()
    try:
        p.write_text(json.dumps({'offline': bool(val)}))
    except Exception:
        pass


def now_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)
