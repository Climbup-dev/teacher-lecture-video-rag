import os
import json
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from pathlib import Path

class DeepgramTranscriber:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Deepgram API Key is required.")
        self.api_key = api_key
        self.base_url = "https://api.deepgram.com/v1/listen"
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=1)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Probes exact audio duration in seconds using FFmpeg/imageio."""
        try:
            import subprocess
            import shutil
            import imageio_ffmpeg
            ffmpeg_bin = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [ffmpeg_bin, "-i", str(audio_path)]
            res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
            for line in res.stderr.splitlines():
                if "Duration:" in line:
                    part = line.split("Duration:")[1].split(",")[0].strip()
                    h, m, s = part.split(":")
                    return float(h) * 3600 + float(m) * 60 + float(s)
        except Exception:
            pass
        return 0.0

    def _transcribe_single_file(self, path: Path) -> Dict[str, Any]:
        """Low-level single audio file upload to Deepgram Nova-2."""
        params = {
            "model": "nova-2",
            "detect_language": "true",
            "smart_format": "true",
            "diarize": "true",
            "utterances": "true",
            "punctuate": "true",
            "paragraphs": "true"
        }

        ext = path.suffix.lower()
        if ext == ".wav":
            content_type = "audio/wav"
        elif ext in (".m4a", ".mp4", ".aac"):
            content_type = "audio/mp4"
        elif ext == ".ogg":
            content_type = "audio/ogg"
        elif ext == ".flac":
            content_type = "audio/flac"
        elif ext == ".mp3":
            content_type = "audio/mp3"
        else:
            content_type = "audio/mpeg"

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": content_type
        }

        with open(path, "rb") as audio_file:
            response = self.session.post(
                self.base_url,
                params=params,
                headers=headers,
                data=audio_file,
                timeout=600
            )

        if response.status_code != 200:
            raise RuntimeError(f"Deepgram API Error ({response.status_code}): {response.text}")

        data = response.json()
        return self._format_response(data)

    def transcribe_file(self, audio_file_path: str, progress_callback=None) -> Dict[str, Any]:
        """
        Transcribes a local audio file with Nova-2, diarization, punctuation,
        and utterance-level timestamps. For long lectures (>25m), automatically
        slices into manageable segments to prevent Deepgram HTTP 504 timeouts
        and processes them concurrently with ThreadPoolExecutor for 3-4x speedup.
        """
        path = Path(audio_file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        duration = self._get_audio_duration(path)
        CHUNK_THRESHOLD = 1500.0  # 25 minutes
        CHUNK_DURATION = 900.0    # 15 minutes

        # If short audio (<= 25 minutes), transcribe directly
        if duration <= 0 or duration <= CHUNK_THRESHOLD:
            res = self._transcribe_single_file(path)
            if progress_callback:
                try:
                    progress_callback(1, 1)
                except Exception:
                    pass
            return res

        # Long lecture detected: Concurrent chunked transcription with timestamp preservation
        import subprocess
        import shutil
        import imageio_ffmpeg
        ffmpeg_bin = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()

        total_chunks = int((duration + CHUNK_DURATION - 1) // CHUNK_DURATION)
        chunk_dir = path.parent / f"chunks_{path.stem}"
        chunk_dir.mkdir(parents=True, exist_ok=True)

        chunk_tasks = []
        try:
            # 1. Rapidly slice chunks using stream copy (-c copy) in < 1 second total
            for idx in range(total_chunks):
                start_s = idx * CHUNK_DURATION
                seg_dur = min(CHUNK_DURATION, duration - start_s)
                if seg_dur <= 0:
                    break

                chunk_file = chunk_dir / f"chunk_{idx}{path.suffix}"
                cmd = [
                    ffmpeg_bin, "-y",
                    "-ss", str(start_s),
                    "-t", str(seg_dur),
                    "-i", str(path),
                    "-c", "copy",
                    str(chunk_file)
                ]
                subprocess.run(cmd, capture_output=True, check=True)
                chunk_tasks.append((idx, chunk_file, start_s, seg_dur))

            # 2. Concurrently transcribe slices with Deepgram Nova-2 (up to 4 parallel workers)
            results_by_idx: Dict[int, Any] = {}
            completed_count = 0
            lock = threading.Lock()

            def _process_chunk(item):
                nonlocal completed_count
                idx, cfile, start_s, seg_dur = item
                res = None
                try:
                    # Retry once on transient network glitch
                    for attempt in range(2):
                        try:
                            res = self._transcribe_single_file(cfile)
                            break
                        except Exception as err:
                            if attempt == 1:
                                raise err
                            time.sleep(1.0)

                    with lock:
                        results_by_idx[idx] = (res, start_s)
                        completed_count += 1
                        if progress_callback:
                            try:
                                progress_callback(completed_count, len(chunk_tasks))
                            except Exception:
                                pass
                finally:
                    # Immediately purge temporary slice to protect container disk/tmpfs
                    if cfile.exists():
                        try:
                            cfile.unlink()
                        except Exception:
                            pass

            max_workers = min(4, len(chunk_tasks))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                list(executor.map(_process_chunk, chunk_tasks))

            # 3. Assemble results strictly ordered by timestamp
            all_utterances: List[Dict[str, Any]] = []
            transcript_parts: List[str] = []

            for idx in range(len(chunk_tasks)):
                res, start_s = results_by_idx[idx]
                if res.get("full_transcript"):
                    transcript_parts.append(res["full_transcript"])

                for utt in res.get("utterances", []):
                    abs_start = round(utt["start_seconds"] + start_s, 2)
                    abs_end = round(utt["end_seconds"] + start_s, 2)
                    s_min, s_sec = divmod(int(abs_start), 60)
                    e_min, e_sec = divmod(int(abs_end), 60)
                    utt["start_seconds"] = abs_start
                    utt["end_seconds"] = abs_end
                    utt["timestamp_label"] = f"{s_min:02d}:{s_sec:02d} - {e_min:02d}:{e_sec:02d}"
                    all_utterances.append(utt)

            return {
                "full_transcript": "\n".join(transcript_parts),
                "duration_seconds": duration,
                "utterances": all_utterances,
                "raw_metadata": {"chunked": True, "total_chunks": len(chunk_tasks), "duration": duration}
            }
        finally:
            shutil.rmtree(chunk_dir, ignore_errors=True)

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
            timeout=900
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
