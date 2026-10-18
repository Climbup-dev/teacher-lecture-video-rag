import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, List
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

app = FastAPI(title="Teacher Lecture Video RAG & Chatbot Engine")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DBAdapter()

class ChatRequest(BaseModel):
    query: str
    lesson_id: str
    session_id: Optional[str] = "default-session"

class ConfigUpdateRequest(BaseModel):
    deepgram_key: Optional[str] = None
    gemini_key: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

@app.get("/api/status")
def get_status():
    reload_config()
    return {
        "deepgram_configured": bool(Config.DEEPGRAM_API_KEY),
        "gemini_configured": bool(Config.GEMINI_API_KEY),
        "supabase_configured": bool(Config.SUPABASE_URL and Config.SUPABASE_KEY),
        "total_lessons_indexed": len(db.list_lessons()),
        "total_chunks_indexed": len(db._read_local_store().get("chunks", []))
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
        "SUPABASE_KEY": req.supabase_key
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
    title: str = Form("Operating Systems: CPU Scheduling"),
    course_name: str = Form("Computer Science - 4th Semester"),
    media_url: Optional[str] = Form(None)
):
    """
    Complete 4-Stage Ingestion Pipeline:
    1. Extract 16kHz mono audio from video (FFmpeg)
    2. Deepgram Nova-2 speech-to-text with diarization & word timestamps
    3. Gemini 2.5 Flash concept chunking & reverse-question enrichment
    4. 768-dim vector embedding & persistence into transcript_chunks_vector
    """
    reload_config()
    if not Config.DEEPGRAM_API_KEY:
        raise HTTPException(status_code=400, detail="Deepgram API key is not configured.")
    if not Config.GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="Gemini API key is not configured.")

    lesson_id = f"lesson_{uuid.uuid4().hex[:8]}"
    course_id = "cs-os-401"
    saved_media_path = None
    clean_audio_path = None

    try:
        # Step 1: Ingestion
        if file and file.filename:
            file_ext = Path(file.filename).suffix
            saved_media_path = Config.UPLOADS_DIR / f"{lesson_id}{file_ext}"
            with open(saved_media_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Audio extraction
            clean_audio_path = extract_and_clean_audio(str(saved_media_path))
            transcriber = DeepgramTranscriber(Config.DEEPGRAM_API_KEY)
            transcription_result = transcriber.transcribe_file(clean_audio_path)
            video_url = f"/uploads/{saved_media_path.name}"
        elif media_url:
            transcriber = DeepgramTranscriber(Config.DEEPGRAM_API_KEY)
            transcription_result = transcriber.transcribe_url(media_url)
            video_url = media_url
        else:
            raise HTTPException(status_code=400, detail="Please upload a video/audio file or provide a media URL.")

        raw_transcript = transcription_result["full_transcript"]
        utterances = transcription_result["utterances"]
        duration_seconds = int(transcription_result.get("duration_seconds", 0))

        # Step 2: Semantic Chunking & Enrichment
        chunker = SemanticChunker(Config.GEMINI_API_KEY)
        enriched_chunks = chunker.chunk_and_enrich(
            utterances=utterances,
            course_title=course_name,
            subject_name=title
        )

        # Step 3: Vector Embeddings
        embedder = VectorEmbedder(Config.GEMINI_API_KEY)
        for chunk in enriched_chunks:
            search_text = embedder.get_chunk_search_text(chunk)
            chunk["embedding"] = embedder.get_embedding(search_text, dimension=768)

        # Step 4: Persist in Database
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
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/api/chat")
def chat_query(req: ChatRequest):
    reload_config()
    if not Config.GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="Gemini API Key is not configured.")

    engine = RAGEngine(Config.GEMINI_API_KEY, db)
    response = engine.answer_query(
        query=req.query,
        lesson_id=req.lesson_id,
        session_id=req.session_id or "default-session"
    )
    return response

@app.post("/api/load-sample")
def load_sample_lecture():
    """
    Loads a comprehensive, realistic university Operating Systems lecture
    with timestamps, teacher dialogue, student questions, and embeddings
    so the user can immediately test the RAG chatbot & video player.
    """
    reload_config()
    lesson_id = "sample_os_scheduling"
    course_id = "cs-os-401"
    title = "Operating Systems: CPU Scheduling & Round Robin Algorithm"

    # Pre-crafted realistic lecture utterances
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
    chunker = SemanticChunker(Config.GEMINI_API_KEY) if Config.GEMINI_API_KEY else None

    # Process into chunks
    if chunker:
        enriched_chunks = chunker.chunk_and_enrich(
            utterances=sample_utterances,
            course_title="Computer Science - OS",
            subject_name=title
        )
    else:
        # Fallback pre-structured chunks
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

    # Generate real embeddings using verified Gemini key
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

# Mount uploads directory for video streaming
uploads_path = Config.UPLOADS_DIR
uploads_path.mkdir(exist_ok=True, parents=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

# Mount frontend
frontend_dir = Config.BASE_DIR / "frontend"
frontend_dir.mkdir(exist_ok=True, parents=True)
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
