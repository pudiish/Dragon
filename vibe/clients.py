"""Centralized client factories for external services.

This module provides small helper functions to create/return configured clients
so the rest of the codebase can import from a single place. Factories are
defensive (return None on missing config) and attempt lazy imports.
"""
from typing import Optional
import os

from .config import settings


def create_mongo_client() -> Optional[object]:
    uri = settings.MONGO_URI
    if not uri:
        return None
    try:
        from pymongo import MongoClient
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # validate connectivity
        client.server_info()
        return client
    except Exception:
        return None


def create_groq_client() -> Optional[object]:
    url = getattr(settings, 'GROQ_API_URL', None)
    key = getattr(settings, 'GROQ_API_KEY', None)
    if not url or not key:
        return None
    # Prefer official OpenAI Python SDK if available (it can be pointed at Groq via base_url)
    try:
        from openai import OpenAI as OpenAISDK

        class _SDKWrapper:
            def __init__(self, api_key: str, base_url: str):
                # instantiate official client with provided base_url
                self._client = OpenAISDK(api_key=api_key, base_url=base_url)

            def generate(self, prompt: str, model: str = None) -> str:
                # Use the /responses compatibility surface
                kwargs = {
                    "model": model or settings.OPENAI_MODEL,
                    "input": prompt,
                }
                resp = self._client.responses.create(**kwargs)
                # Try common fields
                if isinstance(resp, dict):
                    for k in ("output_text", "output", "result", "text"):
                        if k in resp:
                            return resp[k]
                    # attempt to stringify
                    return str(resp)
                # SDK may return an object with .output_text
                try:
                    return getattr(resp, "output_text", str(resp))
                except Exception:
                    return str(resp)

        return _SDKWrapper(api_key=key, base_url=url)
    except Exception:
        # Fallback to internal GroqClient wrapper
        try:
            from .groq import GroqClient
            return GroqClient(api_url=url, api_key=key)
        except Exception:
            return None


def create_openai_client() -> Optional[object]:
    url = getattr(settings, 'OPENAI_API_URL', None)
    key = getattr(settings, 'OPENAI_API_KEY', None)
    if not url or not key:
        return None
    # Prefer official SDK when available
    try:
        from openai import OpenAI as OpenAISDK

        class _SDKOpenAIWrapper:
            def __init__(self, api_key: str, base_url: str):
                self._client = OpenAISDK(api_key=api_key, base_url=base_url)

            def generate(self, prompt: str, model: str = None) -> str:
                kwargs = {"model": model or settings.OPENAI_MODEL, "input": prompt}
                resp = self._client.responses.create(**kwargs)
                try:
                    return getattr(resp, "output_text", str(resp))
                except Exception:
                    return str(resp)

        return _SDKOpenAIWrapper(api_key=key, base_url=url)
    except Exception:
        try:
            from .openai import OpenAIClient
            return OpenAIClient(api_url=url, api_key=key)
        except Exception:
            return None


def init_genai(api_key: str | None) -> bool:
    """Attempt to configure google.generativeai if available and a key is provided.

    Returns True when configured, False otherwise.
    """
    if not api_key:
        return False
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        return True
    except Exception:
        return False


def call_groq(prompt: str, model: str = None) -> Optional[str]:
    """Call Groq (or OpenAI-compatible endpoint provided in settings) and return text or None.

    This function tries to create a GroqClient first and call its generate method. If not
    available, try the OpenAIClient wrapper.
    """
    groq = create_groq_client()
    if groq is not None:
        try:
            return groq.generate(prompt)
        except Exception:
            return None

    openai = create_openai_client()
    if openai is not None:
        try:
            return openai.generate(prompt, model=model or settings.OPENAI_MODEL)
        except Exception:
            return None

    return None
