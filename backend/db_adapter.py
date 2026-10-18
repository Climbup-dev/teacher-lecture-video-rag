import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
from backend.config import Config
from backend.vector_embedder import VectorEmbedder

class DBAdapter:
    def __init__(self, supabase_url: str = "", supabase_key: str = ""):
        self.supabase_url = (supabase_url or Config.SUPABASE_URL).rstrip("/")
        self.supabase_key = supabase_key or Config.SUPABASE_KEY
        self.storage_file = Config.CHUNKS_DIR / "local_store.json"
        self._init_local_store()

    def _init_local_store(self):
        if not self.storage_file.exists():
            initial_data = {
                "courses": {},
                "lessons": {},
                "chunks": [],
                "chat_sessions": {},
                "chat_messages": []
            }
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=2)

    def _read_local_store(self) -> Dict[str, Any]:
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"courses": {}, "lessons": {}, "chunks": [], "chat_sessions": {}, "chat_messages": []}

    def _write_local_store(self, data: Dict[str, Any]):
        with open(self.storage_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def save_lesson(
        self,
        lesson_id: str,
        course_id: str,
        title: str,
        duration_seconds: int,
        video_url: str,
        raw_transcript: str,
        utterances: List[Dict[str, Any]]
    ):
        """Saves lecture metadata and utterances to local store and Supabase."""
        store = self._read_local_store()
        lesson_record = {
            "id": lesson_id,
            "course_id": course_id,
            "title": title,
            "duration_seconds": duration_seconds,
            "video_url": video_url,
            "raw_transcript": raw_transcript,
            "utterances": utterances,
            "processing_status": "ready"
        }
        store["lessons"][lesson_id] = lesson_record
        self._write_local_store(store)

        # Sync to Supabase if credentials are present
        if self.supabase_url and self.supabase_key:
            try:
                headers = {
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates"
                }
                payload = {
                    "id": lesson_id,
                    "course_id": course_id,
                    "module_id": "default-module",
                    "title": title,
                    "duration": f"{duration_seconds // 60}m {duration_seconds % 60}s",
                    "duration_seconds": duration_seconds,
                    "video_url": video_url,
                    "raw_transcript": raw_transcript[:10000],
                    "processing_status": "ready"
                }
                requests.post(f"{self.supabase_url}/rest/v1/course_lessons", headers=headers, json=payload, timeout=10)
            except Exception as e:
                print("Supabase lesson sync warning:", e)

    def save_chunks(self, lesson_id: str, course_id: str, chunks: List[Dict[str, Any]]):
        """Persists enriched chunks with embeddings to transcript_chunks_vector."""
        store = self._read_local_store()

        # Remove previous chunks for this lesson if re-processing
        store["chunks"] = [c for c in store["chunks"] if c.get("lesson_id") != lesson_id]

        for chunk in chunks:
            chunk_record = {
                "id": str(uuid.uuid4()),
                "lesson_id": lesson_id,
                "course_id": course_id,
                "chunk_index": chunk.get("chunk_index", 1),
                "chunk_text": chunk.get("chunk_text", ""),
                "embedding": chunk.get("embedding", []),
                "start_seconds": chunk.get("start_seconds", 0.0),
                "end_seconds": chunk.get("end_seconds", 0.0),
                "timestamp_label": chunk.get("timestamp_label", "00:00 - 00:00"),
                "speaker_label": chunk.get("speaker_label", "teacher"),
                "topic_name": chunk.get("topic_name", ""),
                "cleaned_text": chunk.get("cleaned_text", ""),
                "key_concepts": chunk.get("key_concepts", []),
                "hypothetical_questions": chunk.get("hypothetical_questions", [])
            }
            store["chunks"].append(chunk_record)

        self._write_local_store(store)

        # Sync to Supabase transcript_chunks_vector table if credentials exist
        if self.supabase_url and self.supabase_key:
            try:
                headers = {
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}",
                    "Content-Type": "application/json"
                }
                supabase_rows = []
                for c in chunks:
                    supabase_rows.append({
                        "lesson_id": lesson_id,
                        "course_id": course_id,
                        "chunk_index": c.get("chunk_index", 1),
                        "chunk_text": c.get("chunk_text", ""),
                        "start_seconds": c.get("start_seconds", 0.0),
                        "end_seconds": c.get("end_seconds", 0.0),
                        "timestamp_label": c.get("timestamp_label", ""),
                        "speaker_label": c.get("speaker_label", "teacher")
                    })
                requests.post(f"{self.supabase_url}/rest/v1/transcript_chunks_vector", headers=headers, json=supabase_rows, timeout=15)
            except Exception as e:
                print("Supabase chunk sync warning:", e)

    def search_similar_chunks(
        self,
        query_embedding: List[float],
        lesson_id: Optional[str] = None,
        top_k: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Retrieves the top-k most semantically relevant chunks using cosine similarity
        across indexed embeddings.
        """
        store = self._read_local_store()
        all_chunks = store.get("chunks", [])

        if lesson_id:
            all_chunks = [c for c in all_chunks if c.get("lesson_id") == lesson_id]

        if not all_chunks:
            return []

        scored_chunks = []
        for chunk in all_chunks:
            emb = chunk.get("embedding", [])
            score = VectorEmbedder.cosine_similarity(query_embedding, emb)
            scored_chunks.append({
                **chunk,
                "similarity_score": round(score, 4)
            })

        # Sort descending by similarity
        scored_chunks.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored_chunks[:top_k]

    def get_lesson(self, lesson_id: str) -> Optional[Dict[str, Any]]:
        store = self._read_local_store()
        return store.get("lessons", {}).get(lesson_id)

    def list_lessons(self) -> List[Dict[str, Any]]:
        store = self._read_local_store()
        lessons = list(store.get("lessons", {}).values())
        return lessons

    def get_lesson_chunks(self, lesson_id: str) -> List[Dict[str, Any]]:
        store = self._read_local_store()
        return [c for c in store.get("chunks", []) if c.get("lesson_id") == lesson_id]

    def record_chat_message(
        self,
        session_id: str,
        sender: str,
        message: str,
        timestamp_ref: Optional[Dict[str, Any]] = None,
        retrieved_chunk_ids: Optional[List[str]] = None
    ):
        """Records student and AI messages into ai_chat_messages schema."""
        store = self._read_local_store()
        msg_record = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "sender": sender,
            "message": message,
            "timestamp_ref": timestamp_ref,
            "retrieved_chunk_ids": retrieved_chunk_ids or []
        }
        store["chat_messages"].append(msg_record)
        self._write_local_store(store)
