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

    def answer_query(
        self,
        query: str,
        lesson_id: str,
        session_id: str = "default-session"
    ) -> Dict[str, Any]:
        """
        Executes a high-precision RAG query against the indexed lecture video.
        Retrieves top relevant chunks, builds grounded context, and prompts Gemini 2.5 Flash
        to output an authoritative answer with clickable [MM:SS] video jump timestamps.
        """
        lesson = self.db.get_lesson(lesson_id)
        lesson_title = lesson.get("title", "Lecture") if lesson else "Lecture"

        # 1. Embed student query
        query_emb = self.embedder.get_embedding(query)

        # 2. Retrieve top-4 most semantically similar chunks
        retrieved_chunks = self.db.search_similar_chunks(
            query_embedding=query_emb,
            lesson_id=lesson_id,
            top_k=4
        )

        if not retrieved_chunks:
            return {
                "answer": "No lecture content has been indexed for this lesson yet. Please process the video first.",
                "retrieved_evidence": [],
                "video_timestamps": []
            }

        # 3. Assemble Grounded Context
        context_blocks = []
        for i, c in enumerate(retrieved_chunks):
            start_m, start_s = divmod(int(c['start_seconds']), 60)
            end_m, end_s = divmod(int(c['end_seconds']), 60)
            ts_badge = f"{start_m:02d}:{start_s:02d}"
            
            block = (
                f"--- EVIDENCE CHUNK #{i+1} ---\n"
                f"Topic: {c.get('topic_name', 'Concept')}\n"
                f"Timestamp: [{ts_badge}] (Seconds: {c['start_seconds']} to {c['end_seconds']})\n"
                f"Speaker: {c.get('speaker_label', 'Teacher')}\n"
                f"Transcript Content:\n{c.get('cleaned_text', c.get('chunk_text', ''))}\n"
            )
            context_blocks.append(block)

        context_str = "\n".join(context_blocks)

        # 4. Prompt Gemini for High-Quality Grounded Answer with Emojis & Timestamps
        system_instructions = f"""You are the Intelligent AI Professor & Mentor for the university course lecture: "{lesson_title}".
A student has asked a doubt. Your mission is to provide an ELITE, CLEAR, HIGHLY ENGAGING, and PEDAGOGICALLY SOUND explanation grounded strictly in the provided lecture transcript evidence.

LECTURE EVIDENCE FROM VIDEO:
{context_str}

STUDENT QUESTION:
"{query}"

MANDATORY RESPONSE GUIDELINES (Smart, Clean & Elegant Teaching):
1. 🎯 SMART & FLUID EXPLANATION (ZERO INLINE CLUTTER):
   - Provide a clean, highly intelligent, natural explanation like a world-class mentor.
   - ABSOLUTE RULE: DO NOT put any bracketed timestamps like `[MM:SS]` inside the explanation paragraphs, headings, or bullet points!
   - Keep the body text 100% clean, fluid, and effortless to read. Use clear bold keywords, bullet points, and steps.

2. ⏱️ DEDICATED VIDEO JUMP POINTS AT THE END ONLY:
   - All video timestamps MUST be placed EXCLUSIVELY in a dedicated `### ⏱️ Video Jump Points` section at the bottom.
   - Format:
     ```
     ### ⏱️ Video Jump Points
     * ⏱️ [MM:SS] - Topic / Key Moment 1
     * ⏱️ [MM:SS] - Topic / Key Moment 2
     ```
   - This keeps the explanation smart and readable while providing instant 1-click video navigation.

3. 🎨 VIBRANT EMOJIS & CLEAN VISUAL HIERARCHY:
   - Use meaningful emojis tastefully to highlight section headings and key takeaways (🎯, 💡, ⏱️, 🚀, 📌, ❓).
   - Never overdo emojis on every line; use them on section titles and highlights for a sleek, modern look.

4. 🌐 MULTILINGUAL EXCELLENCE (Hindi / Hinglish / Marathi / English):
   - Match the student's language naturally:
     * If asked in **Hindi / Hinglish**: Explain in smooth, friendly, natural Hindi/Hinglish without awkward literal translations.
     * If asked in **Marathi**: Explain clearly and warmly in natural Marathi.
     * If asked in **English**: Provide an articulate, smart explanation.
   - Preserve the bracketed `[MM:SS]` format strictly in the `### ⏱️ Video Jump Points` section so the video player can seek.

5. 📌 PROFESSOR'S HIGHLIGHTS & TIPS:
   - Include a brief `### 📌 Professor's Pro Tips` section highlighting key warnings (e.g., PATH checkbox, free Community edition) without any inline timestamps.

6. ❓ 2 PRACTICE QUESTIONS:
   - Conclude with `### ❓ Suggested Practice Questions` with 2 thoughtful questions to test the student's understanding.
"""

        payload = {
            "contents": [{"parts": [{"text": system_instructions}]}],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.95
            }
        }

        # Model priority list (Fast, reliable, free-tier compatible)
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
                    raw_answer = data["candidates"][0]["content"]["parts"][0]["text"]
                    break
                elif res.status_code == 429:
                    continue  # Try next available free model
                else:
                    raw_answer = f"Error ({res.status_code}): {res.text}"
            except Exception as e:
                raw_answer = f"AI service error: {str(e)}"

        if not raw_answer:
            raw_answer = "Could not generate answer due to service availability. Please try again in a moment."

        # 5. Extract all timestamps mentioned in the answer (supports MM:SS, MMM:SS, HH:MM:SS)
        extracted = re.findall(r'\[(\d{1,3}:\d{2}(?::\d{2})?)\]', raw_answer)
        # Deduplicate while preserving chronological order
        seen = set()
        found_timestamps = []
        for ts in extracted:
            if ts not in seen:
                seen.add(ts)
                found_timestamps.append(ts)

        # 6. Record interaction in database
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
            retrieved_chunk_ids=[c["id"] for c in retrieved_chunks]
        )

        # Format evidence for frontend display
        evidence_summary = []
        for c in retrieved_chunks:
            evidence_summary.append({
                "id": c["id"],
                "topic_name": c.get("topic_name", "Concept"),
                "start_seconds": c.get("start_seconds", 0),
                "end_seconds": c.get("end_seconds", 0),
                "timestamp_label": c.get("timestamp_label", ""),
                "speaker_label": c.get("speaker_label", "Teacher"),
                "similarity_score": c.get("similarity_score", 0),
                "text_snippet": c.get("cleaned_text", c.get("chunk_text", ""))[:220] + "..."
            })

        return {
            "answer": raw_answer,
            "retrieved_evidence": evidence_summary,
            "video_timestamps": found_timestamps
        }
