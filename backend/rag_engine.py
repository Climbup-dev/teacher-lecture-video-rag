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

        # 4. Prompt Gemini 2.5 Flash for High-Quality Grounded Answer
        system_instructions = f"""You are the Intelligent Teaching Assistant for the university lecture: "{lesson_title}".
A student has asked a doubt. Your job is to provide an elite, clear, university-grade explanation grounded STRICTLY in the provided lecture transcript evidence.

LECTURE EVIDENCE:
{context_str}

STUDENT QUESTION:
"{query}"

STRICT GUIDELINES FOR HIGH QUALITY:
1. Explain the concept clearly and intuitively, with structured bullet points, definitions, or steps as explained by the professor.
2. For EVERY key assertion, formula, or definition, YOU MUST CITE THE EXACT TIMESTAMP in brackets like `[MM:SS]` (e.g. `[04:12]` or `[14:35]`). The student's video player will automatically jump to this moment when clicked!
3. Differentiate between teacher explanations and student questions from class.
4. If the student asks for something that was NOT mentioned or covered in the provided lecture evidence, clearly state:
   "The professor did not explicitly discuss this detail in this lecture segment." Then provide a concise, factual academic explanation clearly marked as supplementary context.
5. Provide 2 concise suggested follow-up questions at the very end in a `### Suggested Questions` section.
6. CROSS-LINGUAL ADAPTABILITY: If the lecture video is in Hindi or Hinglish and the student asks in English (or vice versa), respond fluently in the language the student used, accurately explaining the professor's spoken points while strictly preserving the bracketed timestamp citations `[MM:SS]`.
"""

        payload = {
            "contents": [{"parts": [{"text": system_instructions}]}],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.95
            }
        }

        # High-quota Free Tier models sequence (gemini-3.5-flash, gemini-3.5-flash-lite, gemini-flash-lite-latest)
        models_to_try = [
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
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
        found_timestamps = re.findall(r'\[(\d{1,3}:\d{2}(?::\d{2})?)\]', raw_answer)

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
