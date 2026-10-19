import os
import json
import requests
from typing import Dict, Any, List, Optional
from pathlib import Path

class DeepgramTranscriber:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Deepgram API Key is required.")
        self.api_key = api_key
        self.base_url = "https://api.deepgram.com/v1/listen"

    def transcribe_file(self, audio_file_path: str) -> Dict[str, Any]:
        """
        Transcribes a local audio file with Nova-2, diarization, punctuation,
        and utterance-level timestamps.
        """
        path = Path(audio_file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        params = {
            "model": "nova-2",
            "detect_language": "true",
            "smart_format": "true",
            "diarize": "true",
            "utterances": "true",
            "punctuate": "true",
            "paragraphs": "true"
        }

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav" if path.suffix.lower() == ".wav" else "audio/mpeg"
        }

        with open(path, "rb") as audio_file:
            response = requests.post(
                self.base_url,
                params=params,
                headers=headers,
                data=audio_file,
                timeout=300
            )

        if response.status_code != 200:
            raise RuntimeError(f"Deepgram API Error ({response.status_code}): {response.text}")

        data = response.json()
        return self._format_response(data)

    def transcribe_url(self, audio_url: str) -> Dict[str, Any]:
        """Transcribes audio from a remote URL."""
        params = {
            "model": "nova-2",
            "detect_language": "true",
            "smart_format": "true",
            "diarize": "true",
            "utterances": "true",
            "punctuate": "true",
            "paragraphs": "true"
        }

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            self.base_url,
            params=params,
            headers=headers,
            json={"url": audio_url},
            timeout=300
        )

        if response.status_code != 200:
            raise RuntimeError(f"Deepgram API Error ({response.status_code}): {response.text}")

        data = response.json()
        return self._format_response(data)

    def _format_response(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardizes Deepgram output into clean transcript, speaker utterances,
        and duration metadata.
        """
        results = raw_data.get("results", {})
        channels = results.get("channels", [{}])
        first_channel = channels[0] if channels else {}
        alternatives = first_channel.get("alternatives", [{}])
        first_alt = alternatives[0] if alternatives else {}
        
        full_transcript = first_alt.get("transcript", "")
        raw_utterances = results.get("utterances", [])

        formatted_utterances: List[Dict[str, Any]] = []
        for utt in raw_utterances:
            speaker_num = utt.get("speaker", 0)
            speaker_label = "Teacher" if speaker_num == 0 else f"Student {speaker_num}"
            start_s = round(float(utt.get("start", 0)), 2)
            end_s = round(float(utt.get("end", 0)), 2)
            
            # Format label MM:SS
            start_min, start_sec = divmod(int(start_s), 60)
            end_min, end_sec = divmod(int(end_s), 60)
            timestamp_label = f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}"

            formatted_utterances.append({
                "speaker_id": speaker_num,
                "speaker_label": speaker_label,
                "start_seconds": start_s,
                "end_seconds": end_s,
                "timestamp_label": timestamp_label,
                "text": utt.get("transcript", "").strip()
            })

        duration = raw_data.get("metadata", {}).get("duration", 0)

        return {
            "full_transcript": full_transcript,
            "duration_seconds": duration,
            "utterances": formatted_utterances,
            "raw_metadata": raw_data.get("metadata", {})
        }
