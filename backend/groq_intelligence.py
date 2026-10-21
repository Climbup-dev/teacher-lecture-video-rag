import os
import json
import logging
import requests
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class GroqIntelligence:
    """
    Ultra-fast Query Intelligence Layer powered by Groq.
    Provides:
    1. Sub-second intent classification (Lecture Doubt vs Out-of-Scope).
    2. Instant direct & friendly answers for out-of-scope/general queries with a polite lecture reminder.
    3. Query canonicalization & technical term optimization for Gemini embedding.
    4. Exact time-range extraction in seconds (bypassing regex limitations).
    5. Conversational antecedent resolution.
    """
    GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
    DEFAULT_MODELS = ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"]

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
        env_model = os.getenv("GROQ_MODEL", "").strip()
        self.model = model or env_model or "qwen/qwen3.8-27b"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def analyze_query(
        self,
        query: str,
        lesson_title: str = "",
        lesson_overview: str = "",
        chat_history: Optional[List[Dict[str, str]]] = None,
        timeout: float = 6.0
    ) -> Optional[Dict[str, Any]]:
        """
        Analyzes the student query against the lecture context.
        Returns None if Groq is not configured or if an error occurs (allowing graceful heuristic fallback).
        """
        if not self.is_available:
            return None

        # Build context prompt
        history_context = ""
        if chat_history:
            recent_turns = chat_history[-3:]
            history_context = "\n".join([f"{t.get('role', 'user')}: {t.get('content', '')}" for t in recent_turns])

        system_prompt = (
            "You are an intelligent query analyzer and teaching assistant for a video lecture platform.\n"
            "Analyze the student's query in the context of the current lecture.\n\n"
            f"CURRENT LECTURE TITLE: {lesson_title or 'Educational Video Lecture'}\n"
            f"LECTURE TOPICS/OVERVIEW: {lesson_overview[:1000] if lesson_overview else 'Educational Concepts'}\n\n"
            "YOUR OBJECTIVES:\n"
            "1. Determine whether the student's query is RELEVANT to this lecture or the academic subject of the lecture, or if it is OUT OF SCOPE (e.g. weather, sports, general entertainment, movies, politics, personal questions, unrelated casual chatter).\n"
            "   - Academic concepts related to the lecture domain (e.g. SQL, programming, data, computer science, databases) ARE relevant.\n"
            "   - Questions asking about video navigation or timestamps (e.g. 'what happens around 2-hour mark', '1st hour me kya padhaya') ARE relevant.\n"
            "   - Unrelated general queries are OUT OF SCOPE.\n"
            "2. If OUT OF SCOPE: Provide a clear, concise, accurate 1-2 paragraph helpful direct answer to the student's question.\n"
            "3. If IN SCOPE / RELEVANT:\n"
            "   - Extract any time references into exact start_seconds and end_seconds (e.g., 'around 2 hour mark' -> start: 7140, end: 7260; '1st hour' -> start: 0, end: 3600; 'after 30 mins' -> start: 1800, end: 2400). If no timestamp mentioned, return null.\n"
            "   - Rewrite the query into a clean, canonical technical search query (in English) suitable for dense vector embedding.\n"
            "   - Extract 3-6 high-value technical keywords for sparse keyword matching.\n"
            "   - Resolve any pronouns ('isme', 'yeh', 'after that') using the conversation history.\n\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "is_lecture_related": true | false,\n'
            '  "intent": "lecture_doubt" | "temporal_lookup" | "greeting" | "out_of_scope",\n'
            '  "out_of_scope_direct_answer": "Helpful direct answer if out_of_scope, otherwise empty string",\n'
            '  "optimized_dense_query": "Clean technical query for dense embedding",\n'
            '  "extracted_keywords": ["keyword1", "keyword2"],\n'
            '  "time_range": {"start_seconds": 120, "end_seconds": 240} or null\n'
            "}"
        )

        user_content = f"Student Query: {query}"
        if history_context:
            user_content = f"Recent Conversation History:\n{history_context}\n\n{user_content}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Try active model, fallback to secondary model if needed
        models_to_try = [self.model]
        for m in self.DEFAULT_MODELS:
            if m not in models_to_try:
                models_to_try.append(m)

        for current_model in models_to_try:
            payload = {
                "model": current_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
                "max_tokens": 1000
            }

            try:
                resp = requests.post(self.GROQ_ENDPOINT, headers=headers, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    # Clean markdown fence if present
                    if content.startswith("```"):
                        content = content.strip("`").strip()
                        if content.startswith("json"):
                            content = content[4:].strip()
                    parsed = json.loads(content)
                    logger.info(f"Groq Intelligence parsed with {current_model}: related={parsed.get('is_lecture_related')}, intent={parsed.get('intent')}")
                    return parsed
                else:
                    logger.warning(f"Groq model {current_model} returned HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.warning(f"Groq query analysis failed with {current_model}: {e}")

        return None
