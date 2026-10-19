import json
import requests
from typing import List, Dict, Any

class SemanticChunker:
    def __init__(self, gemini_api_key: str):
        if not gemini_api_key:
            raise ValueError("Gemini API Key is required.")
        self.api_key = gemini_api_key
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"

    def chunk_and_enrich(
        self,
        utterances: List[Dict[str, Any]],
        course_title: str = "University Lecture",
        subject_name: str = "Computer Science"
    ) -> List[Dict[str, Any]]:
        """
        Segments lecture utterances into concept-bounded semantic chunks,
        injects hierarchical context breadcrumbs, cleans speech disfluencies,
        and generates hypothetical student search queries (HyDE) for maximum RAG precision.
        """
        if not utterances:
            return []

        # 1. Group utterances into semantic macro-windows (~90-180 seconds or ~250-400 words)
        grouped_windows = self._group_utterances(utterances)

        # 2. Enrich windows in parallel using ThreadPoolExecutor for 8x speedup
        from concurrent.futures import ThreadPoolExecutor

        def _process_single_window(item):
            index, window = item
            enrichment = self._enrich_window_with_gemini(
                window_text=window["raw_text"],
                course_title=course_title,
                subject_name=subject_name,
                speaker_label=window["dominant_speaker"],
                start_label=window["timestamp_label"]
            )
            context_header = f"[{course_title} > {subject_name} > {enrichment.get('topic_name', 'Lecture Section')}]"
            full_chunk_text = (
                f"{context_header}\n"
                f"Speaker: {window['dominant_speaker']} ({window['timestamp_label']})\n"
                f"Content: {enrichment.get('cleaned_text', window['raw_text'])}\n"
                f"Key Concepts: {', '.join(enrichment.get('key_concepts', []))}"
            )
            return {
                "chunk_index": index + 1,
                "start_seconds": window["start_seconds"],
                "end_seconds": window["end_seconds"],
                "timestamp_label": window["timestamp_label"],
                "speaker_label": window["dominant_speaker"],
                "topic_name": enrichment.get("topic_name", "Lecture Topic"),
                "cleaned_text": enrichment.get("cleaned_text", window["raw_text"]),
                "context_header": context_header,
                "chunk_text": full_chunk_text,
                "key_concepts": enrichment.get("key_concepts", []),
                "hypothetical_questions": enrichment.get("hypothetical_questions", [])
            }

        with ThreadPoolExecutor(max_workers=8) as executor:
            enriched_chunks = list(executor.map(_process_single_window, enumerate(grouped_windows)))

        return enriched_chunks

    def _group_utterances(self, utterances: List[Dict[str, Any]], target_word_count: int = 250) -> List[Dict[str, Any]]:
        """Groups sequential utterances respecting natural conversational duration boundaries."""
        windows = []
        current_utts = []
        current_words = 0

        for utt in utterances:
            words = len(utt["text"].split())
            current_utts.append(utt)
            current_words += words

            # If current group has reached ~200-300 words or duration exceeds 150 seconds
            duration = current_utts[-1]["end_seconds"] - current_utts[0]["start_seconds"]
            if current_words >= target_word_count or duration >= 150:
                windows.append(self._build_window(current_utts))
                current_utts = []
                current_words = 0

        if current_utts:
            windows.append(self._build_window(current_utts))

        return windows

    def _build_window(self, utts: List[Dict[str, Any]]) -> Dict[str, Any]:
        start_s = utts[0]["start_seconds"]
        end_s = utts[-1]["end_seconds"]
        start_min, start_sec = divmod(int(start_s), 60)
        end_min, end_sec = divmod(int(end_s), 60)
        timestamp_label = f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}"

        # Combine text
        combined_text = " ".join([u["text"] for u in utts if u["text"].strip()])

        # Determine dominant speaker
        teacher_count = sum(1 for u in utts if u.get("speaker_label") == "Teacher")
        dominant = "Teacher" if teacher_count >= len(utts) / 2 else utts[0].get("speaker_label", "Speaker")

        return {
            "start_seconds": start_s,
            "end_seconds": end_s,
            "timestamp_label": timestamp_label,
            "dominant_speaker": dominant,
            "raw_text": combined_text
        }

    def _enrich_window_with_gemini(
        self,
        window_text: str,
        course_title: str,
        subject_name: str,
        speaker_label: str,
        start_label: str
    ) -> Dict[str, Any]:
        """
        Calls Gemini 2.5 Flash to generate context metadata, cleaned text, and reverse search questions.
        """
        system_prompt = f"""You are an expert AI Audio Data Engineer specializing in Lecture RAG Optimization.
Your goal is to prepare raw speech transcript from a university lecture for maximum vector retrieval quality.

Lecture: {course_title}
Subject: {subject_name}
Timestamp: {start_label}
Speaker: {speaker_label}

Given this raw spoken transcript:
"{window_text}"

Perform the following tasks:
1. `topic_name`: A short, descriptive title of the specific concept or theorem explained in this segment (3-6 words).
2. `cleaned_text`: Clean speech disfluencies (remove "um", "uh", "you know", repetitive stammers) while 100% preserving all technical terms, definitions, equations, numbers, and logical deductions.
3. `key_concepts`: List of 3 to 6 key terms, formulas, or entities mentioned (include standard English technical terms).
4. `hypothetical_questions`: Generate 3 to 4 realistic questions a student would ask that are directly answered by this specific chunk. If the spoken language is Hindi or Hinglish, generate the hypothetical questions in English (and bilingual) so students asking in English match this chunk with high vector similarity.

Output strictly valid JSON with this exact schema:
{{
  "topic_name": "string",
  "cleaned_text": "string",
  "key_concepts": ["string"],
  "hypothetical_questions": ["string"]
}}
"""
        payload = {
            "contents": [{"parts": [{"text": system_prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }

        models_to_try = [
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3-flash-preview"
        ]

        for model_name in models_to_try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            try:
                res = requests.post(endpoint, json=payload, timeout=45)
                if res.status_code == 200:
                    data = res.json()
                    text_out = data["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(text_out)
                elif res.status_code == 429:
                    continue  # Try fallback model
            except Exception:
                pass

        # Fallback if API momentarily fails or times out
        return {
            "topic_name": f"Lecture Segment ({start_label})",
            "cleaned_text": window_text,
            "key_concepts": [],
            "hypothetical_questions": []
        }
