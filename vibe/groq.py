"""Minimal Groq API client wrapper.

This client expects two environment variables (or constructor args):
- GROQ_API_URL: full URL to the Groq inference endpoint
- GROQ_API_KEY: bearer key

The Groq API has multiple shapes; this wrapper sends a POST with JSON
{'prompt': prompt} and tries to extract a sensible text field from the
JSON response. Adjust `parse_response` if your Groq endpoint uses a different schema.
"""
from typing import Optional
import requests
import os
import json
from types import SimpleNamespace
from dataclasses import dataclass
from requests import Response


class GroqClient:
    def __init__(self, api_url: str, api_key: str, timeout: float = 15.0):
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout
        # provide a simple chat namespace to mimic the groq SDK surface used by the user
        self.chat = SimpleNamespace()
        self.chat.completions = SimpleNamespace()
        self.chat.completions.create = self._chat_completions_create
        # Provide OpenAI 'responses' API compatibility
        self.responses = SimpleNamespace()
        self.responses.create = self._responses_create

    def generate(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"prompt": prompt}
        try:
            # Some users set GROQ_API_URL to a base OpenAI-compatible path (e.g. https://api.groq.com/openai/v1)
            # The actual text/completions endpoint may be at /completions. Append if not present.
            request_url = self.api_url
            if not request_url.rstrip('/').endswith('/completions'):
                request_url = request_url.rstrip('/') + '/completions'

            resp = requests.post(request_url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return self.parse_response(data)
        except Exception as e:
            raise

    def _stream_response_lines(self, resp: Response):
        """Yield lines from a streaming response (text/event-stream or chunked JSON)."""
        # requests.iter_lines will handle chunked transfer encoding nicely
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:
                continue
            # Many streaming endpoints use SSE-style "data: {...}\n\n" framing
            line = raw
            if line.startswith("data:"):
                line = line[len("data:"):].strip()
            yield line

    def _make_chunk_like(self, text: str):
        """Return a minimal object with .choices[0].delta.content like the user's loop expects."""
        # SimpleNamespace lets attribute access work like objects
        delta = SimpleNamespace(content=text)
        choice = SimpleNamespace(delta=delta)
        wrapper = SimpleNamespace(choices=[choice])
        return wrapper

    def _chat_completions_create(self, model: str, messages, temperature: float = 1.0,
                                 max_completion_tokens: int = 1024, top_p: float = 1.0,
                                 reasoning_effort: Optional[str] = None,
                                 stream: bool = False, stop=None, **kwargs):
        """
        Call the Groq chat completions endpoint. If stream=True, returns a generator
        that yields chunk-like objects compatible with the user's loop.
        Otherwise returns the parsed JSON (synchronous mode).
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_completion_tokens,
            "top_p": top_p,
        }
        if reasoning_effort is not None:
            payload["reasoning_effort"] = reasoning_effort
        if stop is not None:
            payload["stop"] = stop

        # If streaming is requested, attempt to use the endpoint with stream semantics
        try:
            if stream:
                # For streaming, request the chat/completions endpoint. Many users set the base url
                # to something like https://api.groq.com/openai/v1 — ensure we target the chat completions path.
                request_url = self.api_url
                if not request_url.rstrip('/').endswith('/chat/completions'):
                    request_url = request_url.rstrip('/') + '/chat/completions'

                # For streaming, request with stream=True so we can iterate over lines
                resp = requests.post(request_url, json=payload, headers=headers, timeout=self.timeout, stream=True)
                resp.raise_for_status()

                def generator():
                    for line in self._stream_response_lines(resp):
                        # try to parse json from the line; if fails, treat as raw text
                        try:
                            obj = json.loads(line)
                        except Exception:
                            # sometimes the server sends raw text or partial fragments
                            yield self._make_chunk_like(line)
                            continue

                        # The server may include incremental deltas under various keys.
                        # Common shapes: {'delta': {'content': '...'}} or {'text': '...'}
                        text = None
                        if isinstance(obj, dict):
                            # delta style
                            if "delta" in obj and isinstance(obj["delta"], dict):
                                text = obj["delta"].get("content")
                            # direct text
                            if text is None:
                                for k in ("text", "output", "result", "content"):
                                    if k in obj:
                                        v = obj[k]
                                        if isinstance(v, str):
                                            text = v
                                            break

                        if text is None:
                            # fallback: stringify object
                            text = json.dumps(obj)

                        yield self._make_chunk_like(text)

                return generator()

            # Non-streaming path (chat/completions)
            request_url = self.api_url
            if not request_url.rstrip('/').endswith('/chat/completions') and not request_url.rstrip('/').endswith('/completions'):
                # prefer chat/completions for chat endpoints
                request_url = request_url.rstrip('/') + '/chat/completions'
            resp = requests.post(request_url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data
        except Exception:
            raise

    def _responses_create(self, model: str = None, input=None, messages=None, temperature: float = 1.0,
                          max_completion_tokens: int = 1024, top_p: float = 1.0,
                          stream: bool = False, stop=None, **kwargs):
        """
        Call the OpenAI-compatible /responses endpoint on Groq. Accepts either an
        `input` string or `messages` list (will be concatenated) to support both
        usage patterns. If stream=True, returns a generator yielding chunk-like
        objects with .choices[0].delta.content to mimic the chat streaming loop.
        Otherwise returns the parsed JSON response.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Normalize input: prefer explicit input, else join messages
        final_input = input
        if final_input is None and messages:
            try:
                parts = []
                for m in messages:
                    # messages expected as dicts with role/content
                    if isinstance(m, dict) and 'content' in m:
                        parts.append(m['content'])
                    elif isinstance(m, (list, tuple)) and len(m) >= 2:
                        parts.append(m[1])
                final_input = "\n".join(parts)
            except Exception:
                final_input = None

        payload = {
            "model": model or "openai/gpt-oss-20b",
            "input": final_input if final_input is not None else (input or ""),
            "temperature": temperature,
            "top_p": top_p,
        }
        if stop is not None:
            payload["stop"] = stop

        try:
            if stream:
                request_url = self.api_url
                if not request_url.rstrip('/').endswith('/responses'):
                    request_url = request_url.rstrip('/') + '/responses'

                resp = requests.post(request_url, json=payload, headers=headers, timeout=self.timeout, stream=True)
                resp.raise_for_status()

                def generator():
                    for line in self._stream_response_lines(resp):
                        # Try to parse JSON chunks; otherwise forward raw text
                        try:
                            obj = json.loads(line)
                        except Exception:
                            yield self._make_chunk_like(line)
                            continue

                        # Many /responses streaming formats include 'delta' or 'output'
                        text = None
                        if isinstance(obj, dict):
                            # OpenAI-like delta
                            if 'delta' in obj and isinstance(obj['delta'], dict):
                                text = obj['delta'].get('content')
                            # direct output_text or output
                            if text is None:
                                if 'text' in obj and isinstance(obj['text'], str):
                                    text = obj['text']
                                elif 'output_text' in obj and isinstance(obj['output_text'], str):
                                    text = obj['output_text']
                                elif 'output' in obj:
                                    # try to extract text pieces
                                    out = obj['output']
                                    if isinstance(out, list):
                                        pieces = []
                                        for it in out:
                                            if isinstance(it, dict) and 'content' in it:
                                                content = it['content']
                                                if isinstance(content, list):
                                                    for c in content:
                                                        if isinstance(c, dict) and 'text' in c:
                                                            pieces.append(c['text'])
                                            elif isinstance(it, str):
                                                pieces.append(it)
                                        if pieces:
                                            text = ' '.join(pieces)

                        if text is None:
                            text = json.dumps(obj)

                        yield self._make_chunk_like(text)

                return generator()

            # Non-streaming responses path
            request_url = self.api_url
            if not request_url.rstrip('/').endswith('/responses'):
                request_url = request_url.rstrip('/') + '/responses'
            resp = requests.post(request_url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            raise

    def parse_response(self, data: dict) -> str:
        # Common possible fields: 'text', 'output', 'result', or nested structures
        if not isinstance(data, dict):
            return str(data)

        # Try common keys
        for key in ("text", "output", "result", "generation", "generations"):
            if key in data:
                val = data[key]
                if isinstance(val, str):
                    return val
                # if it's a list/object, try to extract text
                if isinstance(val, list) and val:
                    first = val[0]
                    if isinstance(first, dict) and "text" in first:
                        return first["text"]
                    if isinstance(first, str):
                        return first

        # Fallback: return JSON string
        return str(data)
