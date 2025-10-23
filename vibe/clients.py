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
