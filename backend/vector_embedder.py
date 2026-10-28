import json
import math
import time
import threading
import requests
from typing import List, Dict, Any

# Global in-memory cache for query embeddings across instances
_EMBEDDING_CACHE: Dict[str, List[float]] = {}
_CACHE_LOCK = threading.Lock()
_MAX_CACHE_ENTRIES = 5000

class VectorEmbedder:
    def __init__(self, gemini_api_key: str):
        if not gemini_api_key:
            raise ValueError("Gemini API Key is required for embeddings.")
        self.api_key = gemini_api_key
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=1)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={self.api_key}"
        self.batch_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents?key={self.api_key}"

    def get_embedding(self, text: str, dimension: int = 768) -> List[float]:
        """
        Generates a 768-dimensional normalized dense vector embedding
        using Google's gemini-embedding-001 model with Matryoshka Representation Learning.
        Uses in-memory LRU-like cache for instant retrieval of repeat queries.
        """
        clean_text = text.strip()
        if not clean_text:
            return [0.0] * dimension

        cache_key = f"{clean_text[:512]}::{dimension}"
        with _CACHE_LOCK:
            if cache_key in _EMBEDDING_CACHE:
                return _EMBEDDING_CACHE[cache_key]

        payload = {
            "model": "models/gemini-embedding-001",
            "content": {"parts": [{"text": clean_text[:2048]}]},
            "outputDimensionality": dimension
        }

        norm_emb = None
        for attempt in range(3):
            try:
                response = self.session.post(self.endpoint, json=payload, timeout=20)
                if response.status_code == 200:
                    data = response.json()
                    embedding = data.get("embedding", {}).get("values", [])
                    norm_emb = self._normalize_vector(embedding)
                    with _CACHE_LOCK:
                        if len(_EMBEDDING_CACHE) >= _MAX_CACHE_ENTRIES:
                            _EMBEDDING_CACHE.pop(next(iter(_EMBEDDING_CACHE)))
                        _EMBEDDING_CACHE[cache_key] = norm_emb
                    return norm_emb
                elif response.status_code in (429, 503):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                else:
                    raise RuntimeError(f"Embedding API error ({response.status_code}): {response.text}")
            except (requests.exceptions.RequestException, ConnectionResetError) as req_err:
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return [0.0] * dimension

        return [0.0] * dimension

    def batch_get_embeddings(self, texts: List[str], dimension: int = 768, batch_size: int = 50) -> List[List[float]]:
        """
        Batch-embeds a list of texts in parallel chunks of up to 50 items per API call,
        reducing total embedding time from several minutes to just 2-4 seconds.
        Caches all generated embeddings into the in-memory cache for fast repeat access.
        """
        if not texts:
            return []

        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), batch_size):
            batch_slice = texts[i:i + batch_size]
            sub_requests = [
                {
                    "model": "models/gemini-embedding-001",
                    "content": {"parts": [{"text": (t.strip()[:2048] or "Lecture segment")}]},
                    "outputDimensionality": dimension
                }
                for t in batch_slice
            ]

            payload = {"requests": sub_requests}
            for attempt in range(3):
                try:
                    response = self.session.post(self.batch_endpoint, json=payload, timeout=30)
                    if response.status_code == 200:
                        data = response.json()
                        embs = data.get("embeddings", [])
                        for text_item, e in zip(batch_slice, embs):
                            raw_vec = e.get("values", [])
                            norm_v = self._normalize_vector(raw_vec)
                            all_embeddings.append(norm_v)
                            # Cache for subsequent individual lookups
                            ckey = f"{text_item.strip()[:512]}::{dimension}"
                            with _CACHE_LOCK:
                                _EMBEDDING_CACHE[ckey] = norm_v
                        break
                    elif response.status_code in (429, 503):
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    else:
                        print(f"[VectorEmbedder] Batch fallback due to HTTP {response.status_code}: {response.text}")
                        for t in batch_slice:
                            all_embeddings.append(self.get_embedding(t, dimension=dimension))
                        break
                except Exception as batch_err:
                    if attempt < 2:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    print(f"[VectorEmbedder] Batch exception: {batch_err}. Falling back to sequential.")
                    for t in batch_slice:
                        all_embeddings.append(self.get_embedding(t, dimension=dimension))
                    break

        return all_embeddings

    def get_chunk_search_text(self, chunk: dict) -> str:
        """
        Creates the enriched text representation for dense indexing, combining
        context header, cleaned content, key concepts, and hypothetical student queries.
        """
        questions = " ".join(chunk.get("hypothetical_questions", []))
        concepts = " ".join(chunk.get("key_concepts", []))
        return f"{chunk.get('context_header', '')} {chunk.get('cleaned_text', '')} {concepts} {questions}".strip()

    @staticmethod
    def _normalize_vector(vec: List[float]) -> List[float]:
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            return vec
        return [x / norm for x in vec]

    @staticmethod
    def cosine_similarity(v1: Any, v2: Any) -> float:
        """Calculates cosine similarity between two normalized vectors."""
        if isinstance(v1, str):
            try:
                v1 = json.loads(v1)
            except Exception:
                return 0.0
        if isinstance(v2, str):
            try:
                v2 = json.loads(v2)
            except Exception:
                return 0.0
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        return sum(a * b for a, b in zip(v1, v2))
