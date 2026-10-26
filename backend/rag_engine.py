import json
import re
import requests
from typing import Dict, Any, List, Optional, Tuple
from backend.vector_embedder import VectorEmbedder
from backend.db_adapter import DBAdapter
from backend.groq_intelligence import GroqIntelligence

class RAGEngine:
    def __init__(
        self,
        gemini_api_key: str,
        db_adapter: DBAdapter,
        groq_api_key: Optional[str] = None,
        groq_model: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        openrouter_model: Optional[str] = None
    ):
        if not gemini_api_key:
            raise ValueError("Gemini API Key is required.")
        self.api_key = gemini_api_key
        self.db = db_adapter
        self.embedder = VectorEmbedder(gemini_api_key)
        self.generation_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        self.groq = GroqIntelligence(api_key=groq_api_key, model=groq_model)
        self.openrouter_api_key = (openrouter_api_key or "").strip()
        self.openrouter_model = openrouter_model or "nvidia/nemotron-3.5-lightning:free"

    STOP_WORDS = {
        'hai', 'kya', 'in', 'the', 'a', 'an', 'sir', 'tell', 'explain', 'about',
        'what', 'is', 'of', 'to', 'and', 'me', 'ke', 'ki', 'ka', 'ko', 'par',
        'pe', 'tha', 'thi', 'se', 'kar', 'batao', 'bataiye', 'how', 'why', 'when',
        'where', 'hua', 'kuch', 'bhi', 'karein', 'karta', 'hoti', 'hota', 'hain',
        'or', 'for', 'with', 'be', 'do', 'does', 'did', 'this', 'that', 'it', 'at',
        'ne', 'aap', 'hum', 'sirf', 'konsi', 'konsa', 'kisko', 'kis', 'kisi', 'kare',
        'which', 'who', 'whom', 'whose', 'can', 'you', 'my', 'your', 'we',
        'our', 'us', 'he', 'she', 'they', 'them', 'their', 'use', 'using', 'used',
        'make', 'made', 'say', 'said', 'please', 'give', 'find', 'show', 'calculate',
        'difference', 'between', 'question', 'doubt', 'lecture', 'video', 'class',
        'course', 'topic', 'teacher', 'professor', 'time', 'minute', 'hour', 'second',
        'rule', 'rules', 'algorithm', 'algorithms', 'step', 'steps', 'method', 'methods'
    }

    FOLLOW_UP_INDICATORS = {
        'isme', 'usme', 'ise', 'use', 'ye', 'yeh', 'wo', 'woh', 'this', 'that',
        'it', 'why', 'again', 'how so', 'above', 'previous', 'point', 'second',
        'first', 'third', 'overhead', 'drawback', 'advantage', 'reason'
    }

    @staticmethod
    def _format_timestamp(seconds: int) -> str:
        """Formats seconds into [HH:MM:SS] if >= 1 hour, or [MM:SS] if < 1 hour."""
        seconds = max(0, int(seconds))
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _extract_time_range(self, query: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Extracts timestamp intervals or points from student query across all video durations (10m to 4h).
        Returns (start_seconds, end_seconds).
        - '1st hour' / 'pehla ghanta' -> (0, 3600)
        - '2nd hour' / 'doosra ghanta' -> (3600, 7200)
        - '3rd hour' -> (7200, 10800)
        - '4th hour' -> (10800, 14400)
        - '1 se 2 ghante ke beech' -> (3600, 7200)
        - 'between 2 and 3 hours' -> (7200, 10800)
        - '5 se 8 minute ke beech' -> (300, 480)
        - '02:15:30' -> (8130, 8130)
        - '24 min' -> (1440, 1440)
        - '03:10' -> (190, 190)
        """
        q = (query or "").lower().strip()

        # Check hour-related queries
        if any(hw in q for hw in ('hour', 'ghanta', 'ghante', 'hr')):
            # 1. Word & Number Ordinals: '1st hour', '2nd hour', 'first hour', 'second hour', '3rd hour', 'third hour', '4th hour', 'fourth hour'
            word_ords = {'first': 1, '1st': 1, 'second': 2, '2nd': 2, 'third': 3, '3rd': 3, 'fourth': 4, '4th': 4}
            for w, num in word_ords.items():
                if re.search(r'\b' + w + r'\s*[- ]*(?:hour|ghanta|ghante|hr)\b', q):
                    return ((num - 1) * 3600, num * 3600)

            # 2. Multi-Hour Interval: '1 to 2 hours', '1 se 2 ghante', 'between 2 and 3 hours'
            m_hr_range = re.search(r'(?:between\s*)?(\d+)\s*(?:to|se|-|and)\s*(\d+)\s*(?:hours?|hrs?|ghante?)', q)
            if m_hr_range:
                h1 = int(m_hr_range.group(1)) * 3600
                h2 = int(m_hr_range.group(2)) * 3600
                return (min(h1, h2), max(h1, h2))

            # 3. Compound: X hour Y min (e.g. '2 hour 15 min', '1 ghanta 10 minute', '2-hour 15-min')
            m_h_m = re.search(r'(\d+)\s*[- ]*(?:hours?|hrs?|ghante?|h)\s*(?:and\s*)?(\d+)\s*(?:mins?|minutes?|m\b)', q)
            if m_h_m:
                sec = int(m_h_m.group(1)) * 3600 + int(m_h_m.group(2)) * 60
                return (sec, sec)

            # 4. Point Hour: 'around the 2-hour mark', '2-hour mark', 'at the 2 hour mark', '2 hours', '2 ghante'
            m_pt = re.search(r'(?:around|at|near)?\s*(\d+)\s*[- ]*(?:hours?|hrs?|ghante?|h)(?:\s*(?:mark|point))?', q)
            if m_pt:
                sec = int(m_pt.group(1)) * 3600
                return (sec, sec)

        # 5. Minute Interval: X se Y min / X to Y min / between X and Y mins
        m = re.search(r'(?:between\s*)?(\d+)\s*(?:se|to|-|and)\s*(\d+)\s*(?:mins?|minutes?|m\b)', q)
        if m:
            s = int(m.group(1)) * 60
            e = int(m.group(2)) * 60
            return (min(s, e), max(s, e))

        # 6. Specific minute point (e.g. "24 min", "24th min", "minute 24")
        m = re.search(r'(\d+)(?:st|nd|rd|th)?\s*(?:mins?|minutes?|m\b)', q)
        if m:
            sec = int(m.group(1)) * 60
            return (sec, sec)

        m = re.search(r'(?:minute|min)\s*(\d+)', q)
        if m:
            sec = int(m.group(1)) * 60
            return (sec, sec)

        return (None, None)

    def _is_overview_query(self, query: str) -> bool:
        """Detects whether student is asking for a global lecture outline or summary across the full lecture."""
        q = (query or "").lower().strip()
        overview_terms = [
            "summary", "summarize", "overview", "outline", "syllabus", "roadmap",
            "poore lecture", "poori video", "whole video", "all topics", "what topics",
            "kya kya padhaya", "topics covered", "all chapters", "table of contents",
            "what is this lecture about", "what is this video about", "course content",
            "what was taught in this video", "kya sikhaya"
        ]
        return any(term in q for term in overview_terms)

    def _is_reverse_temporal_query(self, query: str) -> bool:
        """Detects if student is asking WHEN a topic was discussed (e.g. 'At what time was X explained?')."""
        q = (query or "").lower().strip()
        indicators = ["when was", "at what time", "which minute", "kab bataya", "kab sikhaya", "kis time pe", "kis minute"]
        return any(ind in q for ind in indicators)

    def _extract_domain_keywords(self, text: str) -> List[str]:
        """Extracts significant non-stopword tokens from student query for keyword reranking."""
        tokens = re.findall(r'\b[a-zA-Z_]{3,}\b', (text or "").lower())
        return [t for t in tokens if t not in self.STOP_WORDS]

    def _generate_pedagogical_answer(self, system_instructions: str, safe_query: str) -> str:
        """
        Dual-Engine High-Speed Generation:
        1. Ultra-fast Groq Qwen 27B (~1.2s response time) for instant student feedback.
        2. High-precision Gemini 2.5 Flash as robust secondary fallback.
        """
        # --- TIER 1: Ultra-Fast Groq Engine (~0.8s) ---
        if hasattr(self, "groq") and self.groq.is_available:
            groq_key = self.groq.api_key
            groq_endpoint = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json"
            }
            models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
            for gm in models:
                try:
                    payload = {
                        "model": gm,
                        "messages": [
                            {"role": "system", "content": system_instructions},
                            {"role": "user", "content": safe_query}
                        ],
                        "temperature": 0.2,
                        "max_tokens": 1024
                    }
                    r = requests.post(groq_endpoint, headers=headers, json=payload, timeout=8)
                    if r.status_code == 200:
                        choices = r.json().get("choices", [])
                        if choices and choices[0].get("message", {}).get("content"):
                            return choices[0]["message"]["content"].strip()
                except Exception:
                    continue

        # --- TIER 2: OpenRouter High-Quality Free Backup ---
        openrouter_key = getattr(self, "openrouter_api_key", "")
        if openrouter_key:
            openrouter_endpoint = "https://openrouter.ai/api/v1/chat/completions"
            or_headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json"
            }
            or_models = [
                getattr(self, "openrouter_model", "nvidia/nemotron-3.5-lightning:free"),
                "cohere/north-mini-code:free",
                "liquid/lfm-2.5-2.6b:free"
            ]
            for om in or_models:
                try:
                    payload = {
                        "model": om,
                        "messages": [
                            {"role": "system", "content": system_instructions},
                            {"role": "user", "content": safe_query}
                        ],
                        "temperature": 0.2,
                        "max_tokens": 1024
                    }
                    r = requests.post(openrouter_endpoint, headers=or_headers, json=payload, timeout=10)
                    if r.status_code == 200:
                        choices = r.json().get("choices", [])
                        if choices and choices[0].get("message", {}).get("content"):
                            return choices[0]["message"]["content"].strip()
                except Exception:
                    continue

        # --- TIER 3: Gemini Enterprise Fallback (Preserved primarily for video processing) ---
        payload = {
            "contents": [{"parts": [{"text": f"{system_instructions}\n\nSTUDENT QUESTION:\n{safe_query}"}]}],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.9,
                "maxOutputTokens": 2048
            }
        }
        models_to_try = [
            "gemini-2.5-flash",
            "gemini-3.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-flash-latest"
        ]
        for model_name in models_to_try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            try:
                res = requests.post(endpoint, json=payload, timeout=25)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
                        txt = candidates[0]["content"]["parts"][0].get("text", "")
                        if txt:
                            return txt.strip()
            except Exception:
                continue

        return "Could not generate answer due to AI service temporary availability. Please try again in a moment."

    def answer_query(
        self,
        query: str,
        lesson_id: str,
        session_id: str = "default-session"
    ) -> Dict[str, Any]:
        """
        Executes a high-precision, student-centric RAG query against the indexed lecture video.
        - Precision time-range & point timestamp extraction.
        - Antecedent follow-up resolution using conversation history.
        - Stopword-filtered domain keyword reranking.
        - Strict abstention guardrails for out-of-scope inquiries.
        - Clickable [MM:SS] video jump points.
        """
        lesson = self.db.get_lesson(lesson_id)
        lesson_title = lesson.get("title", "Lecture") if lesson else "Lecture"
        course_id = lesson.get("course_id", "") if lesson else ""

        # Fetch all chronological chunks for this lecture
        all_chunks = self.db.get_all_chunks_for_lesson(lesson_id)
        if not all_chunks:
            # Fallback to direct search if all_chunks empty
            query_emb = self.embedder.get_embedding(query)
            all_chunks = self.db.search_similar_chunks(query_embedding=query_emb, lesson_id=lesson_id, top_k=6)

        if not all_chunks:
            if lesson and lesson.get("processing_status") in ("indexing", "processing"):
                return {
                    "answer": "⏳ **AI Copilot is currently indexing this lecture in the background!**\n\nThe video playback is completely live and available for you to watch. AI timestamped doubts, conceptual notes, and practice quizzes will unlock automatically in 1–2 minutes as soon as the background processing finishes.",
                    "retrieved_evidence": [],
                    "video_timestamps": []
                }
            return {
                "answer": "No lecture content has been indexed for this lesson yet. Please process the video first.",
                "retrieved_evidence": [],
                "video_timestamps": []
            }

        raw_duration = lesson.get("duration_seconds", 0) if lesson else 0
        if not raw_duration and all_chunks:
            raw_duration = int(all_chunks[-1].get("end_seconds", 0))

        duration_mins = raw_duration // 60 if raw_duration else (len(all_chunks) * 2)
        total_chunks = len(all_chunks)

        # Retrieve prior conversation context for this specific session
        history_msgs = []
        last_student_msg = ""
        if hasattr(self.db, "get_chat_history") and session_id and session_id != "default-session":
            raw_history = self.db.get_chat_history(session_id, limit=4)
            for h in raw_history:
                sender_label = "Student" if h.get("sender") == "student" else "Professor"
                msg_snip = h.get("message", "").strip()[:500]  # Expand to 500 chars to avoid truncating technical code
                history_msgs.append(f"- {sender_label}: {msg_snip}")
                if h.get("sender") == "student" and not last_student_msg:
                    last_student_msg = h.get("message", "").strip()

        history_summary = "\n".join(history_msgs) if history_msgs else "New conversation session (no previous messages)."
        safe_query = re.sub(r'[\r\n]+', ' ', (query or "").strip())[:1000]

        # Follow-up query resolution: augment query with prior topic if pronoun/reference detected
        search_query = safe_query
        q_tokens = set(re.findall(r'\b[a-zA-Z0-9_]+\b', safe_query.lower()))
        has_followup_marker = bool(q_tokens.intersection(self.FOLLOW_UP_INDICATORS))
        if has_followup_marker and last_student_msg:
            search_query = f"{last_student_msg} {safe_query}"

        # -------------------------------------------------------------
        # DURATION-ADAPTIVE RETRIEVAL STRATEGY:
        # Tier 1 (<= 15 min, e.g. 10m): Focused window (4-8 chunks)
        # Tier 2 (15 - 60 min, e.g. 1h): Focused 6-Chunk Semantic Window
        # Tier 3 (1 - 2.5 hr, e.g. 2h): Deep 8-Chunk Hybrid Expansion
        # Tier 4 (2.5 - 5+ hr, e.g. 4h): Comprehensive 10-Chunk Hybrid + Chapter Roadmap
        # -------------------------------------------------------------
        if duration_mins <= 15 or total_chunks <= 8:
            duration_tier = "MICRO_LESSON"
            top_k_target = min(4, total_chunks)
        elif duration_mins <= 60 or total_chunks <= 35:
            duration_tier = "STANDARD_LECTURE"
            top_k_target = min(6, total_chunks)
        elif duration_mins <= 150 or total_chunks <= 75:
            duration_tier = "EXTENDED_LECTURE"
            top_k_target = min(8, total_chunks)
        else:
            duration_tier = "MARATHON_MASTERCLASS"
            top_k_target = min(10, total_chunks)

        # Check for temporal intent & intervals
        range_start, range_end = self._extract_time_range(safe_query)
        is_overview = self._is_overview_query(safe_query)
        is_reverse_temporal = self._is_reverse_temporal_query(safe_query)

        # -------------------------------------------------------------
        # GROQ QUERY INTELLIGENCE & INTENT ROUTING
        # -------------------------------------------------------------
        groq_keywords = []
        if hasattr(self, "groq") and self.groq.is_available:
            lesson_overview = ""
            if all_chunks:
                sample_topics = [str(c.get("topic_name", "")) for c in all_chunks[:6] if c.get("topic_name")]
                sample_concepts = []
                for c in all_chunks[:6]:
                    kc = c.get("key_concepts", [])
                    if isinstance(kc, list):
                        sample_concepts.extend([str(k) for k in kc if k])
                    elif isinstance(kc, str) and kc.strip():
                        sample_concepts.append(kc.strip())
                lesson_overview = f"Topics: {', '.join(sample_topics)}. Concepts: {', '.join(sample_concepts[:12])}"

            groq_analysis = self.groq.analyze_query(
                query=safe_query,
                lesson_title=lesson_title,
                lesson_overview=lesson_overview,
                chat_history=raw_history if 'raw_history' in locals() else None
            )

            if groq_analysis:
                # 1. OUT OF SCOPE / IRRELEVANT QUERY WITH HELPFUL DIRECT ANSWER
                if groq_analysis.get("is_lecture_related") is False:
                    intent = (groq_analysis.get("intent") or "").lower()
                    direct_ans = (groq_analysis.get("out_of_scope_direct_answer") or "").strip()
                    
                    # Detect greetings, compliments, acknowledgments (e.g. "THAT GREATE", "thanks", "hello", "hi")
                    lower_q = safe_query.lower()
                    is_pleasantry = (
                        intent == "greeting" or
                        any(w in lower_q for w in ["great", "thanks", "thank you", "hello", "hi", "namaste", "awesome", "perfect", "good", "ok", "understood"])
                    )

                    if is_pleasantry:
                        answer_text = direct_ans or f"You're very welcome! I'm here to help you master **{lesson_title}**. Let me know whenever you have any conceptual questions or need any topic explained."
                        return {
                            "answer": answer_text,
                            "retrieved_evidence": [],
                            "video_timestamps": []
                        }

                    if direct_ans:
                        warning_msg = (
                            f"> ℹ️ **General Concept Note:**\n"
                            f"> {direct_ans}\n\n"
                            f"*Tip: This lecture focuses on **{lesson_title}**. Feel free to ask any specific doubt, code example, or timestamp question from this video!*"
                        )
                    else:
                        warning_msg = (
                            f"> ℹ️ **Lecture Focus Reminder:**\n"
                            f"> This doubt is outside the topics covered in **{lesson_title}**.\n\n"
                            f"Please ask any question related to the lecture concepts, code, or theory covered in this video."
                        )
                    return {
                        "answer": warning_msg,
                        "retrieved_evidence": [],
                        "video_timestamps": []
                    }

                # 2. TEMPORAL BOUNDS EXTRACTED BY GROQ
                time_range = groq_analysis.get("time_range")
                if time_range and isinstance(time_range, dict):
                    t_start = time_range.get("start_seconds")
                    t_end = time_range.get("end_seconds")
                    if t_start is not None and t_end is not None:
                        range_start, range_end = int(t_start), int(t_end)

                # 3. QUERY REWRITING FOR DENSE EMBEDDING
                opt_dense_q = (groq_analysis.get("optimized_dense_query") or "").strip()
                if opt_dense_q:
                    search_query = opt_dense_q

                # 4. KEYWORDS FOR SPARSE MATCHING
                groq_keywords = [k.lower().strip() for k in (groq_analysis.get("extracted_keywords") or []) if k.strip()]

        retrieved_chunks = []
        query_mode = "semantic"

        if range_start is not None and range_end is not None:
            # --- 1. TEMPORAL RANGE / POINT RETRIEVAL ---
            query_mode = "temporal"
            # Bounds check against video duration
            max_duration = max((c.get("end_seconds", 0) for c in all_chunks), default=0)
            if max_duration > 0 and range_start > (max_duration + 60):
                formatted_ts = self._format_timestamp(range_start)
                formatted_max = self._format_timestamp(max_duration)
                return {
                    "answer": f"⚠️ **Timestamp Beyond Video Duration:** The requested timestamp [{formatted_ts}] is beyond the end of this lecture video (Total length: ~{formatted_max}).\n\nPlease check the timestamp and ask questions about the material covered within this video!",
                    "retrieved_evidence": [],
                    "video_timestamps": []
                }

            # Find all chunks overlapping with [range_start, range_end]
            matching_indices = []
            for idx, c in enumerate(all_chunks):
                s = c.get("start_seconds", 0)
                e = c.get("end_seconds", 0)
                if s <= range_end and e >= range_start:
                    matching_indices.append(idx)

            if not matching_indices:
                # Find single nearest chunk
                best_idx = min(range(len(all_chunks)), key=lambda i: abs(all_chunks[i].get("start_seconds", 0) - range_start))
                matching_indices = [best_idx]

            # Context window: Pad ±1 chunk
            min_i = max(0, min(matching_indices) - 1)
            max_i = min(len(all_chunks), max(matching_indices) + 2)
            retrieved_chunks = all_chunks[min_i:max_i]
            for c in retrieved_chunks:
                c["similarity_score"] = 0.99

        elif is_overview:
            # --- 2. GLOBAL OVERVIEW / ROADMAP RETRIEVAL ---
            query_mode = "overview"
            step = max(1, len(all_chunks) // 8)
            retrieved_chunks = all_chunks[::step][:8]
            for c in retrieved_chunks:
                c["similarity_score"] = 0.95

        else:
            # --- 3. HYBRID SEMANTIC + DOMAIN KEYWORD RERANKING ---
            query_emb = self.embedder.get_embedding(search_query)
            domain_tokens = set(self._extract_domain_keywords(search_query))
            if groq_keywords:
                domain_tokens.update(groq_keywords)

            # Fetch candidates from indexed pgvector RPC first
            rpc_matches = self.db.search_similar_chunks(
                query_embedding=query_emb,
                lesson_id=lesson_id,
                course_id=course_id,
                top_k=max(top_k_target * 2, 12)
            )

            # Map candidates by chunk_index
            candidates = rpc_matches if rpc_matches else all_chunks

            scored_chunks = []
            for c in candidates:
                emb = c.get("embedding", [])
                cos_sim = c.get("similarity_score")
                if cos_sim is None:
                    cos_sim = self.embedder.cosine_similarity(query_emb, emb) if emb else 0.0

                # Weighted Domain Keyword Matching:
                topic_txt = (c.get("topic_name") or "").lower()
                concepts_txt = " ".join(c.get("key_concepts") or []).lower()
                body_txt = (c.get("cleaned_text") or c.get("chunk_text") or "")[:400].lower()

                kw_score = 0.0
                for token in domain_tokens:
                    if token in topic_txt:
                        kw_score += 0.12
                    elif token in concepts_txt:
                        kw_score += 0.09
                    elif token in body_txt:
                        kw_score += 0.04

                kw_bonus = min(kw_score, 0.30)
                final_score = (float(cos_sim) * 0.70) + kw_bonus

                scored_chunks.append({
                    **c,
                    "similarity_score": round(final_score, 4),
                    "raw_cos_sim": round(float(cos_sim), 4),
                    "kw_bonus": round(kw_bonus, 4)
                })

            scored_chunks.sort(key=lambda x: x["similarity_score"], reverse=True)
            retrieved_chunks = scored_chunks[:top_k_target]

            # --- 4. ABSTENTION GUARDRAIL FOR OUT-OF-SCOPE QUESTIONS ---
            max_sim = max((c["raw_cos_sim"] for c in scored_chunks), default=0.0)
            max_kw = max((c["kw_bonus"] for c in scored_chunks), default=0.0)

            # If semantic similarity is under 0.53 and zero domain keywords match
            if max_sim < 0.53 and max_kw < 0.05 and not has_followup_marker:
                return {
                    "answer": f"⚠️ **Topic Not Discussed:** The professor does not discuss or cover \"{safe_query}\" in this lecture (Yeh topic is lecture me cover nahi kiya gaya hai).\n\nThis lecture focuses strictly on **{lesson_title}**. Please feel free to ask questions about the concepts taught in this class!",
                    "retrieved_evidence": [],
                    "video_timestamps": []
                }

        # 3. Assemble Grounded Context
        context_blocks = []
        for i, c in enumerate(retrieved_chunks):
            start_ts = self._format_timestamp(c.get('start_seconds', 0))
            end_ts = self._format_timestamp(c.get('end_seconds', 0))

            block = (
                f"--- EVIDENCE SEGMENT #{i+1} ---\n"
                f"Topic: {c.get('topic_name', 'Concept')}\n"
                f"Timestamp: [{start_ts}] ({c.get('start_seconds', 0)}s - {c.get('end_seconds', 0)}s)\n"
                f"Speaker: {c.get('speaker_label', 'Teacher')}\n"
                f"Key Concepts: {', '.join(c.get('key_concepts', []) or [])}\n"
                f"Transcript Content:\n{c.get('cleaned_text', c.get('chunk_text', ''))}\n"
            )
            context_blocks.append(block)

        context_str = "\n".join(context_blocks)

        # Build Course Chapters Outline evenly sampled across full lecture duration (1h, 2h, 3h, 4h)
        roadmap_str = ""
        if is_overview or len(all_chunks) > 8:
            outline_lines = []
            if len(all_chunks) <= 25:
                sampled = all_chunks
            else:
                stride = (len(all_chunks) - 1) / 24.0
                indices = sorted(list({int(round(i * stride)) for i in range(25)}))
                sampled = [all_chunks[idx] for idx in indices if idx < len(all_chunks)]

            for c in sampled:
                ts_str = self._format_timestamp(c.get("start_seconds", 0))
                topic = c.get('topic_name', 'Lecture Section')
                outline_lines.append(f"- [{ts_str}] {topic}")
            roadmap_str = "\n".join(outline_lines)

        # Mode-specific instruction banner
        mode_instruction = ""
        if query_mode == "temporal" and range_start is not None:
            start_badge = self._format_timestamp(range_start)
            end_badge = self._format_timestamp(range_end)
            if range_start == range_end:
                mode_instruction = f"""
🚨 EXACT TIMESTAMP QUERY DETECTED:
The student specifically asked about what happens at timestamp: [{start_badge}] ({range_start} seconds).
1. IMMEDIATELY in your very first sentence, state what the professor is explaining or demonstrating at [{start_badge}].
2. Use the exact transcript evidence from that segment to provide a complete explanation.
"""
            else:
                mode_instruction = f"""
🚨 TIME INTERVAL QUERY DETECTED:
The student specifically asked about the interval from [{start_badge}] to [{end_badge}] ({range_start}s to {range_end}s).
1. IMMEDIATELY in your very first sentence, summarize what was taught during this specific time span ({start_badge} - {end_badge}).
2. Detail the topics discussed chronologically across this interval.
"""
        elif is_reverse_temporal:
            mode_instruction = """
⏱️ REVERSE TEMPORAL QUERY DETECTED:
The student wants to know WHEN a concept was explained.
1. State the exact timestamp in the first sentence: "The professor explained [Topic] at timestamp [MM:SS]..."
2. Explain the concept and attach the video jump point.
"""
        elif query_mode == "overview":
            mode_instruction = f"""
📋 GLOBAL LECTURE OVERVIEW QUERY:
The student asked for an overview/summary of the lecture.
Use the course chapter outline below to provide a structured, chronological roadmap:
{roadmap_str}
"""

        # 4. Prompt for Elite Pedagogical Teaching & Mentoring
        system_instructions = f"""You are the Elite AI Professor, Dedicated Mentor & Personal Tutor for the university course lecture: "{lesson_title}".
Course Video Profile: ~{duration_mins} Minutes ({duration_tier.replace('_', ' ').title()} - {total_chunks} Total Segments)
A student has asked a doubt. Your mission is to DEEPLY UNDERSTAND their exact question, explain it with CRYSTAL CLARITY, guide them step-by-step, and provide practical insights strictly grounded in the lecture.

{mode_instruction}

RECENT CONVERSATION CONTEXT:
{history_summary}

LECTURE TRANSCRIPT EVIDENCE (From {duration_mins}-Minute Video):
{context_str}

PEDAGOGICAL TEACHING & FORMATTING GUIDELINES:
1. 🎯 IMMEDIATE DIRECT ANSWER (Zero AI Filler):
   - Answer the student's exact doubt directly in the very first sentence.
   - NEVER start with generic pleasantries like "That is an excellent question!", "Sure!", "Certainly!", or "I would be happy to help".
   - Start immediately with the core concept definition or explanation.

2. 💡 SIMPLE EXPLANATION & INTUITIVE ANALOGY:
   - Break down complex architectural/technical terms into simple, relatable concepts.
   - Use an intuitive real-world analogy (e.g., hotel receptionist, traffic police, restaurant waiter, security guard) to make the concept stick.

3. 🛠️ ACTIONABLE MECHANISM & HOW IT WORKS:
   - Present 2 to 4 clean, structured bullet points or steps explaining how it works or how to implement it as taught in the lecture.
   - If code or query syntax is relevant, provide a clean, minimal code block with syntax highlighting and clear comments.

4. 🌐 MATCH STUDENT'S LANGUAGE & TONE NATURALLY:
   - If the student asks in **Hindi / Hinglish**: Respond in natural, warm, friendly, clear developer Hinglish (e.g., "Dekho, simple shabdon mein...", "Basically yahan par teacher ne samjhaya hai ki...").
   - If the student asks in **English**: Respond in crisp, well-structured, professional English.

5. ⏱️ CLICKABLE VIDEO JUMP POINTS:
   - Conclude with 1 to 3 exact video jump points referencing where the teacher discussed or demonstrated the topic:
     ### ⏱️ Video Jump Points
     * ⏱️ [MM:SS] - Concept or demonstration label

6. 💡 PRO TIP / KEY TAKEAWAY:
   - End with a single crisp "💡 Pro Tip" or "Key Insight" to help the student remember this for interviews or practical projects.
"""

        raw_answer = self._generate_pedagogical_answer(system_instructions, safe_query)

        # Extract timestamps for video jump badges
        extracted = re.findall(r'\[(\d{1,3}:\d{2}(?::\d{2})?)\]', raw_answer)
        seen = set()
        found_timestamps = []
        for ts in extracted:
            if ts not in seen:
                seen.add(ts)
                found_timestamps.append(ts)

        # Record interaction in database
        self.db.record_chat_message(
            session_id=session_id,
            sender="student",
            message=query
        )
        self.db.record_chat_message(
            session_id=session_id,
            sender="ai",
            message=raw_answer,
            timestamp_ref={"timestamps": found_timestamps},
            retrieved_chunk_ids=[c.get("id", "") for c in retrieved_chunks if c.get("id")]
        )

        # Format evidence for frontend display
        evidence_summary = []
        for c in retrieved_chunks:
            evidence_summary.append({
                "id": c.get("id", ""),
                "topic_name": c.get("topic_name", "Concept"),
                "start_seconds": c.get("start_seconds", 0),
                "end_seconds": c.get("end_seconds", 0),
                "timestamp_label": c.get("timestamp_label", ""),
                "speaker_label": c.get("speaker_label", "Teacher"),
                "similarity_score": c.get("similarity_score", 0),
                "text_snippet": (c.get("cleaned_text") or c.get("chunk_text") or "")[:220] + "..."
            })

        return {
            "answer": raw_answer,
            "retrieved_evidence": evidence_summary,
            "video_timestamps": found_timestamps
        }

