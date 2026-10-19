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

MANDATORY RESPONSE GUIDELINES (Strict Quality & Format):
1. 🎯 CORE TAKEAWAY & CONCEPT BREAKDOWN:
   - Begin with a clear, direct answer that immediately resolves the student's doubt.
   - Break down complex concepts step-by-step using structured markdown headers, bullet points, and bold text.
   - Explain the "Why" and "How" intuitively, using clear real-world analogies, code snippets, or diagrams where appropriate.

2. ⏱️ EXPLICIT CLICKABLE TIMESTAMPS [MM:SS]:
   - For EVERY key explanation, formula, definition, or theorem, cite the exact timestamp in brackets like `[MM:SS]` (e.g. `[02:15]`, `[07:42]`). The student's video player will make these clickable to jump directly to that moment!
   - Include a dedicated section `### ⏱️ Video Moments & Timestamps` summarizing which minute/second covers which sub-topic so the student can easily navigate the lecture.

3. 🎨 RICH EMOJIS & ENGAGING VISUAL HIERARCHY:
   - Use meaningful, aesthetic emojis throughout your response to make learning vibrant, structured, and student-friendly (e.g., 🎯 for Summary, 💡 for Concept Explanation, ⏱️ / 🎥 for Video Jump Links, 🚀 for Examples/Analogies, 📌 for Teacher Notes/Pitfalls, ❓ for Practice Questions).

4. 🌐 MULTILINGUAL EXCELLENCE (Hindi / Hinglish / Marathi / English):
   - Detect the language of the student's question and respond fluently in that SAME language:
     * If asked in **Hindi** or **Hinglish**: Explain warmly in natural, friendly Hindi/Hinglish, keeping technical terms clear and accessible.
     * If asked in **Marathi**: Explain clearly and warmly in natural Marathi with appropriate technical terms.
     * If asked in **English**: Provide an articulate, top-tier academic response.
   - Always strictly retain the bracketed timestamp format `[MM:SS]` regardless of the language used!

5. 📌 STRICT EVIDENCE GROUNDING:
   - Ground all explanations strictly in what the professor covered in the provided transcript.
   - If the student asks about a detail NOT discussed in this lecture segment, clearly note: "📌 *The professor did not explicitly discuss this detail in this lecture clip.*" and provide a brief, helpful supplementary explanation.

6. ❓ SUGGESTED FOLLOW-UP QUESTIONS:
   - End with `### ❓ Suggested Practice Questions` with 2 thoughtful questions to test or deepen the student's understanding.
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
