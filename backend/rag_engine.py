import json
import re
import requests
from typing import Dict, Any, List, Optional
from backend.vector_embedder import VectorEmbedder
from backend.db_adapter import DBAdapter

class RAGEngine:
    def __init__(self, gemini_api_key: str, db_adapter: DBAdapter):
        if not gemini_api_key:
            raise ValueError("Gemini API Key is required.")
        self.api_key = gemini_api_key
        self.db = db_adapter
        self.embedder = VectorEmbedder(gemini_api_key)
        self.generation_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"

    def _extract_temporal_seconds(self, query: str) -> Optional[int]:
        """
        Extracts explicit timestamp references from student query in Hindi, Hinglish, or English.
        Handles: '24 min', '24:00', '1 hour 15 min', 'minute 24', '24th minute', '01:23:45', etc.
        """
        q = (query or "").lower().strip()
        # 1. Format HH:MM:SS or MM:SS (e.g. "01:25:30", "24:00", "05:12")
        m = re.search(r'\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b', q)
        if m:
            h, mn, s = m.groups()
            return (int(h or 0) * 3600) + (int(mn) * 60) + int(s)

        # 2. Format: X hour/hr/ghante Y min (e.g. "1 hour 15 min", "2 ghante 10 minute")
        m = re.search(r'(\d+)\s*(?:hours?|hrs?|ghante?|h)\s*(?:and\s*)?(?:(\d+)\s*(?:mins?|minutes?|m\b))?', q)
        if m:
            h = int(m.group(1))
            mn = int(m.group(2) or 0)
            return (h * 3600) + (mn * 60)

        # 3. Format: X min / X minute / Xth min (e.g. "24 min", "24 minute", "24th min", "24m")
        m = re.search(r'(\d+)(?:st|nd|rd|th)?\s*(?:mins?|minutes?|m\b)', q)
        if m:
            return int(m.group(1)) * 60

        # 4. Format: "minute 24" or "min 24"
        m = re.search(r'(?:minute|min)\s*(\d+)', q)
        if m:
            return int(m.group(1)) * 60

        return None

    def _is_overview_query(self, query: str) -> bool:
        """Detects whether student is asking for a global lecture outline or summary across the full 4 hours."""
        q = (query or "").lower().strip()
        overview_terms = [
            "summary", "summarize", "overview", "outline", "syllabus", "roadmap",
            "poore lecture", "poori video", "whole video", "all topics", "what topics",
            "kya kya padhaya", "topics covered", "all chapters", "table of contents",
            "what is this lecture about", "what is this video about", "course content",
            "what was taught in this video", "kya sikhaya"
        ]
        return any(term in q for term in overview_terms)

    def answer_query(
        self,
        query: str,
        lesson_id: str,
        session_id: str = "default-session"
    ) -> Dict[str, Any]:
        """
        Executes a high-precision, student-centric RAG query against the indexed lecture video.
        - Supports exact temporal queries (e.g. '24 min pr kya hua tha').
        - Supports global 4-hour roadmap/outline queries.
        - Uses hybrid semantic + keyword reranking across 7-8 chunks for deep technical accuracy.
        - Prompts Gemini with an empathetic, pedagogy-first persona and clickable [MM:SS] timestamps.
        """
        lesson = self.db.get_lesson(lesson_id)
        lesson_title = lesson.get("title", "Lecture") if lesson else "Lecture"

        # Fetch all chronological chunks for this lecture
        all_chunks = self.db.get_all_chunks_for_lesson(lesson_id)
        if not all_chunks:
            # Fallback to direct search if all_chunks empty
            query_emb = self.embedder.get_embedding(query)
            all_chunks = self.db.search_similar_chunks(query_embedding=query_emb, lesson_id=lesson_id, top_k=6)

        if not all_chunks:
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

        # -------------------------------------------------------------
        # DURATION-ADAPTIVE RETRIEVAL STRATEGY:
        # Tier 1 (<= 15 min, e.g. 10m): 100% Full-Video Context (zero blind spots)
        # Tier 2 (15 - 60 min, e.g. 1h): Focused 6-Chunk Semantic Window
        # Tier 3 (1 - 2.5 hr, e.g. 2h): Deep 8-Chunk Hybrid Expansion
        # Tier 4 (2.5 - 5+ hr, e.g. 4h): Comprehensive 10-Chunk Hybrid + Chapter Roadmap
        # -------------------------------------------------------------
        if duration_mins <= 15 or total_chunks <= 8:
            duration_tier = "MICRO_LESSON"  # 10 min
            top_k_target = total_chunks     # Full 100% transcript passed to Gemini
        elif duration_mins <= 60 or total_chunks <= 35:
            duration_tier = "STANDARD_LECTURE"  # 1 hour
            top_k_target = min(6, total_chunks)
        elif duration_mins <= 150 or total_chunks <= 75:
            duration_tier = "EXTENDED_LECTURE"  # 2 hours
            top_k_target = min(8, total_chunks)
        else:
            duration_tier = "MARATHON_MASTERCLASS"  # 4+ hours
            top_k_target = min(10, total_chunks)

        # Check for temporal intent (e.g. "24 min pr kya hua tha")
        target_seconds = self._extract_temporal_seconds(query)
        is_overview = self._is_overview_query(query)

        retrieved_chunks = []
        query_mode = "semantic"

        if target_seconds is not None:
            # --- 1. TEMPORAL RETRIEVAL ---
            query_mode = "temporal"
            best_idx = 0
            min_dist = float("inf")
            for idx, c in enumerate(all_chunks):
                s = c.get("start_seconds", 0)
                e = c.get("end_seconds", 0)
                if s <= target_seconds <= e:
                    best_idx = idx
                    min_dist = 0
                    break
                dist = min(abs(s - target_seconds), abs(e - target_seconds))
                if dist < min_dist:
                    min_dist = dist
                    best_idx = idx

            # Dynamic Temporal Window:
            # Short video: 1 chunk before/after; 4-hour video: 2 chunks before/after for broad conversational context
            pad = 2 if duration_tier in ("EXTENDED_LECTURE", "MARATHON_MASTERCLASS") else 1
            start_i = max(0, best_idx - pad)
            end_i = min(len(all_chunks), best_idx + pad + 2)
            retrieved_chunks = all_chunks[start_i:end_i]
            for c in retrieved_chunks:
                c["similarity_score"] = 0.99

        elif is_overview:
            # --- 2. GLOBAL OVERVIEW / ROADMAP RETRIEVAL ---
            query_mode = "overview"
            if duration_tier == "MICRO_LESSON":
                retrieved_chunks = list(all_chunks)
            else:
                step = max(1, len(all_chunks) // 10)
                retrieved_chunks = all_chunks[::step][:10]
            for c in retrieved_chunks:
                c["similarity_score"] = 0.95

        elif duration_tier == "MICRO_LESSON":
            # --- 3A. 10-MINUTE VIDEO: FULL CONTEXT (Zero Blind Spots) ---
            query_mode = "full_video"
            retrieved_chunks = list(all_chunks)
            for c in retrieved_chunks:
                c["similarity_score"] = 1.0

        else:
            # --- 3B. 1-HR, 2-HR & 4-HR VIDEOS: HYBRID SEMANTIC + CONCEPT RERANKING ---
            query_emb = self.embedder.get_embedding(query)
            q_tokens = set(re.findall(r'\w+', query.lower()))

            scored_chunks = []
            for c in all_chunks:
                emb = c.get("embedding", [])
                cos_sim = self.embedder.cosine_similarity(query_emb, emb) if emb else 0.0

                concept_text = " ".join([
                    c.get("topic_name", ""),
                    " ".join(c.get("key_concepts", []) or []),
                    " ".join(c.get("hypothetical_questions", []) or []),
                    c.get("cleaned_text", "")[:300]
                ]).lower()
                c_tokens = set(re.findall(r'\w+', concept_text))
                overlap = len(q_tokens.intersection(c_tokens))
                kw_bonus = min(overlap * 0.05, 0.25)

                final_score = (cos_sim * 0.75) + kw_bonus
                scored_chunks.append({
                    **c,
                    "similarity_score": round(final_score, 4)
                })

            scored_chunks.sort(key=lambda x: x["similarity_score"], reverse=True)
            retrieved_chunks = scored_chunks[:top_k_target]

        # 3. Assemble Grounded Context
        context_blocks = []
        for i, c in enumerate(retrieved_chunks):
            start_m, start_s = divmod(int(c.get('start_seconds', 0)), 60)
            end_m, end_s = divmod(int(c.get('end_seconds', 0)), 60)
            ts_badge = f"{start_m:02d}:{start_s:02d}"

            block = (
                f"--- EVIDENCE SEGMENT #{i+1} ---\n"
                f"Topic: {c.get('topic_name', 'Concept')}\n"
                f"Timestamp: [{ts_badge}] ({c.get('start_seconds', 0)}s - {c.get('end_seconds', 0)}s)\n"
                f"Speaker: {c.get('speaker_label', 'Teacher')}\n"
                f"Key Concepts: {', '.join(c.get('key_concepts', []) or [])}\n"
                f"Transcript Content:\n{c.get('cleaned_text', c.get('chunk_text', ''))}\n"
            )
            context_blocks.append(block)

        context_str = "\n".join(context_blocks)

        # Build 4-Hour Course Chapters Outline if overview mode
        roadmap_str = ""
        if is_overview or len(all_chunks) > 10:
            outline_lines = []
            for c in all_chunks[:30]:  # Up to 30 main chapters
                sm, ss = divmod(int(c.get("start_seconds", 0)), 60)
                outline_lines.append(f"- [{sm:02d}:{ss:02d}] {c.get('topic_name', 'Lecture Section')}")
            roadmap_str = "\n".join(outline_lines)

        # 3b. Retrieve prior conversation context for this specific session
        history_msgs = []
        if hasattr(self.db, "get_chat_history") and session_id and session_id != "default-session":
            raw_history = self.db.get_chat_history(session_id, limit=4)
            for h in raw_history:
                sender_label = "Student" if h.get("sender") == "student" else "Professor"
                msg_snip = h.get("message", "").strip()[:180]
                history_msgs.append(f"- {sender_label}: {msg_snip}")

        history_summary = "\n".join(history_msgs) if history_msgs else "New conversation session (no previous messages)."
        safe_query = re.sub(r'[\r\n]+', ' ', (query or "").strip())[:1000]

        # Mode-specific instruction banner
        mode_instruction = ""
        if query_mode == "temporal":
            target_m, target_s = divmod(target_seconds, 60)
            mode_instruction = f"""
🚨 TEMPORAL TIMESTAMP QUERY DETECTED:
The student specifically asked about what happens at timestamp: [{target_m:02d}:{target_s:02d}] ({target_seconds} seconds).
1. IMMEDIATELY in your very first sentence, state what the professor is explaining, demonstrating, or coding at minute {target_m}:{target_s:02d}.
2. Use the exact transcript evidence from that segment to provide a complete, crystal-clear explanation.
"""
        elif query_mode == "overview":
            mode_instruction = f"""
📋 GLOBAL 4-HOUR LECTURE OVERVIEW QUERY:
The student asked for an overview/summary of the whole lecture.
Use the course chapter outline below to provide a structured, chronological roadmap of the full 4 hours:
{roadmap_str}
"""

        # 4. Prompt Gemini for Elite Pedagogical Teaching
        system_instructions = f"""You are the Brilliant, Highly Empathetic AI Professor & Mentor for the university course lecture: "{lesson_title}".
Course Video Profile: ~{duration_mins} Minutes ({duration_tier.replace('_', ' ').title()} - {total_chunks} Total Segments)
A student has asked a doubt. Your mission is to provide an ACCURATE, HIGHLY ENGAGING, PEDAGOGICALLY SOUND, and PRACTICAL explanation strictly grounded in the provided lecture video.

{mode_instruction}

RECENT CONVERSATION CONTEXT:
{history_summary}

LECTURE TRANSCRIPT EVIDENCE (From {duration_mins}-Minute Video):
{context_str}

STUDENT QUESTION:
<<<
{safe_query}
>>>

TEACHING & FORMATTING GUIDELINES:
1. 🎯 DIRECT & ENGAGING START:
   - Answer the student's exact doubt in the first 1-2 sentences. No generic robotic pleasantries.
   - Speak warmly and encouragingly like an exceptional professor (e.g., "Great doubt!", "Here is exactly how this works...").

2. 🧠 CONCEPTUAL CLARITY & REAL-WORLD EXAMPLES:
   - Break down complex logic into clear, bulleted points or numbered steps.
   - If SQL / code is taught in this video, provide clean code blocks with syntax highlighting (` ```sql `).
   - Explain the "WHY" behind the concept, not just a dry recitation of text.

3. ⏱️ ACCURATE TIMESTAMPS & ZERO INLINE BRACKET CLUTTER:
   - Keep the explanation body 100% clean and effortless to read.
   - Place all video jump points EXCLUSIVELY in a dedicated section at the bottom:
     ```
     ### ⏱️ Video Jump Points
     * ⏱️ [MM:SS] - Concept or moment in lecture
     * ⏱️ [MM:SS] - Next key demonstration
     ```
   - (The frontend makes `[MM:SS]` clickable so students can jump straight into that moment of the 4-hour video!)

4. 🌐 MULTILINGUAL EMPATHY (Hindi / Hinglish / Marathi / English):
   - Match the student's language naturally:
     * If the student asks in **Hindi / Hinglish**: Explain warmly in natural, student-friendly Hindi/Hinglish (e.g., "SQL me JOINs ka main purpose hota hai do tables ko relate karna...").
     * If the student asks in **English**: Provide an articulate, crystal-clear academic explanation.

5. 📌 PROFESSOR'S PRO TIPS:
   - Include a brief `### 📌 Professor's Pro Tips` with 1-2 practical insights or common pitfalls to avoid.

6. ❓ 2 PRACTICE QUESTIONS:
   - Conclude with `### ❓ Suggested Practice Questions` with 2 thoughtful questions to help the student test their mastery.
"""

        payload = {
            "contents": [{"parts": [{"text": system_instructions}]}],
            "generationConfig": {
                "temperature": 0.25,
                "topP": 0.95
            }
        }

        # Model priority list
        models_to_try = [
            "gemini-2.5-flash",
            "gemini-3.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
            "gemini-3-flash-preview"
        ]
        raw_answer = ""

        for model_name in models_to_try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            try:
                res = requests.post(endpoint, json=payload, timeout=45)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
                        raw_answer = candidates[0]["content"]["parts"][0].get("text", "")
                        if raw_answer:
                            break
                elif res.status_code in (429, 503):
                    continue
            except Exception:
                continue

        if not raw_answer:
            raw_answer = "Could not generate answer due to AI service temporary availability. Please try again in a moment."

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

