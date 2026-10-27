import json
import uuid
import threading
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from backend.config import Config
from backend.vector_embedder import VectorEmbedder

class DBAdapter:
    def __init__(self, supabase_url: str = "", supabase_key: str = ""):
        self.supabase_url = (supabase_url or Config.SUPABASE_URL).rstrip("/")
        self.supabase_key = supabase_key or Config.SUPABASE_KEY
        self.storage_file = Config.CHUNKS_DIR / "local_store.json"
        self._store_lock = threading.Lock()
        
        # Configure pooled HTTP session for fast, keep-alive Supabase REST queries
        self.session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.3, status_forcelist=[502, 503, 504])
        adapter = HTTPAdapter(pool_connections=15, pool_maxsize=30, max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self._init_local_store()

    def _get_headers(self) -> Dict[str, str]:
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

    def _init_local_store(self):
        with self._store_lock:
            seed_file = Path(__file__).resolve().parent / "seed_catalog.json"
            if not self.storage_file.exists():
                initial_data = None
                if seed_file.exists():
                    try:
                        with open(seed_file, "r", encoding="utf-8") as sf:
                            initial_data = json.load(sf)
                    except Exception:
                        initial_data = None

                if not initial_data:
                    initial_data = {
                        "courses": {},
                        "lessons": {},
                        "chunks": [],
                        "jobs": {},
                        "chat_sessions": {},
                        "chat_messages": [],
                        "live_sessions": {}
                    }
                try:
                    self.storage_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.storage_file, "w", encoding="utf-8") as f:
                        json.dump(initial_data, f, indent=2)
                except Exception as e:
                    print(f"[DBAdapter] Notice creating local storage: {e}")

    def _read_local_store(self) -> Dict[str, Any]:
        with self._store_lock:
            seed_file = Path(__file__).resolve().parent / "seed_catalog.json"
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not data.get("lessons") and seed_file.exists():
                        try:
                            with open(seed_file, "r", encoding="utf-8") as sf:
                                seed = json.load(sf)
                                data["lessons"] = seed.get("lessons", {})
                                data["courses"] = seed.get("courses", {})
                        except Exception:
                            pass
                    if "jobs" not in data:
                        data["jobs"] = {}
                    return data
            except Exception:
                if seed_file.exists():
                    try:
                        with open(seed_file, "r", encoding="utf-8") as sf:
                            return json.load(sf)
                    except Exception:
                        pass
                return {"courses": {}, "lessons": {}, "chunks": [], "jobs": {}, "chat_sessions": {}, "chat_messages": []}

    def _write_local_store(self, data: Dict[str, Any]):
        with self._store_lock:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def ensure_course_exists(self, course_id: str, title: str = "Applied AI & GenAI"):
        """Ensures the parent course exists in Supabase to satisfy foreign key constraints."""
        if not (self.supabase_url and self.supabase_key):
            return

        try:
            headers = self._get_headers()
            res = self.session.get(
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
            self.session.post(
                f"{self.supabase_url}/rest/v1/courses",
                headers={**headers, "Prefer": "resolution=ignore-duplicates"},
                json=course_payload,
                timeout=8
            )
        except Exception as e:
            print(f"[Supabase] ensure_course_exists notice: {e}")

    def ensure_module_exists(self, course_id: str) -> str:
        """Ensures at least one module exists for course_id and returns its module_id."""
        module_id = f"mod-{course_id[:20]}-1"
        if not (self.supabase_url and self.supabase_key):
            return module_id
        try:
            headers = self._get_headers()
            res = self.session.get(
                f"{self.supabase_url}/rest/v1/course_modules?course_id=eq.{course_id}&select=id&limit=1",
                headers=headers,
                timeout=5
            )
            if res.ok and len(res.json()) > 0:
                return res.json()[0]["id"]
            
            payload = {
                "id": module_id,
                "course_id": course_id,
                "title": "Module 1: Core Lectures",
                "display_order": 1
            }
            self.session.post(
                f"{self.supabase_url}/rest/v1/course_modules",
                headers={**headers, "Prefer": "resolution=ignore-duplicates"},
                json=payload,
                timeout=8
            )
            return module_id
        except Exception as e:
            print(f"[Supabase] ensure_module_exists notice: {e}")
            return module_id

    def list_courses(self) -> List[Dict[str, Any]]:
        """Returns courses strictly from Supabase."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                res = self.session.get(
                    f"{self.supabase_url}/rest/v1/courses?select=*&order=created_at.desc",
                    headers=headers,
                    timeout=8
                )
                if res.ok:
                    courses = res.json()
                    if isinstance(courses, list):
                        return courses
            except Exception as e:
                print(f"[Supabase] list_courses error: {e}")

        store = self._read_local_store()
        return list(store.get("courses", {}).values())

    def create_course(
        self,
        title: str,
        category: str = "Computer Science",
        level: str = "All Levels",
        description: str = "",
        instructor_name: str = "Course Instructor",
        thumbnail: str = "",
        tagline: str = ""
    ) -> Dict[str, Any]:
        """Creates a new course in Supabase and local store."""
        import re
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower()).strip('-')
        course_id = f"course-{slug[:25]}-{uuid.uuid4().hex[:4]}"
        
        course_payload = {
            "id": course_id,
            "slug": slug,
            "title": title,
            "tagline": tagline or f"Comprehensive mastery of {title}",
            "description": description or f"Learn {title} with curated video lectures and AI doubt assistance.",
            "category": category,
            "level": level,
            "thumbnail": thumbnail or "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800",
            "instructor_name": instructor_name,
            "instructor_title": "Lead Instructor",
            "duration": "0 Hours",
            "total_lessons": 0
        }

        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                headers["Prefer"] = "return=representation"
                res = self.session.post(
                    f"{self.supabase_url}/rest/v1/courses",
                    headers=headers,
                    json=course_payload,
                    timeout=10
                )
                if res.ok and res.json():
                    created = res.json()[0]
                    store = self._read_local_store()
                    store["courses"][course_id] = created
                    self._write_local_store(store)
                    return created
            except Exception as e:
                print(f"[Supabase] create_course warning: {e}")

        store = self._read_local_store()
        store["courses"][course_id] = course_payload
        self._write_local_store(store)
        return course_payload

    def delete_course(self, course_id: str) -> bool:
        """Deletes course and associated lessons, vector chunks, and resources."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                self.session.delete(f"{self.supabase_url}/rest/v1/transcript_chunks_vector?course_id=eq.{course_id}", headers=headers, timeout=8)
                self.session.delete(f"{self.supabase_url}/rest/v1/course_resources?course_id=eq.{course_id}", headers=headers, timeout=8)
                self.session.delete(f"{self.supabase_url}/rest/v1/course_lessons?course_id=eq.{course_id}", headers=headers, timeout=8)
                self.session.delete(f"{self.supabase_url}/rest/v1/courses?id=eq.{course_id}", headers=headers, timeout=8)
            except Exception as e:
                print(f"[Supabase] delete_course warning: {e}")

        store = self._read_local_store()
        if course_id in store.get("courses", {}):
            del store["courses"][course_id]
        
        lessons_to_del = [lid for lid, l in store.get("lessons", {}).items() if l.get("course_id") == course_id]
        for lid in lessons_to_del:
            del store["lessons"][lid]
        
        store["chunks"] = [c for c in store.get("chunks", []) if c.get("course_id") != course_id]
        if "resources" in store:
            store["resources"] = [r for r in store["resources"] if r.get("course_id") != course_id]

        self._write_local_store(store)
        return True


    def save_lesson(
        self,
        lesson_id: str,
        course_id: str,
        title: str,
        duration_seconds: int,
        video_url: str,
        raw_transcript: str = "",
        utterances: Optional[List[Dict[str, Any]]] = None,
        structured_notes: Optional[Dict[str, Any]] = None,
        chapters: Optional[List[Dict[str, Any]]] = None,
        processing_status: str = "ready"
    ):
        """Saves lecture metadata and utterances to local store and Supabase."""
        store = self._read_local_store()
        existing_lesson = store.get("lessons", {}).get(lesson_id, {})

        lesson_record = {
            "id": lesson_id,
            "course_id": course_id,
            "title": title,
            "duration_seconds": duration_seconds or existing_lesson.get("duration_seconds", 0),
            "video_url": video_url or existing_lesson.get("video_url", ""),
            "raw_transcript": raw_transcript if raw_transcript is not None else existing_lesson.get("raw_transcript", ""),
            "utterances": utterances if utterances is not None else existing_lesson.get("utterances", []),
            "structured_notes": structured_notes or existing_lesson.get("structured_notes", {}),
            "chapters": chapters or existing_lesson.get("chapters", []),
            "processing_status": processing_status
        }
        store["lessons"][lesson_id] = lesson_record
        self._write_local_store(store)

        # Sync to Supabase
        if self.supabase_url and self.supabase_key:
            try:
                self.ensure_course_exists(course_id, title=f"Course: {title}")
                module_id = self.ensure_module_exists(course_id)
                headers = self._get_headers()
                headers["Prefer"] = "resolution=merge-duplicates"

                mins = duration_seconds // 60
                secs = duration_seconds % 60
                dur_label = f"{mins}m {secs}s" if duration_seconds > 0 else "Processing..."
                payload = {
                    "id": lesson_id,
                    "course_id": course_id,
                    "module_id": module_id,
                    "title": title,
                    "duration": dur_label,
                    "duration_seconds": duration_seconds,
                    "video_url": video_url,
                    "raw_transcript": (raw_transcript or "")[:25000],
                    "structured_notes": structured_notes or {},
                    "chapters": chapters or [],
                    "processing_status": processing_status,
                    "display_order": 1,
                    "is_free_preview": True
                }
                res = self.session.post(f"{self.supabase_url}/rest/v1/course_lessons", headers=headers, json=payload, timeout=12)
                if not res.ok:
                    print(f"[Supabase] course_lessons sync HTTP {res.status_code}: {res.text}")
            except Exception as e:
                print(f"[Supabase] lesson sync warning: {e}")

    def log_mentor_notification(self, notification_data: Dict[str, Any]):
        """Logs dispatched mentor notification to local store for audit and history."""
        import datetime
        store = self._read_local_store()
        if "mentor_notifications" not in store:
            store["mentor_notifications"] = []
        entry = {
            **notification_data,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        store["mentor_notifications"].append(entry)
        self._write_local_store(store)

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
                # 1. Clean previous chunks for this lesson in Supabase to prevent duplicates
                try:
                    self.session.delete(
                        f"{self.supabase_url}/rest/v1/transcript_chunks_vector?lesson_id=eq.{lesson_id}",
                        headers=headers,
                        timeout=8
                    )
                except Exception as del_err:
                    print(f"[Supabase] previous chunks delete notice: {del_err}")

                supabase_rows = []
                for c in chunks:
                    topic = c.get("topic_name") or ""
                    concepts = ", ".join(c.get("key_concepts") or [])
                    raw_txt = c.get("cleaned_text") or c.get("chunk_text") or ""
                    formatted_txt = f"[{topic}]\nConcepts: {concepts}\n{raw_txt}" if (topic and not raw_txt.startswith("[")) else raw_txt

                    row = {
                        "lesson_id": lesson_id,
                        "course_id": course_id,
                        "chunk_index": c.get("chunk_index", 1),
                        "chunk_text": formatted_txt,
                        "start_seconds": float(c.get("start_seconds", 0.0)),
                        "end_seconds": float(c.get("end_seconds", 0.0)),
                        "timestamp_label": c.get("timestamp_label", ""),
                        "speaker_label": c.get("speaker_label", "teacher")
                    }
                    emb = c.get("embedding")
                    if emb and isinstance(emb, list) and len(emb) == 768:
                        row["embedding"] = emb
                    else:
                        row["embedding"] = [0.0] * 768
                    supabase_rows.append(row)

                res = self.session.post(
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
        course_id: Optional[str] = None,
        top_k: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top-k most semantically relevant chunks.
        Strategy 1: Fast in-database pgvector RPC search (zero vector transfer overhead).
        Strategy 2: Resilient local fallback with Python cosine similarity.
        """
        # 1. Primary: Indexed pgvector search via Supabase RPC
        if self.supabase_url and self.supabase_key and query_embedding:
            try:
                headers = self._get_headers()
                rpc_payload = {
                    "query_embedding": query_embedding,
                    "match_threshold": 0.0,
                    "match_count": top_k,
                    "filter_course_id": course_id or "",
                    "filter_lesson_id": lesson_id or ""
                }
                rpc_res = self.session.post(
                    f"{self.supabase_url}/rest/v1/rpc/match_transcript_chunks",
                    headers=headers,
                    json=rpc_payload,
                    timeout=8
                )
                if rpc_res.ok:
                    matches = rpc_res.json()
                    if isinstance(matches, list) and len(matches) > 0:
                        scored = []
                        for m in matches:
                            scored.append({
                                **m,
                                "similarity_score": round(float(m.get("similarity", 0.0)), 4)
                            })
                        return scored
            except Exception as rpc_e:
                print(f"[Supabase RPC] Vector search notice: {rpc_e}")

        # 2. Fallback: Local store / REST download
        chunks_to_search = []
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                url = f"{self.supabase_url}/rest/v1/transcript_chunks_vector?select=*"
                if lesson_id:
                    url += f"&lesson_id=eq.{lesson_id}"
                res = self.session.get(url, headers=headers, timeout=8)
                if res.ok:
                    chunks_to_search = res.json()
            except Exception as e:
                print(f"[Supabase] search_similar_chunks fetch error: {e}")

        if not chunks_to_search:
            store = self._read_local_store()
            chunks_to_search = store.get("chunks", [])
            if lesson_id:
                chunks_to_search = [c for c in chunks_to_search if c.get("lesson_id") == lesson_id]

        if not chunks_to_search:
            return []

        # Deduplicate candidates by chunk_index
        seen_indices = set()
        unique_chunks = []
        for c in chunks_to_search:
            idx = c.get("chunk_index", 0)
            if idx not in seen_indices:
                seen_indices.add(idx)
                unique_chunks.append(c)

        scored_chunks = []
        for chunk in unique_chunks:
            emb = chunk.get("embedding", [])
            if emb:
                score = VectorEmbedder.cosine_similarity(query_embedding, emb)
                scored_chunks.append({
                    **chunk,
                    "similarity_score": round(score, 4)
                })

        scored_chunks.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored_chunks[:top_k]

    def get_all_chunks_for_lesson(self, lesson_id: str) -> List[Dict[str, Any]]:
        """Retrieves all indexed chunks for a lesson, deduplicated and ordered chronologically by start_seconds."""
        raw_chunks = []
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                url = f"{self.supabase_url}/rest/v1/transcript_chunks_vector?lesson_id=eq.{lesson_id}&select=*&order=start_seconds.asc"
                res = self.session.get(url, headers=headers, timeout=8)
                if res.ok:
                    raw_chunks = res.json()
            except Exception as e:
                print(f"[Supabase] get_all_chunks_for_lesson error: {e}")

        store = self._read_local_store()
        local_chunks = [c for c in store.get("chunks", []) if c.get("lesson_id") == lesson_id]

        # Build local metadata index: chunk_index -> local metadata
        local_meta_map = {c.get("chunk_index"): c for c in local_chunks if c.get("chunk_index")}

        chunks_source = raw_chunks if raw_chunks else local_chunks

        # Deduplicate by chunk_index while enriching with local metadata
        seen_indices = set()
        deduped = []
        for c in chunks_source:
            idx = c.get("chunk_index", 0)
            if idx not in seen_indices:
                seen_indices.add(idx)
                # Merge local enrichments if available
                enriched = dict(c)
                if idx in local_meta_map:
                    lm = local_meta_map[idx]
                    if not enriched.get("topic_name") and lm.get("topic_name"):
                        enriched["topic_name"] = lm.get("topic_name")
                    if not enriched.get("key_concepts") and lm.get("key_concepts"):
                        enriched["key_concepts"] = lm.get("key_concepts")
                    if not enriched.get("hypothetical_questions") and lm.get("hypothetical_questions"):
                        enriched["hypothetical_questions"] = lm.get("hypothetical_questions")
                deduped.append(enriched)

        deduped.sort(key=lambda x: x.get("start_seconds", 0.0))
        return deduped

    def get_lesson(self, lesson_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single lesson from Supabase."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                res = self.session.get(
                    f"{self.supabase_url}/rest/v1/course_lessons?id=eq.{lesson_id}&select=*",
                    headers=headers,
                    timeout=6
                )
                if res.ok and len(res.json()) > 0:
                    return res.json()[0]
            except Exception as e:
                print(f"[Supabase] get_lesson error: {e}")

        store = self._read_local_store()
        return store.get("lessons", {}).get(lesson_id)

    def list_lessons(self) -> List[Dict[str, Any]]:
        """Retrieves all lessons from Supabase course_lessons."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                res = self.session.get(
                    f"{self.supabase_url}/rest/v1/course_lessons?select=*&order=created_at.asc",
                    headers=headers,
                    timeout=8
                )
                if res.ok:
                    lessons = res.json()
                    if isinstance(lessons, list):
                        return lessons
            except Exception as e:
                print(f"[Supabase] list_lessons error: {e}")

        store = self._read_local_store()
        return list(store.get("lessons", {}).values())

    def get_lesson_chunks(self, lesson_id: str) -> List[Dict[str, Any]]:
        """Retrieves vector transcript chunks directly from Supabase transcript_chunks_vector."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                res = self.session.get(
                    f"{self.supabase_url}/rest/v1/transcript_chunks_vector?lesson_id=eq.{lesson_id}&order=chunk_index.asc&select=*",
                    headers=headers,
                    timeout=8
                )
                if res.ok:
                    chunks = res.json()
                    if isinstance(chunks, list):
                        return chunks
            except Exception as e:
                print(f"[Supabase] get_lesson_chunks error: {e}")

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

    def get_chat_history(self, session_id: str, limit: int = 4) -> List[Dict[str, Any]]:
        """Returns recent chat messages for a session to provide grounded context."""
        try:
            store = self._read_local_store()
            all_msgs = [m for m in store.get("chat_messages", []) if m.get("session_id") == session_id]
            return all_msgs[-limit:] if limit > 0 else all_msgs
        except Exception:
            return []

    def clear_chat_session(self, session_id: str) -> bool:
        """Clears chat history for a session when user closes or resets AI tutorial."""
        try:
            store = self._read_local_store()
            if "chat_messages" in store:
                store["chat_messages"] = [m for m in store["chat_messages"] if m.get("session_id") != session_id]
                self._write_local_store(store)
                return True
        except Exception as e:
            print(f"[Warning] Could not clear chat session: {e}")
        return False

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
                upload_res = self.session.post(upload_endpoint, headers=headers, data=file_bytes, timeout=30)
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
                db_res = self.session.post(table_endpoint, headers=table_headers, json=payload, timeout=10)
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

    def upload_assignment_asset(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = "image/png",
        assignment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploads assignment diagrams, images, and schema assets directly to Supabase Storage ('course_resources').
        Returns the permanent public URL and asset metadata.
        """
        import re
        import time

        clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
        subfolder = f"assignments/{assignment_id}" if assignment_id else "assignments"
        storage_path = f"{subfolder}/{int(time.time())}_{clean_name}"

        download_url = f"{self.supabase_url}/storage/v1/object/public/course_resources/{storage_path}"

        if self.supabase_url and self.supabase_key:
            try:
                upload_endpoint = f"{self.supabase_url}/storage/v1/object/course_resources/{storage_path}"
                headers = {
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}",
                    "Content-Type": content_type or "application/octet-stream",
                    "x-upsert": "true"
                }
                upload_res = self.session.post(upload_endpoint, headers=headers, data=file_bytes, timeout=30)
                if upload_res.ok:
                    return {
                        "status": "success",
                        "url": download_url,
                        "storage_path": storage_path,
                        "filename": filename,
                        "size": len(file_bytes),
                        "content_type": content_type,
                        "storage": "supabase"
                    }
                else:
                    print(f"[Supabase Storage] Assignment asset upload HTTP {upload_res.status_code}: {upload_res.text}")
            except Exception as e:
                print(f"[Supabase Storage] upload_assignment_asset exception: {e}")

        # Local fallback if Supabase Storage is not reachable
        from backend.config import Config
        fallback_dir = Config.CHUNKS_DIR / "assignment_assets"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        local_filename = f"{int(time.time())}_{clean_name}"
        local_path = fallback_dir / local_filename
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        local_url = f"/api/assignments/assets/{local_filename}"
        return {
            "status": "success",
            "url": local_url,
            "storage_path": str(local_path),
            "filename": filename,
            "size": len(file_bytes),
            "content_type": content_type,
            "storage": "local"
        }

    def get_course_resources(self, course_id: str) -> List[Dict[str, Any]]:
        """Retrieves all resources, notes, assignments for a course directly from Supabase."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                res = self.session.get(
                    f"{self.supabase_url}/rest/v1/course_resources?course_id=eq.{course_id}&order=created_at.desc",
                    headers=headers,
                    timeout=8
                )
                if res.ok:
                    resources = res.json()
                    if isinstance(resources, list):
                        return resources
            except Exception as e:
                print(f"[Supabase] get_course_resources warning: {e}")

        store = self._read_local_store()
        resources = store.get("resources", [])
        return [r for r in resources if r.get("course_id") == course_id]

    def get_students(self, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves students from Supabase (profiles + course_enrollments) with local store caching."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                enr_url = f"{self.supabase_url}/rest/v1/course_enrollments?select=*"
                if course_id:
                    enr_url += f"&course_id=eq.{course_id}"
                enr_res = self.session.get(enr_url, headers=headers, timeout=6)

                if enr_res.ok:
                    enrollments = enr_res.json()
                    prof_res = self.session.get(f"{self.supabase_url}/rest/v1/profiles?select=id,full_name,email,avatar_url", headers=headers, timeout=6)
                    profiles_map = {p["id"]: p for p in prof_res.json()} if prof_res.ok else {}

                    crs_res = self.session.get(f"{self.supabase_url}/rest/v1/courses?select=id,title", headers=headers, timeout=6)
                    courses_map = {c["id"]: c.get("title") for c in crs_res.json()} if crs_res.ok else {}

                    if not course_id:
                        # Group by unique student according to Supabase profile (user_id / email)
                        students_map = {}
                        for enr in enrollments:
                            uid = enr.get("user_id")
                            p = profiles_map.get(uid, {})
                            cid = enr.get("course_id")
                            c_title = courses_map.get(cid) or "University Course"
                            enr_date = str(enr.get("enrolled_at", ""))[:10] or "2026-10-18"
                            prog_val = int(enr.get("progress_percentage") or 0)
                            enr_id = str(enr.get("id"))

                            email = p.get("email") or "student@university.edu"
                            key = str(uid) if uid else email.lower().strip()

                            if key not in students_map:
                                students_map[key] = {
                                    "id": str(uid) if uid else enr_id,
                                    "user_id": uid,
                                    "name": p.get("full_name") or (email.split("@")[0].title()) or "Enrolled Student",
                                    "email": email,
                                    "avatar_url": p.get("avatar_url"),
                                    "course_id": cid,
                                    "course_title": c_title,
                                    "courses_count": 0,
                                    "enrolled_courses": [],
                                    "courses": [],
                                    "enrollment_ids": [],
                                    "enrolled_date": enr_date,
                                    "total_progress": 0,
                                    "doubts_asked": 0,
                                    "status": "Active"
                                }

                            std = students_map[key]
                            std["courses_count"] += 1
                            std["enrollment_ids"].append(enr_id)
                            std["enrolled_courses"].append(c_title)
                            std["courses"].append({
                                "id": cid,
                                "title": c_title,
                                "enrollment_id": enr_id,
                                "enrolled_date": enr_date,
                                "progress": prog_val
                            })
                            std["total_progress"] += prog_val
                            if enr_date < std["enrolled_date"]:
                                std["enrolled_date"] = enr_date

                        students = []
                        for s in students_map.values():
                            count = s["courses_count"]
                            s["progress"] = f"{round(s['total_progress'] / max(1, count))}%"
                            del s["total_progress"]
                            students.append(s)
                    else:
                        students = []
                        for enr in enrollments:
                            p = profiles_map.get(enr.get("user_id"), {})
                            cid = enr.get("course_id")
                            c_title = courses_map.get(cid) or "University Course"
                            enr_id = str(enr.get("id"))
                            students.append({
                                "id": enr_id,
                                "user_id": enr.get("user_id"),
                                "name": p.get("full_name") or (p.get("email", "").split("@")[0].title()) or "Enrolled Student",
                                "email": p.get("email") or "student@university.edu",
                                "avatar_url": p.get("avatar_url"),
                                "course_id": cid,
                                "course_title": c_title,
                                "courses_count": 1,
                                "enrolled_courses": [c_title],
                                "courses": [{"id": cid, "title": c_title, "enrollment_id": enr_id}],
                                "enrollment_ids": [enr_id],
                                "enrolled_date": str(enr.get("enrolled_at", ""))[:10] or "2026-10-18",
                                "progress": f"{enr.get('progress_percentage', 0)}%",
                                "doubts_asked": 0,
                                "status": "Completed" if enr.get("is_completed") else "Active"
                            })

                    store = self._read_local_store()
                    store["students"] = students
                    self._write_local_store(store)
                    return students
            except Exception as e:
                print(f"[Supabase] get_students live fetch error: {e}")

        store = self._read_local_store()
        students = store.get("students", [])
        if course_id:
            students = [s for s in students if s.get("course_id") == course_id or any(c.get("id") == course_id for c in s.get("courses", []))]
        return students

    def add_student(self, name: str, email: str, course_id: str) -> Dict[str, Any]:
        """Enrolls a new student into a course in Supabase and local cache."""
        import time
        new_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        courses = self.list_courses()
        course_name = "University Course"
        for c in courses:
            if c.get("id") == course_id:
                course_name = c.get("title", course_name)
                break

        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                # Check if profile exists for this email
                prof_check = self.session.get(f"{self.supabase_url}/rest/v1/profiles?email=eq.{email}&select=id", headers=headers, timeout=5)
                if prof_check.ok and len(prof_check.json()) > 0:
                    user_id = prof_check.json()[0]["id"]
                else:
                    # Create user via Supabase auth admin or profile
                    prof_payload = {
                        "id": user_id,
                        "email": email,
                        "full_name": name,
                        "role": "student"
                    }
                    self.session.post(f"{self.supabase_url}/rest/v1/profiles", headers={**headers, "Prefer": "resolution=ignore-duplicates"}, json=prof_payload, timeout=5)

                enr_payload = {
                    "id": new_id,
                    "user_id": user_id,
                    "course_id": course_id,
                    "progress_percentage": 0,
                    "is_completed": False
                }
                res = self.session.post(f"{self.supabase_url}/rest/v1/course_enrollments", headers=headers, json=enr_payload, timeout=8)
                if not res.ok:
                    print(f"[Supabase] course_enrollments insert notice: {res.text}")
            except Exception as e:
                print(f"[Supabase] add_student warning: {e}")

        new_std = {
            "id": new_id,
            "user_id": user_id,
            "name": name,
            "email": email,
            "course_id": course_id,
            "course_title": course_name,
            "enrolled_date": time.strftime("%Y-%m-%d"),
            "progress": "0%",
            "doubts_asked": 0,
            "status": "Active"
        }

        store = self._read_local_store()
        if "students" not in store:
            store["students"] = []
        store["students"].append(new_std)
        self._write_local_store(store)
        return new_std

    def delete_student(self, student_id: str) -> bool:
        """Removes a student enrollment or all student enrollments from Supabase and local cache."""
        deleted = False
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                # Delete by enrollment id or user_id
                self.session.delete(f"{self.supabase_url}/rest/v1/course_enrollments?id=eq.{student_id}", headers=headers, timeout=8)
                self.session.delete(f"{self.supabase_url}/rest/v1/course_enrollments?user_id=eq.{student_id}", headers=headers, timeout=8)
                deleted = True
            except Exception as e:
                print(f"[Supabase] delete_student warning: {e}")

        store = self._read_local_store()
        if "students" in store:
            init_len = len(store["students"])
            store["students"] = [s for s in store["students"] if s.get("id") != student_id and s.get("user_id") != student_id]
            if len(store["students"]) < init_len:
                deleted = True
            self._write_local_store(store)
        return deleted or True

    # =========================================================================
    # DURABLE INGESTION JOB STATE MACHINE (SUPABASE + LOCAL RECOVERY)
    # =========================================================================

    def create_job(
        self,
        course_id: str,
        title: str,
        media_url: str = "",
        file_id: Optional[str] = None,
        lesson_id: Optional[str] = None,
        user_id: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a new durable ingestion job with initial state 'QUEUED'."""
        import datetime
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        lesson_id = lesson_id or f"lesson_{uuid.uuid4().hex[:8]}"

        job_payload = {
            "id": job_id,
            "course_id": course_id,
            "lesson_id": lesson_id,
            "user_id": user_id,
            "title": title,
            "media_url": media_url,
            "file_id": file_id,
            "idempotency_key": idempotency_key or f"{course_id}::{file_id or media_url}::{title}",
            "status": "QUEUED",
            "current_stage": "QUEUED",
            "progress_percent": 0,
            "stage_message": "Ingestion job queued and awaiting worker assignment.",
            "checkpoints": {},
            "error_message": None,
            "attempts": 0,
            "max_attempts": 3,
            "created_at": now_iso,
            "updated_at": now_iso,
            "completed_at": None
        }

        # 1. Persist to Supabase if available
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                headers["Prefer"] = "return=representation"
                res = self.session.post(
                    f"{self.supabase_url}/rest/v1/ingestion_jobs",
                    headers=headers,
                    json=job_payload,
                    timeout=8
                )
                if res.ok and res.json():
                    created = res.json()[0]
                    # Also keep local store updated
                    store = self._read_local_store()
                    store["jobs"][job_id] = created
                    self._write_local_store(store)
                    return created
                else:
                    print(f"[Supabase] ingestion_jobs insert notice HTTP {res.status_code}: {res.text}")
            except Exception as e:
                print(f"[Supabase] create_job warning: {e}")

        # 2. Local store persistence
        store = self._read_local_store()
        store["jobs"][job_id] = job_payload
        self._write_local_store(store)
        return job_payload

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves an ingestion job by ID from Supabase or local store."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                res = self.session.get(
                    f"{self.supabase_url}/rest/v1/ingestion_jobs?id=eq.{job_id}&select=*",
                    headers=headers,
                    timeout=6
                )
                if res.ok and len(res.json()) > 0:
                    job = res.json()[0]
                    store = self._read_local_store()
                    store["jobs"][job_id] = job
                    self._write_local_store(store)
                    return job
            except Exception as e:
                print(f"[Supabase] get_job warning: {e}")

        store = self._read_local_store()
        return store.get("jobs", {}).get(job_id)

    def find_job_by_idempotency_key(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Finds any active or recently completed job matching the idempotency key."""
        if not idempotency_key:
            return None

        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                res = self.session.get(
                    f"{self.supabase_url}/rest/v1/ingestion_jobs?idempotency_key=eq.{idempotency_key}&order=created_at.desc&limit=1&select=*",
                    headers=headers,
                    timeout=6
                )
                if res.ok and len(res.json()) > 0:
                    return res.json()[0]
            except Exception as e:
                print(f"[Supabase] find_job_by_idempotency_key warning: {e}")

        store = self._read_local_store()
        for j in store.get("jobs", {}).values():
            if j.get("idempotency_key") == idempotency_key:
                return j
        return None

    def update_job_stage(
        self,
        job_id: str,
        stage: str,
        status: str = "IN_PROGRESS",
        progress_percent: int = 0,
        stage_message: str = "",
        checkpoint_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Updates the stage, status, progress, and incremental checkpoints of an ingestion job."""
        import datetime
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        store = self._read_local_store()
        job = store.get("jobs", {}).get(job_id) or self.get_job(job_id)
        if not job:
            return None

        job["current_stage"] = stage
        job["status"] = status
        job["progress_percent"] = max(0, min(100, progress_percent))
        if stage_message:
            job["stage_message"] = stage_message
        if error_message is not None:
            job["error_message"] = error_message
        job["updated_at"] = now_iso

        if checkpoint_data:
            if "checkpoints" not in job or not isinstance(job["checkpoints"], dict):
                job["checkpoints"] = {}
            job["checkpoints"].update(checkpoint_data)

        # Update local store
        store["jobs"][job_id] = job
        self._write_local_store(store)

        # Sync to Supabase
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                patch_payload = {
                    "current_stage": job["current_stage"],
                    "status": job["status"],
                    "progress_percent": job["progress_percent"],
                    "stage_message": job["stage_message"],
                    "error_message": job.get("error_message"),
                    "checkpoints": job.get("checkpoints", {}),
                    "updated_at": now_iso
                }
                res = self.session.patch(
                    f"{self.supabase_url}/rest/v1/ingestion_jobs?id=eq.{job_id}",
                    headers=headers,
                    json=patch_payload,
                    timeout=8
                )
                if not res.ok:
                    print(f"[Supabase] update_job_stage patch notice HTTP {res.status_code}: {res.text}")
            except Exception as e:
                print(f"[Supabase] update_job_stage warning: {e}")

        return job

    def complete_job(
        self,
        job_id: str,
        lesson_id: str,
        duration_seconds: int = 0,
        total_chunks: int = 0,
        stage_message: str = "Lecture successfully processed and indexed."
    ) -> Optional[Dict[str, Any]]:
        """Transitions job to terminal 'COMPLETED' state."""
        import datetime
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        store = self._read_local_store()
        job = store.get("jobs", {}).get(job_id) or self.get_job(job_id)
        if not job:
            return None

        job["status"] = "COMPLETED"
        job["current_stage"] = "COMPLETED"
        job["progress_percent"] = 100
        job["stage_message"] = stage_message
        job["lesson_id"] = lesson_id
        job["completed_at"] = now_iso
        job["updated_at"] = now_iso
        if "checkpoints" not in job or not isinstance(job["checkpoints"], dict):
            job["checkpoints"] = {}
        job["checkpoints"]["duration_seconds"] = duration_seconds
        job["checkpoints"]["total_chunks_indexed"] = total_chunks

        store["jobs"][job_id] = job
        self._write_local_store(store)

        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                patch_payload = {
                    "status": "COMPLETED",
                    "current_stage": "COMPLETED",
                    "progress_percent": 100,
                    "stage_message": stage_message,
                    "lesson_id": lesson_id,
                    "checkpoints": job["checkpoints"],
                    "completed_at": now_iso,
                    "updated_at": now_iso
                }
                self.session.patch(
                    f"{self.supabase_url}/rest/v1/ingestion_jobs?id=eq.{job_id}",
                    headers=headers,
                    json=patch_payload,
                    timeout=8
                )
            except Exception as e:
                print(f"[Supabase] complete_job patch warning: {e}")

        return job

    def fail_job(self, job_id: str, error_message: str) -> Optional[Dict[str, Any]]:
        """Transitions job to terminal 'FAILED' state with sanitized error description."""
        import datetime
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        store = self._read_local_store()
        job = store.get("jobs", {}).get(job_id) or self.get_job(job_id)
        if not job:
            return None

        job["status"] = "FAILED"
        job["current_stage"] = "FAILED"
        job["error_message"] = error_message
        job["stage_message"] = f"Failed: {error_message}"
        job["updated_at"] = now_iso

        store["jobs"][job_id] = job
        self._write_local_store(store)

        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                patch_payload = {
                    "status": "FAILED",
                    "current_stage": "FAILED",
                    "error_message": error_message,
                    "stage_message": f"Failed: {error_message}",
                    "updated_at": now_iso
                }
                self.session.patch(
                    f"{self.supabase_url}/rest/v1/ingestion_jobs?id=eq.{job_id}",
                    headers=headers,
                    json=patch_payload,
                    timeout=8
                )
            except Exception as e:
                print(f"[Supabase] fail_job patch warning: {e}")

        return job

    def cancel_job(self, job_id: str) -> bool:
        """Marks a queued or in-progress job as CANCELLED."""
        import datetime
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        store = self._read_local_store()
        if "jobs" not in store or not isinstance(store["jobs"], dict):
            store["jobs"] = {}

        job = store["jobs"].get(job_id) or self.get_job(job_id)
        if not job:
            return False

        if job.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
            return False

        job["status"] = "CANCELLED"
        job["current_stage"] = "CANCELLED"
        job["stage_message"] = "Job cancelled by instructor."
        job["updated_at"] = now_iso

        store = self._read_local_store()
        if "jobs" not in store or not isinstance(store["jobs"], dict):
            store["jobs"] = {}
        store["jobs"][job_id] = job
        self._write_local_store(store)

        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                self.session.patch(
                    f"{self.supabase_url}/rest/v1/ingestion_jobs?id=eq.{job_id}",
                    headers=headers,
                    json={"status": "CANCELLED", "current_stage": "CANCELLED", "stage_message": "Job cancelled by instructor.", "updated_at": now_iso},
                    timeout=8
                )
            except Exception as e:
                print(f"[Supabase] cancel_job warning: {e}")

        return True

    def list_jobs(self, course_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists recent ingestion jobs, optionally filtered by course_id."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                url = f"{self.supabase_url}/rest/v1/ingestion_jobs?select=*&order=created_at.desc&limit={limit}"
                if course_id:
                    url += f"&course_id=eq.{course_id}"
                res = self.session.get(url, headers=headers, timeout=8)
                if res.ok and isinstance(res.json(), list):
                    return res.json()
            except Exception as e:
                print(f"[Supabase] list_jobs warning: {e}")

        store = self._read_local_store()
        jobs = list(store.get("jobs", {}).values())
        if course_id:
            jobs = [j for j in jobs if j.get("course_id") == course_id]
        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return jobs[:limit]

    def log_security_threat(
        self,
        lesson_id: str,
        lesson_title: str,
        threat_type: str,
        ip_address: str,
        user_agent: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        details: Optional[str] = None
    ) -> Dict[str, Any]:
        """Records an illegal download attempt or scraper activity."""
        import datetime
        threat_id = f"threat_{uuid.uuid4().hex[:12]}"
        record = {
            "id": threat_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "lesson_id": lesson_id,
            "lesson_title": lesson_title,
            "threat_type": threat_type,
            "ip_address": ip_address,
            "user_agent": (user_agent or "")[:250],
            "user_id": user_id or "anonymous",
            "user_email": user_email or "unknown",
            "details": details or "",
            "action_taken": "BLOCKED_403"
        }

        store = self._read_local_store()
        if "security_threats" not in store:
            store["security_threats"] = []
        store["security_threats"].insert(0, record)
        store["security_threats"] = store["security_threats"][:500]
        self._write_local_store(store)

        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                self.session.post(
                    f"{self.supabase_url}/rest/v1/security_threat_logs",
                    headers=headers,
                    json=record,
                    timeout=5
                )
            except Exception:
                pass

        return record

    def get_security_threats(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent security threats for admin dashboard."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                url = f"{self.supabase_url}/rest/v1/security_threat_logs?select=*&order=timestamp.desc&limit={limit}"
                res = self.session.get(url, headers=headers, timeout=5)
                if res.ok and isinstance(res.json(), list) and len(res.json()) > 0:
                    return res.json()
            except Exception:
                pass

        store = self._read_local_store()
        return store.get("security_threats", [])[:limit]

    def clear_security_threats(self) -> bool:
        """Clears security threat records."""
        store = self._read_local_store()
        store["security_threats"] = []
        self._write_local_store(store)
        return True

    # --- ASSIGNMENT & MCQ STORAGE METHODS ---

    def _serialize_assignment_for_supabase(self, assignment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Serializes internal assignment model to Supabase course_assignments schema."""
        aid = assignment_data.get("id") or str(uuid.uuid4())
        course_id = assignment_data.get("course_id")
        if not course_id and assignment_data.get("lesson_id"):
            lesson = self.get_lesson(assignment_data.get("lesson_id"))
            if lesson:
                course_id = lesson.get("course_id")
        if not course_id:
            course_id = "course-python-programming-comple-386c"

        title = assignment_data.get("title") or "Milestone Practical Assignment"
        starter_code = assignment_data.get("starter_code") or ""
        max_score = int(assignment_data.get("max_score") or 100)
        due_date = assignment_data.get("due_date") or ""
        status = assignment_data.get("status") or "draft"
        scenario = assignment_data.get("scenario_context") or ""
        problems = assignment_data.get("problems") or []
        rubric = assignment_data.get("rubric") or {}
        summary = assignment_data.get("description") or f"Hands-on assignment for lecture {assignment_data.get('lesson_id')}"

        instructions = [
            f"Challenge {p.get('problem_number', idx+1)} ({p.get('tier', 'Core')}) [{p.get('marks', 0)} pts]: {p.get('problem_statement', '')}"
            for idx, p in enumerate(problems)
        ]

        desc_payload = {
            "summary": summary,
            "lesson_id": assignment_data.get("lesson_id"),
            "status": status,
            "scenario_context": scenario,
            "problems": problems,
            "rubric": rubric,
            "assignment_type": assignment_data.get("assignment_type", "CODING")
        }
        if "quality_report" in assignment_data:
            desc_payload["quality_report"] = assignment_data["quality_report"]

        return {
            "id": aid,
            "course_id": course_id,
            "title": title,
            "description": json.dumps(desc_payload, ensure_ascii=False),
            "instructions": instructions,
            "starter_code": starter_code,
            "max_score": max_score,
            "due_date": due_date
        }

    def _deserialize_assignment_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Deserializes Supabase course_assignments row into internal assignment model."""
        desc = row.get("description") or ""
        parsed = {}
        if isinstance(desc, str) and desc.strip().startswith("{") and desc.strip().endswith("}"):
            try:
                parsed = json.loads(desc)
            except Exception:
                parsed = {}

        raw_problems = parsed.get("problems") or []
        assign_type = parsed.get("assignment_type") or "CODING"
        for p in raw_problems:
            if "goal_type" not in p:
                p["goal_type"] = "THEORY" if assign_type == "THEORY" else "CODING"

        return {
            "id": row.get("id"),
            "course_id": row.get("course_id"),
            "lesson_id": parsed.get("lesson_id") or row.get("module_id"),
            "title": row.get("title"),
            "description": parsed.get("summary") or desc,
            "scenario_context": parsed.get("scenario_context") or "",
            "starter_code": row.get("starter_code") or "",
            "assignment_type": assign_type,
            "problems": raw_problems,
            "rubric": parsed.get("rubric") or {
                "logic_and_correctness": 50,
                "syntax_and_quality": 25,
                "edge_cases": 15,
                "approach_clarity": 10
            },
            "max_score": row.get("max_score") or 100,
            "due_date": row.get("due_date") or "",
            "status": parsed.get("status") or "published",
            "quality_report": parsed.get("quality_report"),
            "created_at": row.get("created_at")
        }

    def save_assignment(self, assignment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves or updates an assignment record directly in Supabase course_assignments."""
        aid = assignment_data.get("id") or str(uuid.uuid4())
        assignment_data["id"] = aid

        if self.supabase_url and self.supabase_key:
            try:
                supabase_payload = self._serialize_assignment_for_supabase(assignment_data)
                headers = self._get_headers()
                headers["Prefer"] = "resolution=merge-duplicates,return=representation"
                res = self.session.post(
                    f"{self.supabase_url}/rest/v1/course_assignments",
                    headers=headers,
                    json=supabase_payload,
                    timeout=8
                )
                if res.ok and res.json():
                    created_row = res.json()[0]
                    created = self._deserialize_assignment_from_supabase(created_row)
                    store = self._read_local_store()
                    store.setdefault("assignments", {})[aid] = created
                    self._write_local_store(store)
                    return created
                else:
                    print(f"[Supabase] save_assignment HTTP {res.status_code}: {res.text[:150]}")
            except Exception as e:
                print(f"[Supabase] save_assignment notice: {e}")

        store = self._read_local_store()
        store.setdefault("assignments", {})[aid] = assignment_data
        self._write_local_store(store)
        return assignment_data

    def get_assignment_by_id(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves assignment by ID from Supabase course_assignments."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                url = f"{self.supabase_url}/rest/v1/course_assignments?id=eq.{assignment_id}&select=*"
                res = self.session.get(url, headers=headers, timeout=5)
                if res.ok and len(res.json()) > 0:
                    return self._deserialize_assignment_from_supabase(res.json()[0])
            except Exception as e:
                print(f"[Supabase] get_assignment_by_id notice: {e}")

        store = self._read_local_store()
        return store.get("assignments", {}).get(assignment_id)

    def get_assignment_by_lesson(self, lesson_id: str, status: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves latest assignment for a lesson from Supabase course_assignments with graceful course fallback."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                lesson = self.get_lesson(lesson_id)
                course_id = lesson.get("course_id") if lesson else None
                url = f"{self.supabase_url}/rest/v1/course_assignments?"
                if course_id:
                    url += f"course_id=eq.{course_id}&"
                url += "order=created_at.desc&limit=20"
                res = self.session.get(url, headers=headers, timeout=6)
                if res.ok and res.json():
                    first_course_match = None
                    for row in res.json():
                        deserialized = self._deserialize_assignment_from_supabase(row)
                        is_status_ok = (status is None or deserialized.get("status") == status)
                        if is_status_ok and not first_course_match:
                            first_course_match = deserialized
                        if deserialized.get("lesson_id") == lesson_id:
                            if is_status_ok:
                                return deserialized
                    # Graceful fallback: return the latest published assignment for this course
                    if first_course_match:
                        return first_course_match
            except Exception as e:
                print(f"[Supabase] get_assignment_by_lesson notice: {e}")

        store = self._read_local_store()
        assignments = list(store.get("assignments", {}).values())
        matching = [a for a in assignments if a.get("lesson_id") == lesson_id]
        if status:
            matching = [a for a in matching if a.get("status") == status]
        if matching:
            return matching[-1]
        # Local fallback by course
        if lesson_id:
            lesson = self.get_lesson(lesson_id)
            if lesson and lesson.get("course_id"):
                c_matches = [a for a in assignments if a.get("course_id") == lesson["course_id"]]
                if status:
                    c_matches = [a for a in c_matches if a.get("status") == status]
                if c_matches:
                    return c_matches[-1]
        return None

    def update_assignment_status(self, assignment_id: str, status: str) -> bool:
        """Updates assignment status (draft, published, archived)."""
        return self.update_assignment(assignment_id, {"status": status})

    def update_assignment(self, assignment_id: str, updates: Dict[str, Any]) -> bool:
        """Updates assignment structured fields (title, scenario, problems, status, etc.)."""
        if not updates:
            return True

        existing = self.get_assignment_by_id(assignment_id) or {}
        merged = {**existing, **updates}
        merged["id"] = assignment_id

        if self.supabase_url and self.supabase_key:
            try:
                serialized = self._serialize_assignment_for_supabase(merged)
                patch_payload = {
                    "title": serialized.get("title"),
                    "description": serialized.get("description"),
                    "starter_code": serialized.get("starter_code"),
                    "max_score": serialized.get("max_score"),
                    "due_date": serialized.get("due_date"),
                    "instructions": serialized.get("instructions")
                }
                headers = self._get_headers()
                url = f"{self.supabase_url}/rest/v1/course_assignments?id=eq.{assignment_id}"
                res = self.session.patch(url, headers=headers, json=patch_payload, timeout=6)
                if res.ok:
                    store = self._read_local_store()
                    store.setdefault("assignments", {})[assignment_id] = merged
                    self._write_local_store(store)
                    return True
                else:
                    print(f"[Supabase] update_assignment patch HTTP {res.status_code}: {res.text[:150]}")
            except Exception as e:
                print(f"[Supabase] update_assignment notice: {e}")

        store = self._read_local_store()
        store.setdefault("assignments", {})[assignment_id] = merged
        self._write_local_store(store)
        return True

    def _resolve_supabase_user_id(self, student_id: str, student_email: str = "") -> Optional[str]:
        """Resolves a student identifier or email to a valid auth UUID in Supabase profiles."""
        if not (self.supabase_url and self.supabase_key):
            return None
        try:
            uuid.UUID(str(student_id))
            return str(student_id)
        except (ValueError, TypeError):
            pass

        try:
            headers = self._get_headers()
            if student_email:
                r = self.session.get(f"{self.supabase_url}/rest/v1/profiles?email=eq.{student_email}&select=id", headers=headers, timeout=4)
                if r.ok and r.json():
                    return r.json()[0]["id"]
            r_all = self.session.get(f"{self.supabase_url}/rest/v1/profiles?limit=1&select=id", headers=headers, timeout=4)
            if r_all.ok and r_all.json():
                return r_all.json()[0]["id"]
        except Exception:
            pass
        return None

    def save_submission(self, submission_data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves or updates a student assignment submission in Supabase assignment_submissions."""
        raw_id = str(submission_data.get("id") or "")
        try:
            uuid.UUID(raw_id)
            sid = raw_id
        except (ValueError, TypeError):
            sid = str(uuid.uuid4())
        submission_data["id"] = sid

        assignment_id = submission_data.get("assignment_id")
        course_id = submission_data.get("course_id")
        if not course_id and assignment_id:
            assign = self.get_assignment_by_id(assignment_id)
            if assign:
                course_id = assign.get("course_id")
        if not course_id:
            course_id = "course-python-programming-comple-386c"
        submission_data["course_id"] = course_id

        student_id = str(submission_data.get("student_id") or "anonymous_student")
        student_email = str(submission_data.get("student_email") or "")
        student_name = str(submission_data.get("student_name") or "Student")

        score = int(submission_data.get("ai_score") if submission_data.get("ai_score") is not None else (submission_data.get("score") or 0))
        ai_feedback = submission_data.get("ai_feedback") or submission_data.get("feedback") or {}

        raw_status = str(submission_data.get("status") or "graded").lower()
        db_status = raw_status if raw_status in ("submitted", "graded") else "graded"

        # Embed complete submission context into feedback payload
        feedback_bundle = {
            **(ai_feedback if isinstance(ai_feedback, dict) else {"raw_feedback": str(ai_feedback)}),
            "student_id": student_id,
            "student_name": student_name,
            "student_email": student_email,
            "security_status": raw_status,
            "score": score
        }

        user_id = self._resolve_supabase_user_id(student_id, student_email)

        if self.supabase_url and self.supabase_key and user_id:
            try:
                headers = self._get_headers()
                headers["Prefer"] = "resolution=merge-duplicates,return=representation"
                supabase_sub_payload = {
                    "id": sid,
                    "assignment_id": assignment_id,
                    "course_id": course_id,
                    "user_id": user_id,
                    "submission_code": str(submission_data.get("submission_content") or submission_data.get("submission_code") or "")[:20000],
                    "submission_text": str(submission_data.get("approach_notes") or submission_data.get("submission_text") or "")[:5000],
                    "score": score,
                    "feedback": json.dumps(feedback_bundle, ensure_ascii=False),
                    "status": db_status
                }
                res = self.session.post(
                    f"{self.supabase_url}/rest/v1/assignment_submissions?on_conflict=assignment_id,user_id",
                    headers=headers,
                    json=supabase_sub_payload,
                    timeout=8
                )
                if res.ok and res.json():
                    created = res.json()[0]
                    # Augment with rich app fields
                    created["ai_score"] = score
                    created["ai_feedback"] = feedback_bundle
                    created["student_id"] = student_id
                    created["student_name"] = student_name
                    created["student_email"] = student_email
                    created["status"] = raw_status
                    store = self._read_local_store()
                    store.setdefault("submissions", {})[sid] = created
                    self._write_local_store(store)
                    return created
                else:
                    print(f"[Supabase] save_submission HTTP {res.status_code}: {res.text[:150]}")
            except Exception as e:
                print(f"[Supabase] save_submission notice: {e}")

        store = self._read_local_store()
        store.setdefault("submissions", {})[sid] = submission_data
        self._write_local_store(store)
        return submission_data

    def _deserialize_submission_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Deserializes Supabase assignment_submissions row into full app model."""
        fb_raw = row.get("feedback") or ""
        fb = {}
        if isinstance(fb_raw, str) and fb_raw.strip().startswith("{"):
            try:
                fb = json.loads(fb_raw)
            except Exception:
                fb = {"raw_feedback": fb_raw}
        elif isinstance(fb_raw, dict):
            fb = fb_raw

        score = row.get("score") if row.get("score") is not None else fb.get("score", 0)
        return {
            "id": row.get("id"),
            "assignment_id": row.get("assignment_id"),
            "course_id": row.get("course_id"),
            "student_id": fb.get("student_id") or row.get("user_id"),
            "student_name": fb.get("student_name") or "Student",
            "student_email": fb.get("student_email") or "",
            "submission_content": row.get("submission_code") or row.get("submission_text") or "",
            "submission_code": row.get("submission_code") or "",
            "submission_text": row.get("submission_text") or "",
            "score": score,
            "ai_score": score,
            "feedback": fb,
            "ai_feedback": fb,
            "status": row.get("status") or "graded",
            "submitted_at": row.get("submitted_at"),
            "evaluated_at": row.get("graded_at") or row.get("submitted_at")
        }

    def get_submission(self, assignment_id: str, student_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a student's submission for an assignment from Supabase or local store."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                url = f"{self.supabase_url}/rest/v1/assignment_submissions?assignment_id=eq.{assignment_id}&order=submitted_at.desc"
                res = self.session.get(url, headers=headers, timeout=5)
                if res.ok and res.json():
                    for row in res.json():
                        deserialized = self._deserialize_submission_row(row)
                        if deserialized.get("student_id") == student_id or row.get("user_id") == student_id:
                            return deserialized
            except Exception as e:
                print(f"[Supabase] get_submission notice: {e}")

        store = self._read_local_store()
        submissions = list(store.get("submissions", {}).values())
        for sub in submissions:
            if sub.get("assignment_id") == assignment_id and (sub.get("student_id") == student_id or sub.get("id") == student_id):
                return sub
        return None

    def list_assignment_submissions(self, assignment_id: str) -> List[Dict[str, Any]]:
        """Lists all student submissions for an assignment (Teacher portal)."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                url = f"{self.supabase_url}/rest/v1/assignment_submissions?assignment_id=eq.{assignment_id}&order=submitted_at.desc"
                res = self.session.get(url, headers=headers, timeout=8)
                if res.ok and isinstance(res.json(), list):
                    return [self._deserialize_submission_row(r) for r in res.json()]
            except Exception as e:
                print(f"[Supabase] list_assignment_submissions notice: {e}")

        store = self._read_local_store()
        submissions = list(store.get("submissions", {}).values())
        return [s for s in submissions if s.get("assignment_id") == assignment_id]

    def save_mcq_bank(self, lesson_id: str, questions: List[Dict[str, Any]]) -> bool:
        """Caches a verified question bank for a lesson in Supabase course_quizzes and local store."""
        lesson = self.get_lesson(lesson_id)
        course_id = (lesson.get("course_id") if lesson else None) or "course-python-programming-comple-386c"
        quiz_id = f"quiz_{lesson_id}"
        quiz_title = f"Lecture Practice Arena: {lesson.get('title', 'Lecture Quiz') if lesson else 'Lecture Quiz'}"

        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                headers["Prefer"] = "resolution=merge-duplicates,return=representation"
                payload = {
                    "id": quiz_id,
                    "course_id": course_id,
                    "title": quiz_title,
                    "description": json.dumps({"lesson_id": lesson_id}, ensure_ascii=False),
                    "time_limit_minutes": 15,
                    "questions": questions
                }
                res = self.session.post(
                    f"{self.supabase_url}/rest/v1/course_quizzes",
                    headers=headers,
                    json=payload,
                    timeout=8
                )
                if not res.ok:
                    print(f"[Supabase] save_mcq_bank HTTP {res.status_code}: {res.text[:150]}")
            except Exception as e:
                print(f"[Supabase] save_mcq_bank notice: {e}")

        store = self._read_local_store()
        store.setdefault("mcq_banks", {})[lesson_id] = questions
        self._write_local_store(store)
        return True

    def get_mcq_bank(self, lesson_id: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieves cached MCQ bank for a lesson from Supabase course_quizzes or local store."""
        quiz_id = f"quiz_{lesson_id}"
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                url = f"{self.supabase_url}/rest/v1/course_quizzes?id=eq.{quiz_id}&select=questions&limit=1"
                res = self.session.get(url, headers=headers, timeout=5)
                if res.ok and len(res.json()) > 0:
                    qs = res.json()[0].get("questions")
                    if qs and isinstance(qs, list) and len(qs) > 0:
                        return qs
                url_desc = f"{self.supabase_url}/rest/v1/course_quizzes?description=like.*{lesson_id}*&select=questions&limit=1"
                res_desc = self.session.get(url_desc, headers=headers, timeout=5)
                if res_desc.ok and len(res_desc.json()) > 0:
                    qs = res_desc.json()[0].get("questions")
                    if qs and isinstance(qs, list) and len(qs) > 0:
                        return qs
            except Exception as e:
                print(f"[Supabase] get_mcq_bank notice: {e}")

        store = self._read_local_store()
        return store.get("mcq_banks", {}).get(lesson_id)

    def save_quiz_attempt(
        self,
        lesson_id: str,
        student_id: str,
        selected_answers: Dict[str, Any],
        score: int,
        total: int
    ) -> bool:
        """Saves a student quiz attempt to Supabase quiz_attempts table."""
        user_id = self._resolve_supabase_user_id(student_id)
        if self.supabase_url and self.supabase_key and user_id:
            try:
                headers = self._get_headers()
                headers["Prefer"] = "resolution=merge-duplicates,return=representation"
                attempt_id = str(uuid.uuid4())
                quiz_id = f"quiz_{lesson_id}"
                payload = {
                    "id": attempt_id,
                    "quiz_id": quiz_id,
                    "user_id": user_id,
                    "selected_answers": selected_answers,
                    "score": score,
                    "total_questions": total
                }
                res = self.session.post(
                    f"{self.supabase_url}/rest/v1/quiz_attempts",
                    headers=headers,
                    json=payload,
                    timeout=6
                )
                if res.ok:
                    return True
                else:
                    print(f"[Supabase] save_quiz_attempt HTTP {res.status_code}: {res.text[:150]}")
            except Exception as e:
                print(f"[Supabase] save_quiz_attempt notice: {e}")
        return False

    def schedule_live_session(
        self,
        course_id: str,
        title: str,
        description: str,
        scheduled_at: str,
        host_name: str = "Faculty"
    ) -> Dict[str, Any]:
        """Schedules a new live class session."""
        session_id = str(uuid.uuid4())
        safe_course = "".join(c for c in course_id if c.isalnum() or c == "_")
        agora_channel = f"climbup_{safe_course}_{session_id[:8]}"
        
        session_data = {
            "id": session_id,
            "course_id": course_id,
            "title": title,
            "description": description or "",
            "scheduled_at": scheduled_at,
            "status": "scheduled",
            "agora_channel": agora_channel,
            "host_name": host_name,
            "recording_url": None,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                headers["Prefer"] = "return=representation"
                res = self.session.post(
                    f"{self.supabase_url}/rest/v1/live_sessions",
                    headers=headers,
                    json=session_data,
                    timeout=5
                )
                if res.ok and res.json():
                    return res.json()[0]
                else:
                    print(f"[Supabase] schedule_live_session notice ({res.status_code}): {res.text[:120]}")
            except Exception as e:
                print(f"[Supabase] schedule_live_session error: {e}")
                
        with self._store_lock:
            store = self._read_local_store()
            if "live_sessions" not in store:
                store["live_sessions"] = {}
            store["live_sessions"][session_id] = session_data
            self._write_local_store(store)
            
        return session_data

    def get_live_sessions(
        self,
        course_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lists live sessions filtered by course and/or status."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                url = f"{self.supabase_url}/rest/v1/live_sessions?select=*"
                if course_id:
                    url += f"&course_id=eq.{course_id}"
                if status:
                    url += f"&status=eq.{status}"
                url += "&order=scheduled_at.asc"
                res = self.session.get(url, headers=headers, timeout=5)
                if res.ok:
                    return res.json()
            except Exception as e:
                print(f"[Supabase] get_live_sessions notice: {e}")
                
        store = self._read_local_store()
        sessions = list(store.get("live_sessions", {}).values())
        if course_id:
            sessions = [s for s in sessions if s.get("course_id") == course_id]
        if status:
            sessions = [s for s in sessions if s.get("status") == status]
        return sorted(sessions, key=lambda s: s.get("scheduled_at", ""))

    def get_live_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Gets a live session by ID."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                url = f"{self.supabase_url}/rest/v1/live_sessions?id=eq.{session_id}&select=*"
                res = self.session.get(url, headers=headers, timeout=5)
                if res.ok and res.json():
                    return res.json()[0]
            except Exception as e:
                print(f"[Supabase] get_live_session_by_id notice: {e}")
                
        store = self._read_local_store()
        return store.get("live_sessions", {}).get(session_id)

    def update_live_session_status(
        self,
        session_id: str,
        status: str,
        recording_url: Optional[str] = None
    ) -> bool:
        """Updates live session status ('scheduled', 'live', 'completed', 'cancelled') and optional recording_url."""
        updates: Dict[str, Any] = {"status": status, "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        if recording_url is not None:
            updates["recording_url"] = recording_url
            
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                url = f"{self.supabase_url}/rest/v1/live_sessions?id=eq.{session_id}"
                res = self.session.patch(url, headers=headers, json=updates, timeout=5)
                if res.ok:
                    return True
            except Exception as e:
                print(f"[Supabase] update_live_session_status notice: {e}")
                
        with self._store_lock:
            store = self._read_local_store()
            if "live_sessions" in store and session_id in store["live_sessions"]:
                store["live_sessions"][session_id].update(updates)
                self._write_local_store(store)
                return True
        return False

    def delete_live_session(self, session_id: str) -> bool:
        """Deletes a live session."""
        if self.supabase_url and self.supabase_key:
            try:
                headers = self._get_headers()
                url = f"{self.supabase_url}/rest/v1/live_sessions?id=eq.{session_id}"
                res = self.session.delete(url, headers=headers, timeout=5)
                if res.ok:
                    return True
            except Exception as e:
                print(f"[Supabase] delete_live_session notice: {e}")
                
        with self._store_lock:
            store = self._read_local_store()
            if "live_sessions" in store and session_id in store["live_sessions"]:
                del store["live_sessions"][session_id]
                self._write_local_store(store)
                return True
        return False
