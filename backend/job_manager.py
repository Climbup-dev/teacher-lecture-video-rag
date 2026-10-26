import os
import sys
import uuid
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from backend.config import Config, reload_config
from backend.db_adapter import DBAdapter
from backend.audio_extractor import extract_and_clean_audio
from backend.deepgram_transcriber import DeepgramTranscriber
from backend.semantic_chunker import SemanticChunker
from backend.vector_embedder import VectorEmbedder
from backend.google_drive import GoogleDriveManager
from backend.hls_transcoder import HLSTranscoder

logger = logging.getLogger("climbup.job_manager")

class IngestionJobManager:
    """
    Durable Background Ingestion Engine.
    Executes multi-stage lecture RAG pipeline asynchronously with:
    - Bounded concurrency (2 workers) for 1 GB RAM Cloud Run safety.
    - Incremental checkpoint persistence to avoid re-billing Deepgram/Gemini.
    - Idempotency & deduplication.
    - Full terminal state management (QUEUED, IN_PROGRESS, COMPLETED, FAILED, CANCELLED).
    """

    def __init__(self, db_adapter: Optional[DBAdapter] = None, max_workers: int = 2):
        self.db = db_adapter or DBAdapter()
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="rag_ingest_worker")
        logger.info(f"IngestionJobManager initialized with {self.max_workers} worker threads.")

    def submit_job(
        self,
        course_id: str,
        title: str,
        media_url: str = "",
        file_id: Optional[str] = None,
        lesson_id: Optional[str] = None,
        user_id: Optional[str] = None,
        local_filepath: Optional[str] = None,
        force_restart: bool = False
    ) -> Dict[str, Any]:
        """
        Submits a lecture ingestion job idempotently.
        Returns the existing active job if duplicate, or dispatches a new background job.
        """
        reload_config()
        clean_fid = file_id or (GoogleDriveManager.extract_file_id(media_url) if media_url else None)
        idempotency_key = f"{course_id}::{clean_fid or media_url or title}::{title.strip().lower()}"

        # 1. Idempotency check
        if not force_restart:
            existing = self.db.find_job_by_idempotency_key(idempotency_key)
            if existing:
                status = existing.get("status")
                if status in ("QUEUED", "IN_PROGRESS"):
                    logger.info(f"Duplicate job request for key '{idempotency_key}'. Returning existing active job {existing.get('id')}.")
                    return existing
                elif status == "COMPLETED":
                    logger.info(f"Job for key '{idempotency_key}' is already COMPLETED. Returning completed job {existing.get('id')}.")
                    return existing

        # 2. Create durable job record
        job = self.db.create_job(
            course_id=course_id,
            title=title,
            media_url=media_url,
            file_id=clean_fid,
            lesson_id=lesson_id,
            user_id=user_id,
            idempotency_key=idempotency_key
        )
        job_id = job["id"]

        # 3. Dispatch to bounded thread pool
        self.executor.submit(self._execute_pipeline, job_id, local_filepath)
        logger.info(f"Dispatched background ingestion job {job_id} for '{title}' (course: {course_id}).")
        return job

    def retry_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retries a FAILED or interrupted job from its last verified checkpoint."""
        job = self.db.get_job(job_id)
        if not job:
            return None

        if job.get("status") == "IN_PROGRESS":
            return job

        self.db.update_job_stage(
            job_id=job_id,
            stage="QUEUED",
            status="QUEUED",
            progress_percent=10,
            stage_message="Job queued for retry recovery."
        )
        self.executor.submit(self._execute_pipeline, job_id, None)
        return self.db.get_job(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancels an ongoing or queued job."""
        return self.db.cancel_job(job_id)

    def _is_cancelled(self, job_id: str) -> bool:
        job = self.db.get_job(job_id)
        return bool(job and job.get("status") == "CANCELLED")

    def _execute_pipeline(self, job_id: str, local_filepath: Optional[str] = None):
        """Authoritative execution loop with stage transitions, checkpoints, and resource bounds."""
        job = self.db.get_job(job_id)
        if not job:
            logger.error(f"Cannot execute pipeline: job {job_id} not found.")
            return

        lesson_id = job.get("lesson_id") or f"lesson_{uuid.uuid4().hex[:8]}"
        course_id = job.get("course_id", "course-applied-ai-rag")
        title = job.get("title", "Lecture")
        media_url = job.get("media_url", "")
        file_id = job.get("file_id")
        checkpoints = job.get("checkpoints", {}) or {}

        temp_media_path = None
        clean_audio_path = checkpoints.get("clean_audio_path")
        transcription_result = checkpoints.get("transcription_result")
        enriched_chunks = checkpoints.get("enriched_chunks")
        video_url = checkpoints.get("video_url", "")

        try:
            # -----------------------------------------------------------------
            # STAGE 1: VERIFYING_SOURCE (10%)
            # -----------------------------------------------------------------
            if self._is_cancelled(job_id): return
            self.db.update_job_stage(
                job_id,
                stage="VERIFYING_SOURCE",
                status="IN_PROGRESS",
                progress_percent=10,
                stage_message="Verifying lecture video source and permissions..."
            )

            gdm = GoogleDriveManager()
            if not file_id and media_url:
                file_id = gdm.extract_file_id(media_url)
            elif file_id:
                file_id = gdm.extract_file_id(file_id)

            if file_id:
                if not video_url:
                    video_url = f"https://drive.google.com/file/d/{file_id}/preview"
                    if gdm.is_configured():
                        try:
                            gdm.make_file_public_readable(file_id)
                        except Exception:
                            pass
            elif local_filepath and Path(local_filepath).exists():
                temp_media_path = Path(local_filepath)
                if not video_url:
                    video_url = f"/uploads/{temp_media_path.name}"
            elif media_url:
                video_url = media_url

            self.db.update_job_stage(
                job_id,
                stage="VERIFYING_SOURCE",
                progress_percent=20,
                stage_message="Source validated successfully.",
                checkpoint_data={"video_url": video_url, "file_id": file_id}
            )

            # -----------------------------------------------------------------
            # STAGE 2: AUDIO_EXTRACTION (35%)
            # -----------------------------------------------------------------
            if self._is_cancelled(job_id): return

            # Check if audio was already extracted in a prior run
            if clean_audio_path and Path(clean_audio_path).exists():
                # If existing audio is oversized (>50MB), compress it to 16kHz mono to prevent Deepgram 504 Gateway Timeout
                try:
                    old_fpath = Path(clean_audio_path)
                    if old_fpath.stat().st_size > 50 * 1024 * 1024:
                        logger.info(f"Existing audio is {old_fpath.stat().st_size / (1024*1024):.1f}MB (>50MB). Compressing to compact 16kHz mono...")
                        compact_path = extract_and_clean_audio(str(old_fpath))
                        if compact_path and Path(compact_path).exists() and compact_path != str(old_fpath):
                            try:
                                old_fpath.unlink()
                            except Exception:
                                pass
                            clean_audio_path = compact_path
                            self.db.update_job_stage(
                                job_id,
                                stage="AUDIO_EXTRACTION",
                                progress_percent=40,
                                stage_message="Audio compressed to compact 16kHz mono.",
                                checkpoint_data={"clean_audio_path": clean_audio_path}
                            )
                except Exception as comp_err:
                    logger.warning(f"Notice on compressing existing audio: {comp_err}")

            if not clean_audio_path or not Path(clean_audio_path).exists():
                self.db.update_job_stage(
                    job_id,
                    stage="AUDIO_EXTRACTION",
                    progress_percent=25,
                    stage_message="Extracting speech audio with FFmpeg (16kHz mono)..."
                )

                # Download from Drive if needed
                if file_id and not temp_media_path:
                    temp_media_path = Config.UPLOADS_DIR / f"temp_stream_{lesson_id}.tmp"
                    logger.info(f"Downloading Google Drive file {file_id} to {temp_media_path}...")
                    success = gdm.download_file(file_id, temp_media_path)
                    if not success or not temp_media_path.exists():
                        raise RuntimeError(f"Could not retrieve video from Google Drive (ID: {file_id}). Check permissions.")

                if not temp_media_path or not temp_media_path.exists():
                    raise RuntimeError("Source media file is missing or inaccessible.")

                # Run bounded FFmpeg audio extraction
                clean_audio_path = extract_and_clean_audio(str(temp_media_path))

                # Package into AES-128 Encrypted HLS stream if FFmpeg is available
                hls_packaged = False
                try:
                    hls_output_dir = Config.CHUNKS_DIR / "hls" / lesson_id
                    if not (hls_output_dir / "master.m3u8").exists() and HLSTranscoder.is_ffmpeg_available():
                        logger.info(f"[HLS Ingestion] Packaging {lesson_id} into AES-128 encrypted HLS segments...")
                        res = HLSTranscoder.package_video_to_encrypted_hls(
                            lesson_id=lesson_id,
                            input_file_path=temp_media_path,
                            output_hls_dir=hls_output_dir,
                            segment_duration=6
                        )
                        hls_packaged = bool(res and res.get("total_segments", 0) > 0)
                except Exception as hls_err:
                    logger.warning(f"[HLS Ingestion] Notice on HLS packaging: {hls_err}")

                # Immediately delete temporary video file to protect 1 GB RAM / tmpfs disk!
                if temp_media_path and temp_media_path.exists() and "temp_stream_" in temp_media_path.name:
                    try:
                        temp_media_path.unlink()
                        logger.info(f"Purged temporary media {temp_media_path} to conserve container memory.")
                    except Exception as e:
                        logger.warning(f"Notice on deleting temp video: {e}")

                self.db.update_job_stage(
                    job_id,
                    stage="AUDIO_EXTRACTION",
                    progress_percent=40,
                    stage_message="Audio extraction complete (32kbps mono).",
                    checkpoint_data={"clean_audio_path": clean_audio_path, "audio_extracted": True, "hls_enabled": hls_packaged}
                )

            # -----------------------------------------------------------------
            # STAGE 3: TRANSCRIPTION (60%)
            # -----------------------------------------------------------------
            if self._is_cancelled(job_id): return

            if not transcription_result or not transcription_result.get("utterances"):
                self.db.update_job_stage(
                    job_id,
                    stage="TRANSCRIPTION",
                    progress_percent=45,
                    stage_message="Transcribing dialogue with Deepgram Nova-2 (Diarization & Timestamps)..."
                )

                if not Config.DEEPGRAM_API_KEY:
                    raise RuntimeError("Deepgram API Key is not configured on the server.")

                transcriber = DeepgramTranscriber(Config.DEEPGRAM_API_KEY)

                def _on_transcription_progress(completed: int, total: int):
                    if total > 1:
                        pct = 45 + int((completed / total) * 15)
                        self.db.update_job_stage(
                            job_id,
                            stage="TRANSCRIPTION",
                            progress_percent=pct,
                            stage_message=f"Deepgram Nova-2: Transcribed section {completed}/{total} (Diarization & Timestamps)..."
                        )

                transcription_result = transcriber.transcribe_file(clean_audio_path, progress_callback=_on_transcription_progress)

                # Free the temporary clean audio file immediately after successful transcription!
                if clean_audio_path and Path(clean_audio_path).exists():
                    try:
                        Path(clean_audio_path).unlink()
                        logger.info(f"Purged temporary audio {clean_audio_path} after transcription.")
                    except Exception as e:
                        logger.warning(f"Notice on deleting clean audio: {e}")

                self.db.update_job_stage(
                    job_id,
                    stage="TRANSCRIPTION",
                    progress_percent=60,
                    stage_message=f"Deepgram transcription finished ({len(transcription_result.get('utterances', []))} utterances).",
                    checkpoint_data={
                        "transcription_result": transcription_result,
                        "duration_seconds": int(transcription_result.get("duration_seconds", 0))
                    }
                )

            raw_transcript = transcription_result["full_transcript"]
            utterances = transcription_result["utterances"]
            duration_seconds = int(transcription_result.get("duration_seconds", 0))

            if not raw_transcript.strip() or not utterances:
                raise RuntimeError("No spoken dialogue was detected in this lecture audio. Please upload an audible recording.")

            # -----------------------------------------------------------------
            # STAGE 4: SEMANTIC_PROCESSING (75%)
            # -----------------------------------------------------------------
            if self._is_cancelled(job_id): return

            if not enriched_chunks:
                self.db.update_job_stage(
                    job_id,
                    stage="SEMANTIC_PROCESSING",
                    progress_percent=65,
                    stage_message="Segmenting lecture into concept boundaries and generating HyDE queries with Gemini..."
                )

                if not Config.GEMINI_API_KEY:
                    raise RuntimeError("Gemini API Key is not configured on the server.")

                chunker = SemanticChunker(Config.GEMINI_API_KEY)
                enriched_chunks = chunker.chunk_and_enrich(
                    utterances=utterances,
                    course_title=title,
                    subject_name=title
                )

                self.db.update_job_stage(
                    job_id,
                    stage="SEMANTIC_PROCESSING",
                    progress_percent=78,
                    stage_message=f"Semantic chunking completed ({len(enriched_chunks)} concept chunks created).",
                    checkpoint_data={"enriched_chunks": enriched_chunks}
                )

            # -----------------------------------------------------------------
            # STAGE 5: EMBEDDING (88%)
            # -----------------------------------------------------------------
            if self._is_cancelled(job_id): return

            # Check if vectors are already generated
            needs_embedding = any("embedding" not in c or not c["embedding"] for c in enriched_chunks)
            if needs_embedding:
                self.db.update_job_stage(
                    job_id,
                    stage="EMBEDDING",
                    progress_percent=82,
                    stage_message="Generating 768-dim normalized embeddings in batches of 40..."
                )

                embedder = VectorEmbedder(Config.GEMINI_API_KEY)
                search_texts = [embedder.get_chunk_search_text(chunk) for chunk in enriched_chunks]
                embeddings = embedder.batch_get_embeddings(search_texts, dimension=768, batch_size=40)

                for idx, emb in enumerate(embeddings):
                    if idx < len(enriched_chunks):
                        enriched_chunks[idx]["embedding"] = emb

                self.db.update_job_stage(
                    job_id,
                    stage="EMBEDDING",
                    progress_percent=90,
                    stage_message=f"Generated {len(embeddings)} 768-dim vector embeddings.",
                    checkpoint_data={"enriched_chunks": enriched_chunks, "embeddings_completed": True}
                )

            # -----------------------------------------------------------------
            # STAGE 6: VECTOR_SYNC (95%)
            # -----------------------------------------------------------------
            if self._is_cancelled(job_id): return

            self.db.update_job_stage(
                job_id,
                stage="VECTOR_SYNC",
                progress_percent=92,
                stage_message="Persisting lecture metadata & vectors to Supabase and local store..."
            )

            # Save lesson metadata
            self.db.save_lesson(
                lesson_id=lesson_id,
                course_id=course_id,
                title=title,
                duration_seconds=duration_seconds,
                video_url=video_url,
                raw_transcript=raw_transcript,
                utterances=utterances
            )

            # Save chunks and vectors
            self.db.save_chunks(
                lesson_id=lesson_id,
                course_id=course_id,
                chunks=enriched_chunks
            )

            # Auto-synthesize initial MCQ assessment bank in background so student quizzes are instantly ready
            try:
                def _bg_generate_mcqs():
                    try:
                        from backend.assignment_engine import AssignmentEngine
                        engine = AssignmentEngine(self.db)
                        engine.generate_mcq_quiz(lesson_id, count=5)
                        logger.info(f"Auto-generated practice MCQ bank for new lecture {lesson_id}")
                    except Exception as mcq_err:
                        logger.warning(f"Background MCQ synthesis notice: {mcq_err}")
                threading.Thread(target=_bg_generate_mcqs, daemon=True).start()
            except Exception as e:
                logger.warning(f"Could not dispatch background MCQ generator: {e}")

            # -----------------------------------------------------------------
            # STAGE 7: COMPLETED (100%)
            # -----------------------------------------------------------------
            self.db.complete_job(
                job_id=job_id,
                lesson_id=lesson_id,
                duration_seconds=duration_seconds,
                total_chunks=len(enriched_chunks),
                stage_message=f"Lecture '{title}' indexed successfully with {len(enriched_chunks)} concept chunks."
            )
            logger.info(f"Job {job_id} for lecture '{title}' COMPLETED successfully in background!")

        except Exception as e:
            logger.exception(f"Job {job_id} failed during execution: {e}")
            error_msg = str(e)
            # Sanitize error message for UI display
            if "API key" in error_msg.lower():
                error_msg = "Provider API key configuration error."
            self.db.fail_job(job_id, error_message=error_msg)

        finally:
            # Defensive memory and tmpfs cleanup
            if temp_media_path and Path(temp_media_path).exists() and "temp_stream_" in str(temp_media_path):
                try:
                    Path(temp_media_path).unlink()
                except Exception:
                    pass
            if clean_audio_path and Path(clean_audio_path).exists() and "clean_16k" in str(clean_audio_path):
                try:
                    Path(clean_audio_path).unlink()
                except Exception:
                    pass

# Singleton instance
_job_manager_instance: Optional[IngestionJobManager] = None

def get_job_manager() -> IngestionJobManager:
    global _job_manager_instance
    if _job_manager_instance is None:
        _job_manager_instance = IngestionJobManager()
    return _job_manager_instance
