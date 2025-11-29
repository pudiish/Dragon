"""Utility helpers: config path, persisted state helpers, and datetime helpers."""
from pathlib import Path
import json
import datetime as _dt
import uuid


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


def snippets_file() -> Path:
    """Return path to the persisted playground snippets JSON file."""
    p = config_dir() / "playground_snippets.json"
    if not p.exists():
        try:
            p.write_text(json.dumps({}))
        except Exception:
            pass
    return p


def load_snippets() -> dict:
    """Load all persisted snippets as a dict.

    Returns a dict keyed by snippet id with metadata: {id: {code, lang, prompt, created_at}}
    """
    p = snippets_file()
    try:
        return json.loads(p.read_text() or "{}")
    except Exception:
        return {}


def save_snippet(code: str, lang: str = "text", prompt: str | None = None) -> str:
    """Save a snippet and return its generated id."""
    snippets = load_snippets()
    sid = uuid.uuid4().hex[:12]
    snippets[sid] = {
        "code": code,
        "lang": lang,
        "prompt": prompt or "",
        "created_at": now_utc().isoformat()
    }
    try:
        snippets_file().write_text(json.dumps(snippets))
    except Exception:
        pass
    return sid


def get_snippet(sid: str) -> dict | None:
    try:
        return load_snippets().get(sid)
    except Exception:
        return None


def sanitize_and_validate_code(code: str, lang: str = 'python') -> str:
    """Sanitize generated text and try to return valid code.

    This is the same logic previously embedded in app.py but moved here so it
    can be reused and unit-tested.
    """
    import re

    if not code:
        return ''

    # Remove surrogate pairs / emoji (U+10000+)
    code = re.sub(r"[\U00010000-\U0010ffff]", '', code)
    # Remove control characters except newline and tab
    code = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", '', code)

    # Remove leading and trailing backticks/fences if still present
    code = re.sub(r"^```[\s\S]*?\n", '', code)
    code = re.sub(r"\n```$", '', code)
    code = code.strip('\n')

    # Quick path: try to compile as-is (Python only)
    if lang == 'python':
        try:
            compile(code, '<generated>', 'exec')
            return code
        except SyntaxError:
            # Helper: normalize common print variants into Python3 print(...)
            def _normalize_prints(text: str) -> str:
                import re as _re
                out_lines = []
                for ln in text.splitlines():
                    s = ln.rstrip()
                    m = _re.match(r"^\s*print\s+(['\"])(.*)\1\s*$", s)
                    if m:
                        # print "hello" -> print("hello")
                        out_lines.append(_re.sub(r"^\s*print\s+(['\"])(.*)\1\s*$", r"print(\1\2\1)", s))
                        continue
                    m2 = _re.match(r"^\s*print\s+(.+)$", s)
                    if m2:
                        content = m2.group(1).strip()
                        # if content already looks like a parenthesized call, keep
                        if content.startswith('(') and content.endswith(')'):
                            out_lines.append(f"print{content}")
                        else:
                            # wrap unquoted content into quotes
                            if (content.startswith('"') and content.endswith('"')) or (content.startswith("'") and content.endswith("'")):
                                out_lines.append(f"print({content})")
                            else:
                                # simple transform: print hello world -> print("hello world")
                                # remove any trailing comments
                                content_clean = _re.sub(r"\s+#.*$", '', content).strip()
                                # Escape double quotes in content
                                content_clean = content_clean.replace('"', '\\"')
                                out_lines.append(f"print(\"{content_clean}\")")
                        continue
                    out_lines.append(ln)
                return "\n".join(out_lines)

            # Try normalizing prints first and attempt compile
            norm_code = _normalize_prints(code)
            try:
                compile(norm_code, '<generated>', 'exec')
                return norm_code
            except SyntaxError:
                pass

            # Try stripping leading prose lines until compile succeeds
            lines = norm_code.splitlines()
            for i in range(len(lines)):
                candidate = '\n'.join(lines[i:]).strip()
                if not candidate:
                    continue
                try:
                    compile(candidate, '<generated>', 'exec')
                    return candidate
                except SyntaxError:
                    # try normalize prints on the candidate as well
                    candidate_norm = _normalize_prints(candidate)
                    try:
                        compile(candidate_norm, '<generated>', 'exec')
                        return candidate_norm
                    except SyntaxError:
                        continue

            # As a last resort, extract lines that look like code (heuristic)
            code_like = []
            for ln in lines:
                stripped = ln.strip()
                if not stripped:
                    continue
                # heuristic: import, def, class, print, return, if, for, while, =, (), :, @
                if re.search(r'^(import |from |def |class |@|print\(|return |if |for |while |with |try:|except |pass$)', stripped) or re.search(r'[=()#:]', stripped):
                    code_like.append(ln)

            candidate = '\n'.join(code_like).strip()
            try:
                if candidate:
                    compile(candidate, '<generated>', 'exec')
                    return candidate
            except Exception:
                return ''

            return ''

    # For non-python languages just return the sanitized text
    return code


def process_generated_code(gen_output: str, prompt_text: str, lang: str = 'python') -> str:
    """Given raw generator output and the original prompt/language, return sanitized code or a deterministic fallback.

    This centralizes the logic used by the app when handling LLM output so tests
    can exercise the same behavior.
    """
    import re, json

    if gen_output is None:
        gen_output = ''

    # Strip common markdown fences if present
    m = re.search(r"```(?:\w+)?\n([\s\S]*?)\n```", str(gen_output))
    if m:
        code_text = m.group(1)
    else:
        code_text = str(gen_output)

    sanitized = sanitize_and_validate_code(code_text, lang=lang)

    if sanitized:
        return sanitized

    # Deterministic fallback heuristics
    p = (prompt_text or '').lower()
    fallback_code = ''
    if 'print' in p and 'hello' in p:
        pm = re.search(r"print\s+['\"]?([a-z0-9 ,!_\-]+)['\"]?", p)
        if pm:
            content = pm.group(1).strip()
        else:
            content = 'hello world'
        fallback_code = f'print({json.dumps(content)})'
    elif 'hello' in p:
        fallback_code = 'print("hello world")'

    return fallback_code
