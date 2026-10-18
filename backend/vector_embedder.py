import math
import requests
from typing import List

class VectorEmbedder:
    def __init__(self, gemini_api_key: str):
        if not gemini_api_key:
            raise ValueError("Gemini API Key is required for embeddings.")
        self.api_key = gemini_api_key
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={self.api_key}"

    def get_embedding(self, text: str, dimension: int = 768) -> List[float]:
        """
        Generates a 768-dimensional normalized dense vector embedding
        using Google's gemini-embedding-001 model with Matryoshka Representation Learning.
        """
        clean_text = text.strip()
        if not clean_text:
            return [0.0] * dimension

        payload = {
            "model": "models/gemini-embedding-001",
            "content": {"parts": [{"text": clean_text[:2048]}]},
            "outputDimensionality": dimension
        }

        response = requests.post(self.endpoint, json=payload, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Embedding API error ({response.status_code}): {response.text}")

        data = response.json()
        embedding = data.get("embedding", {}).get("values", [])
        return self._normalize_vector(embedding)

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
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Calculates cosine similarity between two normalized vectors."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        return sum(a * b for a, b in zip(v1, v2))
