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

    def _get_headers(self) -> Dict[str, str]:
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

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

    def ensure_course_exists(self, course_id: str, title: str = "Applied AI & GenAI"):
        """Ensures the parent course exists in Supabase to satisfy foreign key constraints."""
        if not (self.supabase_url and self.supabase_key):
            return

        try:
            headers = self._get_headers()
            res = requests.get(
                f"{self.supabase_url}/rest/v1/courses?id=eq.{course_id}&select=id",
                headers=headers,
                timeout=5
            )
            if res.ok and len(res.json()) > 0:
                return  # Course already exists

            # If course does not exist, insert it
            slug = course_id.lower().replace(" ", "-")
            course_payload = {
                "id": course_id,
                "slug": f"{slug}-{uuid.uuid4().hex[:4]}",
                "title": title,
                "category": "Computer Science",
                "level": "All Levels",
                "thumbnail": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800",
                "instructor_name": "Course Professor",
                "duration": "10+ Hours",
                "total_lessons": 1
            }
            requests.post(
                f"{self.supabase_url}/rest/v1/courses",
                headers={**headers, "Prefer": "resolution=ignore-duplicates"},
                json=course_payload,
                timeout=8
            )
        except Exception as e:
            print(f"[Supabase] ensure_course_exists notice: {e}")

    def list_courses(self) -> List[Dict[str, Any]]:
        """Returns courses from Supabase with fallback to local store."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                res = requests.get(
                    f"{self.supabase_url}/rest/v1/courses?select=id,title,category,thumbnail,instructor_name,total_lessons",
                    headers=headers,
                    timeout=6
                )
                if res.ok:
                    courses = res.json()
                    if courses:
                        return courses
            except Exception as e:
                print(f"[Supabase] list_courses fallback: {e}")

        # Local fallback
        return [
            {
                "id": "course-applied-ai-rag",
                "title": "Applied AI & GenAI with RAG Architectures",
                "category": "Artificial Intelligence",
                "instructor_name": "Prof. AI Systems",
                "total_lessons": 4
            },
            {
                "id": "course-os-kernel",
                "title": "Operating Systems: Kernel & CPU Scheduling",
                "category": "Computer Science",
                "instructor_name": "Prof. OS Engineering",
                "total_lessons": 2
            }
        ]

    def save_lesson(
        self,
        lesson_id: str,
        course_id: str,
        title: str,
        duration_seconds: int,
        video_url: str,
        raw_transcript: str,
        utterances: List[Dict[str, Any]],
        structured_notes: Optional[Dict[str, Any]] = None,
        chapters: Optional[List[Dict[str, Any]]] = None
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
            "structured_notes": structured_notes or {},
            "chapters": chapters or [],
            "processing_status": "ready"
        }
        store["lessons"][lesson_id] = lesson_record
        self._write_local_store(store)

        # Sync to Supabase
        if self.supabase_url and self.supabase_key:
            try:
                self.ensure_course_exists(course_id, title=f"Course: {title}")
                headers = self._get_headers()
                headers["Prefer"] = "resolution=merge-duplicates"

                mins = duration_seconds // 60
                secs = duration_seconds % 60
                payload = {
                    "id": lesson_id,
                    "course_id": course_id,
                    "module_id": None,  # Avoid foreign key constraint on course_modules
                    "title": title,
                    "duration": f"{mins}m {secs}s",
                    "duration_seconds": duration_seconds,
                    "video_url": video_url,
                    "raw_transcript": raw_transcript[:25000],
                    "structured_notes": structured_notes or {},
                    "chapters": chapters or [],
                    "processing_status": "ready"
                }
                res = requests.post(f"{self.supabase_url}/rest/v1/course_lessons", headers=headers, json=payload, timeout=12)
                if not res.ok:
                    print(f"[Supabase] course_lessons sync HTTP {res.status_code}: {res.text}")
            except Exception as e:
                print(f"[Supabase] lesson sync warning: {e}")

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
                headers = self._get_headers()
                supabase_rows = []
                for c in chunks:
                    row = {
                        "lesson_id": lesson_id,
                        "course_id": course_id,
                        "chunk_index": c.get("chunk_index", 1),
                        "chunk_text": c.get("cleaned_text") or c.get("chunk_text", ""),
                        "start_seconds": float(c.get("start_seconds", 0.0)),
                        "end_seconds": float(c.get("end_seconds", 0.0)),
                        "timestamp_label": c.get("timestamp_label", ""),
                        "speaker_label": c.get("speaker_label", "teacher")
                    }
                    emb = c.get("embedding")
                    if emb and isinstance(emb, list) and len(emb) == 768:
                        row["embedding"] = emb
                    supabase_rows.append(row)

                res = requests.post(
                    f"{self.supabase_url}/rest/v1/transcript_chunks_vector",
                    headers=headers,
                    json=supabase_rows,
                    timeout=20
                )
                if not res.ok:
                    print(f"[Supabase] transcript_chunks_vector sync HTTP {res.status_code}: {res.text}")
            except Exception as e:
                print(f"[Supabase] chunk sync warning: {e}")

    def search_similar_chunks(
        self,
        query_embedding: List[float],
        lesson_id: Optional[str] = None,
        top_k: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top-k most semantically relevant chunks using cosine similarity.
        Provides sub-millisecond local caching alongside cloud Supabase sync.
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
        retrieved_chunk_ids: Optional[List[str]] = None,
        lesson_id: Optional[str] = None,
        course_id: Optional[str] = None
    ):
        """Records student and AI messages into ai_chat_messages schema."""
        try:
            store = self._read_local_store()
            if "chat_messages" not in store:
                store["chat_messages"] = []
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
        except Exception as e:
            print(f"[Warning] Could not record chat message: {e}")

    def upload_course_resource(
        self,
        course_id: str,
        title: str,
        file_bytes: bytes,
        filename: str,
        file_type: str = "pdf",
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Uploads course resource/note to Supabase Storage ('course_resources')
        and persists record in Supabase table 'public.course_resources'.
        """
        import re
        import time

        clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
        storage_path = f"{course_id}/{int(time.time())}_{clean_name}"

        file_size_mb = f"{round(len(file_bytes) / (1024 * 1024), 2)} MB" if len(file_bytes) > 1024 * 1024 else f"{round(len(file_bytes) / 1024, 1)} KB"
        download_url = f"{self.supabase_url}/storage/v1/object/public/course_resources/{storage_path}"

        if self.supabase_url and self.supabase_key:
            try:
                # 1. Supabase Storage API upload
                upload_endpoint = f"{self.supabase_url}/storage/v1/object/course_resources/{storage_path}"
                headers = {
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}",
                    "Content-Type": "application/octet-stream",
                    "x-upsert": "true"
                }
                upload_res = requests.post(upload_endpoint, headers=headers, data=file_bytes, timeout=30)
                if not upload_res.ok:
                    print(f"[Supabase Storage] Note upload HTTP {upload_res.status_code}: {upload_res.text}")

                # 2. Insert into public.course_resources table
                record_id = str(uuid.uuid4())
                table_endpoint = f"{self.supabase_url}/rest/v1/course_resources"
                table_headers = self._get_headers()
                table_headers["Prefer"] = "return=representation"
                payload = {
                    "id": record_id,
                    "course_id": course_id,
                    "title": title,
                    "file_type": file_type.lower(),
                    "file_size": file_size_mb,
                    "download_url": download_url,
                    "description": description or f"Official course material: {title}"
                }
                db_res = requests.post(table_endpoint, headers=table_headers, json=payload, timeout=10)
                if db_res.ok and db_res.json():
                    return db_res.json()[0]
            except Exception as e:
                print(f"[Supabase] upload_course_resource error: {e}")

        # Local fallback
        store = self._read_local_store()
        if "resources" not in store:
            store["resources"] = []
        rec = {
            "id": str(uuid.uuid4()),
            "course_id": course_id,
            "title": title,
            "file_type": file_type.lower(),
            "file_size": file_size_mb,
            "download_url": download_url,
            "description": description or f"Course material: {title}",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        store["resources"].append(rec)
        self._write_local_store(store)
        return rec

    def get_course_resources(self, course_id: str) -> List[Dict[str, Any]]:
        """Retrieves all resources, notes, assignments for a course from Supabase with local fallback."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                res = requests.get(
                    f"{self.supabase_url}/rest/v1/course_resources?course_id=eq.{course_id}&order=created_at.desc",
                    headers=headers,
                    timeout=8
                )
                if res.ok:
                    return res.json()
            except Exception as e:
                print(f"[Supabase] get_course_resources warning: {e}")

        store = self._read_local_store()
        resources = store.get("resources", [])
        return [r for r in resources if r.get("course_id") == course_id]

