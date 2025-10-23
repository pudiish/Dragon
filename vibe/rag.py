# shim: re-export the implementation from vibe.services.rag
from .services.rag import RAGClient  # type: ignore

__all__ = ["RAGClient"]
