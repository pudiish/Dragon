"""RAG client wrapper (moved to vibe.services).

This file is a copy of the original `vibe/rag.py` to centralize service modules.
"""
from typing import Optional, List, Dict


class RAGClient:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", cache_folder: str = "./model_cache", chroma_path: str = "./chroma_db"):
        self.model_name = model_name
        self.cache_folder = cache_folder
        self.chroma_path = chroma_path
        self._initialized = False
        self._model = None
        self._client = None
        self._collection = None

    def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            from sentence_transformers import SentenceTransformer
            import chromadb
            from chromadb.config import Settings

            self._model = SentenceTransformer(self.model_name, device="cpu", cache_folder=self.cache_folder)
            self._client = chromadb.PersistentClient(path=self.chroma_path, settings=Settings(anonymized_telemetry=False))
            try:
                self._collection = self._client.get_collection("vibemind_knowledge")
            except Exception:
                self._collection = self._client.create_collection("vibemind_knowledge")

            self._initialized = True
            return True
        except Exception:
            self._initialized = False
            return False

    def add_document(self, text: str, metadata: Optional[Dict] = None) -> bool:
        if not self._initialized:
            return False
        try:
            emb = self._model.encode(text).tolist()
            doc_id = f"doc_{int(__import__('time').time() * 1000)}"
            self._collection.add(embeddings=[emb], documents=[text], metadatas=[metadata or {}], ids=[doc_id])
            return True
        except Exception:
            return False

    def search(self, query: str, n_results: int = 3) -> List[Dict]:
        if not self._initialized:
            return []
        try:
            emb = self._model.encode(query).tolist()
            results = self._collection.query(query_embeddings=[emb], n_results=n_results)
            documents = []
            for i in range(len(results.get("documents", [[]])[0])):
                documents.append({
                    "text": results["documents"][0][i],
                    "metadata": results.get("metadatas", [[]])[0][i],
                    "distance": results.get("distances", [[]])[0][i],
                })
            return documents
        except Exception:
            return []
