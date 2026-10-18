import os
import uuid
import shutil
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import Config, reload_config
from backend.audio_extractor import extract_and_clean_audio
from backend.deepgram_transcriber import DeepgramTranscriber
from backend.semantic_chunker import SemanticChunker
from backend.vector_embedder import VectorEmbedder
from backend.db_adapter import DBAdapter
from backend.rag_engine import RAGEngine
from backend.google_drive import GoogleDriveManager

app = FastAPI(title="ClimbUp Mentor Engine | Teacher Video RAG & Studio")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DBAdapter()
drive_mgr = GoogleDriveManager()

class ChatRequest(BaseModel):
    query: str
    lesson_id: str
    session_id: Optional[str] = "default-session"

class ConfigUpdateRequest(BaseModel):
    deepgram_key: Optional[str] = None
    gemini_key: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    drive_folder_id: Optional[str] = None

class DriveIngestRequest(BaseModel):
    file_id: str
    title: str
    course_name: Optional[str] = "Applied AI & GenAI with RAG Architectures"
    course_id: Optional[str] = "course-applied-ai-rag"

class CourseCreateRequest(BaseModel):
    title: str
    category: Optional[str] = "Computer Science"
    level: Optional[str] = "All Levels"
    description: Optional[str] = ""
    instructor_name: Optional[str] = "Course Instructor"
    thumbnail: Optional[str] = ""
    tagline: Optional[str] = ""

class StudentEnrollRequest(BaseModel):
    name: str
    email: str
    course_id: str

@app.get("/api/status")
def get_status():
    reload_config()
    gdm = GoogleDriveManager()
    return {
        "deepgram_configured": bool(Config.DEEPGRAM_API_KEY),
        "gemini_configured": bool(Config.GEMINI_API_KEY),
        "supabase_configured": bool(Config.SUPABASE_URL and Config.SUPABASE_KEY),
        "google_drive_configured": gdm.is_configured(),
        "google_drive_folder_id": Config.GOOGLE_DRIVE_FOLDER_ID,
        "total_lessons_indexed": len(db.list_lessons()),
        "total_chunks_indexed": len(db._read_local_store().get("chunks", []))
    }

@app.get("/api/courses")
def get_courses():
    reload_config()
    return db.list_courses()

@app.post("/api/courses")
def create_course(req: CourseCreateRequest):
    reload_config()
    if not req.title or not req.title.strip():
        raise HTTPException(status_code=400, detail="Course title is required")
    course = db.create_course(
        title=req.title.strip(),
        category=req.category or "Computer Science",
        level=req.level or "All Levels",
        description=req.description or "",
        instructor_name=req.instructor_name or "Course Instructor",
        thumbnail=req.thumbnail or "",
        tagline=req.tagline or ""
    )
    return {"status": "success", "message": f"Course '{req.title}' created successfully.", "course": course}

@app.delete("/api/courses/{course_id}")
def delete_course(course_id: str):
    reload_config()
    success = db.delete_course(course_id)
    return {"status": "success", "message": f"Course {course_id} deleted.", "deleted": success}

@app.delete("/api/resources/{resource_id}")
def delete_resource(resource_id: str):
    reload_config()
    store = db._read_local_store()
    if "resources" in store:
        store["resources"] = [r for r in store["resources"] if r.get("id") != resource_id]
        db._write_local_store(store)
    if db.supabase_url and db.supabase_key:
        try:
            requests.delete(f"{db.supabase_url}/rest/v1/course_resources?id=eq.{resource_id}", headers=db._get_headers(), timeout=6)
        except Exception as e:
            print(f"[Supabase] delete_resource notice: {e}")
    return {"status": "success", "message": "Resource deleted successfully."}

@app.delete("/api/lessons/{lesson_id}")
def delete_lesson(lesson_id: str):
    reload_config()
    store = db._read_local_store()
    if lesson_id in store.get("lessons", {}):
        del store["lessons"][lesson_id]
    store["chunks"] = [c for c in store.get("chunks", []) if c.get("lesson_id") != lesson_id]
    db._write_local_store(store)
    if db.supabase_url and db.supabase_key:
        try:
            requests.delete(f"{db.supabase_url}/rest/v1/course_lessons?id=eq.{lesson_id}", headers=db._get_headers(), timeout=6)
            requests.delete(f"{db.supabase_url}/rest/v1/transcript_chunks_vector?lesson_id=eq.{lesson_id}", headers=db._get_headers(), timeout=6)
        except Exception as e:
            print(f"[Supabase] delete_lesson notice: {e}")
    return {"status": "success", "message": "Lesson deleted successfully."}

@app.get("/api/students")
def list_students(course_id: Optional[str] = None):
    reload_config()
    return db.get_students(course_id)

@app.post("/api/students")
def enroll_student(req: StudentEnrollRequest):
    reload_config()
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Student name is required")
    if not req.email or not req.email.strip():
        raise HTTPException(status_code=400, detail="Student email is required")
    return db.add_student(req.name.strip(), req.email.strip(), req.course_id)

@app.delete("/api/students/{student_id}")
def delete_student(student_id: str):
    reload_config()
    success = db.delete_student(student_id)
    return {"status": "success", "deleted": success}

@app.get("/api/drive/files")
def list_drive_files():
    reload_config()
    gdm = GoogleDriveManager()
    if not gdm.is_configured():
        return {"configured": False, "files": [], "message": "Google Drive credentials not set"}
    
    files = gdm.list_files()
    return {
        "configured": True,
        "folder_id": Config.GOOGLE_DRIVE_FOLDER_ID,
        "total": len(files),
        "files": files
    }

@app.get("/api/courses/{course_id}/resources")
def get_course_resources(course_id: str):
    reload_config()
    return db.get_course_resources(course_id)

@app.post("/api/resources/upload")
async def upload_resource(
    file: UploadFile = File(...),
    course_id: str = Form("course-applied-ai-rag"),
    title: str = Form(...),
    file_type: str = Form("pdf"),
    description: Optional[str] = Form("")
):
    """
    Uploads official teacher lecture notes, assignments, or slides directly
    into Supabase Storage ('course_resources') and persists record into 'public.course_resources'.
    """
    reload_config()
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    
    detected_type = file_type
    if file.filename:
        ext = file.filename.split(".")[-1].lower()
        if ext in ["pdf", "zip", "doc", "docx", "ppt", "pptx", "txt", "ipynb"]:
            detected_type = ext

    result = db.upload_course_resource(
        course_id=course_id,
        title=title,
        file_bytes=file_bytes,
        filename=file.filename or "notes.pdf",
        file_type=detected_type,
        description=description or f"Official course material for {title}"
    )
    return {
        "status": "success",
        "message": f"Resource '{title}' uploaded to Supabase Storage & Database successfully.",
        "resource": result
    }


@app.post("/api/update-config")
def update_config(req: ConfigUpdateRequest):
    env_lines = []
    if Config.ENV_PATH.exists():
        with open(Config.ENV_PATH, "r", encoding="utf-8") as f:
            env_lines = f.readlines()

    keys_to_update = {
        "DEEPGRAM_API_KEY": req.deepgram_key,
        "GEMINI_API_KEY": req.gemini_key,
        "SUPABASE_URL": req.supabase_url,
        "SUPABASE_SERVICE_ROLE_KEY": req.supabase_key,
        "GOOGLE_DRIVE_FOLDER_ID": req.drive_folder_id
    }

    updated_keys = set()
    new_lines = []
    for line in env_lines:
        matched = False
        for k, v in keys_to_update.items():
            if v is not None and line.startswith(f"{k}="):
                new_lines.append(f"{k}={v}\n")
                updated_keys.add(k)
                matched = True
                break
        if not matched:
            new_lines.append(line)

    for k, v in keys_to_update.items():
        if v is not None and k not in updated_keys:
            new_lines.append(f"{k}={v}\n")

    with open(Config.ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    reload_config()
    return {"status": "success", "message": "Configuration updated successfully."}

@app.get("/api/lessons")
def list_lessons():
    return db.list_lessons()

@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: str):
    lesson = db.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    chunks = db.get_lesson_chunks(lesson_id)
    return {
        **lesson,
        "chunks": chunks
    }

@app.post("/api/process-video")
async def process_video(
    file: Optional[UploadFile] = File(None),
    title: str = Form("Applied AI: Vector RAG Architectures"),
    course_name: str = Form("Applied AI & GenAI with RAG Architectures"),
    course_id: str = Form("course-applied-ai-rag"),
    media_url: Optional[str] = Form(None)
):
    """
    Stateless RAG Ingestion Pipeline:
    1. Direct upload of video file to Google Drive (Cloud Run server is NOT used as video storage)
    2. Temporary audio extraction via FFmpeg
    3. Immediate deletion of local video file to free container memory/disk
    4. Deepgram Nova-2 transcription with diarization & word timestamps
    5. Immediate deletion of local audio file
    6. Gemini 2.5 Flash concept chunking & reverse-question enrichment
    7. 768-dim vector embeddings persisted into Supabase (course_lessons & transcript_chunks_vector)
    """
    reload_config()
    if not Config.DEEPGRAM_API_KEY:
        raise HTTPException(status_code=400, detail="Deepgram API key is not configured.")
    if not Config.GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="Gemini API key is not configured.")

    lesson_id = f"lesson_{uuid.uuid4().hex[:8]}"
    saved_media_path = None
    clean_audio_path = None
    video_url = ""
    drive_file_id = None

    try:
        if file and file.filename:
            file_ext = Path(file.filename).suffix or ".mp4"
            temp_name = f"temp_{lesson_id}{file_ext}"
            saved_media_path = Config.UPLOADS_DIR / temp_name
            
            with open(saved_media_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # 1. Direct Upload to Google Drive (Offload heavy video storage from Cloud Run!)
            gdm = GoogleDriveManager()
            if gdm.is_configured():
                print(f"[Upload] Uploading {file.filename} directly to Google Drive...")
                mime = file.content_type or "video/mp4"
                drive_res = gdm.upload_file(saved_media_path, filename=file.filename, mime_type=mime)
                if drive_res:
                    drive_file_id = drive_res.get("id")
                    video_url = drive_res.get("stream_url") or drive_res.get("webViewLink")
                    print(f"[Upload] Successfully uploaded to Google Drive. ID: {drive_file_id}")
            
            if not video_url:
                # Fallback if Drive is unconfigured or failed: serve locally
                permanent_media_path = Config.UPLOADS_DIR / f"{lesson_id}{file_ext}"
                shutil.copy(saved_media_path, permanent_media_path)
                video_url = f"/uploads/{permanent_media_path.name}"

            # 2. Extract 16kHz audio for RAG
            clean_audio_path = extract_and_clean_audio(str(saved_media_path))
            
            # 3. Clean up the temporary local video file if uploaded to Drive
            if drive_file_id and saved_media_path.exists():
                try:
                    saved_media_path.unlink()
                except Exception:
                    pass

            # 4. Transcribe audio with Deepgram Nova-2
            transcriber = DeepgramTranscriber(Config.DEEPGRAM_API_KEY)
            transcription_result = transcriber.transcribe_file(clean_audio_path)

            # 5. Clean up temporary audio file immediately
            if clean_audio_path and Path(clean_audio_path).exists():
                try:
                    Path(clean_audio_path).unlink()
                except Exception:
                    pass

        elif media_url:
            clean_url = media_url.strip()
            gdm = GoogleDriveManager()
            drive_fid = gdm.extract_file_id(clean_url)

            # Check if input is a Google Drive URL or File ID
            if drive_fid and ("drive.google.com" in clean_url or len(clean_url) < 60):
                print(f"[Ingest] Google Drive link detected. File ID: {drive_fid}")
                if gdm.is_configured():
                    gdm.make_file_public_readable(drive_fid)

                video_url = f"https://drive.google.com/file/d/{drive_fid}/preview"
                stream_url = f"https://drive.google.com/uc?export=download&id={drive_fid}"
                
                transcriber = DeepgramTranscriber(Config.DEEPGRAM_API_KEY)
                try:
                    # Strategy 1: Direct Deepgram URL Stream (0 bytes downloaded on our server!)
                    print("[Ingest] Sending direct stream link to Deepgram Nova-2...")
                    transcription_result = transcriber.transcribe_url(stream_url)
                    print("[Ingest] Deepgram successfully transcribed directly from Google Drive stream!")
                except Exception as stream_err:
                    print(f"[Ingest] Direct URL stream notice: {stream_err}. Falling back to lightweight audio extraction...")
                    temp_media = Config.UPLOADS_DIR / f"temp_stream_{lesson_id}.tmp"
                    gdm.download_file(drive_fid, temp_media)
                    clean_audio = extract_and_clean_audio(str(temp_media))
                    if temp_media.exists():
                        try:
                            temp_media.unlink()
                        except Exception:
                            pass
                    transcription_result = transcriber.transcribe_file(clean_audio)
                    if clean_audio and Path(clean_audio).exists():
                        try:
                            Path(clean_audio).unlink()
                        except Exception:
                            pass
            else:
                transcriber = DeepgramTranscriber(Config.DEEPGRAM_API_KEY)
                transcription_result = transcriber.transcribe_url(clean_url)
                video_url = clean_url
        else:
            raise HTTPException(status_code=400, detail="Please upload a video file or provide a URL.")

        raw_transcript = transcription_result["full_transcript"]
        utterances = transcription_result["utterances"]
        duration_seconds = int(transcription_result.get("duration_seconds", 0))

        # 6. Semantic Chunking & Enrichment
        chunker = SemanticChunker(Config.GEMINI_API_KEY)
        enriched_chunks = chunker.chunk_and_enrich(
            utterances=utterances,
            course_title=course_name,
            subject_name=title
        )

        # 7. 768-dim Vector Embeddings
        embedder = VectorEmbedder(Config.GEMINI_API_KEY)
        for chunk in enriched_chunks:
            search_text = embedder.get_chunk_search_text(chunk)
            chunk["embedding"] = embedder.get_embedding(search_text, dimension=768)

        # 8. Persist to Supabase and Local Store
        db.save_lesson(
            lesson_id=lesson_id,
            course_id=course_id,
            title=title,
            duration_seconds=duration_seconds,
            video_url=video_url,
            raw_transcript=raw_transcript,
            utterances=utterances
        )
        db.save_chunks(lesson_id=lesson_id, course_id=course_id, chunks=enriched_chunks)

        return {
            "status": "success",
            "lesson_id": lesson_id,
            "title": title,
            "duration_seconds": duration_seconds,
            "video_url": video_url,
            "storage_location": "Google Drive" if drive_file_id else "Server",
            "total_utterances": len(utterances),
            "total_chunks_indexed": len(enriched_chunks),
            "preview_chunks": [
                {
                    "topic": c["topic_name"],
                    "timestamp": c["timestamp_label"],
                    "speaker": c["speaker_label"],
                    "sample_text": c["cleaned_text"][:150]
                }
                for c in enriched_chunks[:5]
            ]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/api/drive/ingest")
async def ingest_from_drive(req: DriveIngestRequest):
    """
    Directly processes a video file residing in Google Drive:
    Streams the media into memory/temp, extracts audio, transcribes, chunks,
    embeds into Supabase, and cleans disk.
    """
    reload_config()
    gdm = GoogleDriveManager()
    if not gdm.is_configured():
        raise HTTPException(status_code=400, detail="Google Drive is not configured.")

    lesson_id = f"lesson_drive_{uuid.uuid4().hex[:8]}"
    temp_video = Config.UPLOADS_DIR / f"drive_{req.file_id}.tmp"

    try:
        # 1. Stream file from Google Drive
        meta = gdm.get_file_metadata(req.file_id)
        file_name = meta.get("name") if meta else req.title
        success = gdm.download_file(req.file_id, temp_video)
        if not success:
            raise HTTPException(status_code=404, detail="Could not retrieve file from Google Drive.")

        # 2. Extract 16kHz audio
        clean_audio_path = extract_and_clean_audio(str(temp_video))

        # 3. Immediately delete temp video from server
        if temp_video.exists():
            try:
                temp_video.unlink()
            except Exception:
                pass

        # 4. Transcribe with Deepgram
        transcriber = DeepgramTranscriber(Config.DEEPGRAM_API_KEY)
        transcription_result = transcriber.transcribe_file(clean_audio_path)

        # 5. Delete temp audio
        if clean_audio_path and Path(clean_audio_path).exists():
            try:
                Path(clean_audio_path).unlink()
            except Exception:
                pass

        raw_transcript = transcription_result["full_transcript"]
        utterances = transcription_result["utterances"]
        duration_seconds = int(transcription_result.get("duration_seconds", 0))

        # 6. Semantic Chunking
        chunker = SemanticChunker(Config.GEMINI_API_KEY)
        enriched_chunks = chunker.chunk_and_enrich(
            utterances=utterances,
            course_title=req.course_name or "Applied AI",
            subject_name=req.title
        )

        # 7. Vector Embeddings
        embedder = VectorEmbedder(Config.GEMINI_API_KEY)
        for chunk in enriched_chunks:
            search_text = embedder.get_chunk_search_text(chunk)
            chunk["embedding"] = embedder.get_embedding(search_text, dimension=768)

        # Google Drive stream preview URL
        drive_stream_url = f"https://drive.google.com/file/d/{req.file_id}/preview"

        # 8. Save to Supabase
        db.save_lesson(
            lesson_id=lesson_id,
            course_id=req.course_id or "course-applied-ai-rag",
            title=req.title or file_name,
            duration_seconds=duration_seconds,
            video_url=drive_stream_url,
            raw_transcript=raw_transcript,
            utterances=utterances
        )
        db.save_chunks(lesson_id=lesson_id, course_id=req.course_id or "course-applied-ai-rag", chunks=enriched_chunks)

        return {
            "status": "success",
            "lesson_id": lesson_id,
            "title": req.title or file_name,
            "duration_seconds": duration_seconds,
            "video_url": drive_stream_url,
            "storage": "Google Drive Folder",
            "total_chunks_indexed": len(enriched_chunks)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Google Drive ingestion failed: {str(e)}")

@app.post("/api/chat")
def chat_query(req: ChatRequest):
    reload_config()
    if not Config.GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="Gemini API Key is not configured.")

    try:
        engine = RAGEngine(Config.GEMINI_API_KEY, db)
        response = engine.answer_query(
            query=req.query,
            lesson_id=req.lesson_id,
            session_id=req.session_id or "default-session"
        )
        return response
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"RAG Error: {str(e)}")

@app.post("/api/load-sample")
def load_sample_lecture():
    """
    Loads realistic university Operating Systems lecture with timestamps,
    teacher dialogue, student questions, and embeddings.
    """
    reload_config()
    lesson_id = "sample_os_scheduling"
    course_id = "course-applied-ai-rag"
    title = "Operating Systems: CPU Scheduling & Round Robin Algorithm"

    sample_utterances = [
        {
            "speaker_id": 0,
            "speaker_label": "Teacher",
            "start_seconds": 0.0,
            "end_seconds": 45.0,
            "timestamp_label": "00:00 - 00:45",
            "text": "Good morning everyone. Today we are diving into one of the most critical topics in Operating Systems: CPU Scheduling. The CPU is the brain of the computer, and when multiple processes want to run simultaneously, the OS scheduler must decide which process gets CPU time and for how long."
        },
        {
            "speaker_id": 0,
            "speaker_label": "Teacher",
            "start_seconds": 46.0,
            "end_seconds": 125.0,
            "timestamp_label": "00:46 - 02:05",
            "text": "First, let's understand the difference between Preemptive and Non-Preemptive scheduling. In non-preemptive scheduling, once a process gets the CPU, it keeps running until it finishes its CPU burst or switches to an I/O wait state. FCFS (First Come First Serve) is a classic example. But in preemptive scheduling, the operating system can interrupt a currently running process to give the CPU to another higher-priority process."
        },
        {
            "speaker_id": 1,
            "speaker_label": "Student 1",
            "start_seconds": 126.0,
            "end_seconds": 145.0,
            "timestamp_label": "02:06 - 02:25",
            "text": "Professor, does preemptive scheduling cause overhead because of context switching?"
        },
        {
            "speaker_id": 0,
            "speaker_label": "Teacher",
            "start_seconds": 146.0,
            "end_seconds": 260.0,
            "timestamp_label": "02:26 - 04:20",
            "text": "Excellent question. Yes, absolutely. Context switching requires saving the CPU registers, program counter, and stack pointer of the old process and loading the state of the new process. This takes memory bus cycles and CPU time, so too frequent preemption degrades overall throughput."
        },
        {
            "speaker_id": 0,
            "speaker_label": "Teacher",
            "start_seconds": 261.0,
            "end_seconds": 450.0,
            "timestamp_label": "04:21 - 07:30",
            "text": "Now let us focus on Round Robin Scheduling, denoted as RR. Round Robin is designed specifically for time-sharing systems. The core concept is the Time Quantum or Time Slice, typically ranging from 10 to 100 milliseconds. The ready queue is treated as a circular FIFO queue. The CPU scheduler allocates the CPU to each process for an interval of up to 1 time quantum."
        },
        {
            "speaker_id": 0,
            "speaker_label": "Teacher",
            "start_seconds": 451.0,
            "end_seconds": 630.0,
            "timestamp_label": "07:31 - 10:30",
            "text": "What happens if the time quantum expires? If process P1 has a burst time of 24ms and quantum is 4ms, after 4ms a timer interrupt occurs. The OS moves P1 to the tail of the ready queue and dispatches P2. If quantum q is extremely large, Round Robin degrades into First-Come First-Served (FCFS). Conversely, if quantum q is extremely small, say 1 microsecond, context switch overhead dominates and system performance collapses."
        },
        {
            "speaker_id": 0,
            "speaker_label": "Teacher",
            "start_seconds": 631.0,
            "end_seconds": 810.0,
            "timestamp_label": "10:31 - 13:30",
            "text": "Rule of thumb for exam questions: You should set the time quantum such that roughly 80 percent of the CPU bursts are shorter than the time quantum. This minimizes context switching while providing excellent response time for interactive processes. Let's calculate average turnaround time: Turnaround time equals Completion time minus Arrival time."
        }
    ]

    embedder = VectorEmbedder(Config.GEMINI_API_KEY) if Config.GEMINI_API_KEY else None

    enriched_chunks = [
        {
            "chunk_index": 1,
            "start_seconds": 0.0,
            "end_seconds": 125.0,
            "timestamp_label": "00:00 - 02:05",
            "speaker_label": "Teacher",
            "topic_name": "Introduction to CPU Scheduling & Preemption",
            "cleaned_text": "CPU Scheduling determines which process gets CPU time. Preemptive scheduling allows the OS to interrupt a running process (e.g., Round Robin, SRTF), whereas Non-preemptive scheduling holds the CPU until the process terminates or yields for I/O (e.g., FCFS).",
            "context_header": "[Computer Science > OS > CPU Scheduling Concepts]",
            "chunk_text": "[Computer Science > OS > CPU Scheduling Concepts]\nPreemptive vs Non-Preemptive scheduling. In non-preemptive, process keeps CPU until termination. In preemptive, OS can interrupt process.",
            "key_concepts": ["CPU Scheduling", "Preemptive", "Non-Preemptive", "FCFS"],
            "hypothetical_questions": [
                "What is the difference between preemptive and non-preemptive scheduling?",
                "What is FCFS scheduling?",
                "Why does the OS need CPU scheduling?"
            ]
        },
        {
            "chunk_index": 2,
            "start_seconds": 126.0,
            "end_seconds": 260.0,
            "timestamp_label": "02:06 - 04:20",
            "speaker_label": "Teacher",
            "topic_name": "Context Switching Overhead in Preemptive Systems",
            "cleaned_text": "Context switching requires saving the CPU registers, program counter, and stack pointer of the current process and restoring the state of the new process. Excessive context switches reduce CPU throughput.",
            "context_header": "[Computer Science > OS > Context Switching]",
            "chunk_text": "[Computer Science > OS > Context Switching]\nContext switching overhead: saving registers and program counter takes CPU time and bus cycles.",
            "key_concepts": ["Context Switch", "Overhead", "Program Counter", "Registers", "Throughput"],
            "hypothetical_questions": [
                "What overhead is associated with preemptive scheduling?",
                "What happens during a context switch?",
                "Does context switching reduce CPU performance?"
            ]
        },
        {
            "chunk_index": 3,
            "start_seconds": 261.0,
            "end_seconds": 630.0,
            "timestamp_label": "04:21 - 10:30",
            "speaker_label": "Teacher",
            "topic_name": "Round Robin (RR) Algorithm & Time Quantum Effects",
            "cleaned_text": "Round Robin uses a fixed time quantum (10-100ms) with a circular FIFO ready queue. If a process does not complete before quantum expires, a timer interrupt occurs and it moves to the tail of the queue. If quantum is too large, RR behaves like FCFS. If too small, context switch overhead dominates.",
            "context_header": "[Computer Science > OS > Round Robin Algorithm]",
            "chunk_text": "[Computer Science > OS > Round Robin Algorithm]\nRound Robin algorithm and Time Quantum. If time quantum expires, timer interrupt moves process to tail. Large quantum becomes FCFS; small quantum causes high context switch overhead.",
            "key_concepts": ["Round Robin", "Time Quantum", "Time Slice", "Circular Queue", "Timer Interrupt"],
            "hypothetical_questions": [
                "What is Round Robin scheduling?",
                "What happens if time quantum is too large in Round Robin?",
                "What happens if time quantum is too small?",
                "What is a time quantum?"
            ]
        },
        {
            "chunk_index": 4,
            "start_seconds": 631.0,
            "end_seconds": 810.0,
            "timestamp_label": "10:31 - 13:30",
            "speaker_label": "Teacher",
            "topic_name": "Optimal Time Quantum Rule of Thumb & Turnaround Time",
            "cleaned_text": "Exam rule of thumb: 80 percent of CPU bursts should be shorter than the time quantum. Turnaround Time = Completion Time - Arrival Time. Minimizes context switches while maintaining interactive responsiveness.",
            "context_header": "[Computer Science > OS > Turnaround Time & 80% Rule]",
            "chunk_text": "[Computer Science > OS > Turnaround Time & 80% Rule]\n80% rule: 80% of CPU bursts should be shorter than time quantum. Turnaround Time = Completion Time - Arrival Time.",
            "key_concepts": ["80% Rule of Thumb", "Turnaround Time", "Arrival Time", "Completion Time"],
            "hypothetical_questions": [
                "What is the 80% rule of thumb for choosing time quantum?",
                "How is turnaround time calculated in CPU scheduling?",
                "How to balance response time and context switch overhead?"
            ]
        }
    ]

    if embedder:
        for c in enriched_chunks:
            search_text = embedder.get_chunk_search_text(c)
            c["embedding"] = embedder.get_embedding(search_text, dimension=768)
    else:
        for c in enriched_chunks:
            c["embedding"] = [0.0] * 768

    db.save_lesson(
        lesson_id=lesson_id,
        course_id=course_id,
        title=title,
        duration_seconds=810,
        video_url="/uploads/berkeley_cs61c.mp4",
        raw_transcript=" ".join([u["text"] for u in sample_utterances]),
        utterances=sample_utterances
    )
    db.save_chunks(lesson_id=lesson_id, course_id=course_id, chunks=enriched_chunks)

    return {
        "status": "success",
        "message": "Sample university lecture loaded with 4 concept-enriched RAG chunks and full timestamp index.",
        "lesson_id": lesson_id,
        "title": title
    }

# Mount uploads directory for fallback video streaming
uploads_path = Config.UPLOADS_DIR
uploads_path.mkdir(exist_ok=True, parents=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

# Mount frontend
frontend_dir = Config.BASE_DIR / "frontend"
frontend_dir.mkdir(exist_ok=True, parents=True)
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
