import os
import sys
import uuid
import shutil
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure Windows console / terminal handles emojis and unicode without charmap crashes
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import time
import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Response, Header, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse, JSONResponse, FileResponse
from pydantic import BaseModel

from backend.config import Config, reload_config
from backend.audio_extractor import extract_and_clean_audio
from backend.deepgram_transcriber import DeepgramTranscriber
from backend.semantic_chunker import SemanticChunker
from backend.vector_embedder import VectorEmbedder
from backend.db_adapter import DBAdapter
from backend.rag_engine import RAGEngine
from backend.google_drive import GoogleDriveManager
from backend.job_manager import get_job_manager
from backend.security import (
    detect_download_attempt,
    get_client_ip,
    generate_signed_stream_token,
    verify_signed_stream_token,
    check_rate_limit,
    verify_admin_or_instructor_auth
)

# Configure structured production logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] [Req:%(request_id)s] %(message)s"
    if "%(request_id)s" in logging._defaultFormatter._fmt else
    "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("climbup.backend")

app = FastAPI(
    title="ClimbUp Mentor Engine | Teacher Video RAG & Studio",
    version="2.0.0",
    docs_url=None if Config.ENVIRONMENT == "production" else "/docs",
    redoc_url=None if Config.ENVIRONMENT == "production" else "/redoc",
)

# 1. Security Headers & Request Correlation Middleware
@app.middleware("http")
async def add_security_headers_and_tracing(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    request.state.request_id = req_id
    start_time = time.time()
    
    response: Response = await call_next(request)
    
    latency = time.time() - start_time
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Response-Time"] = f"{latency:.4f}s"
    
    # Do not log sensitive health check polling spam unless error
    if request.url.path not in ("/health", "/healthz") or response.status_code >= 400:
        logger.info(f"{request.method} {request.url.path} - {response.status_code} ({latency:.3f}s) [id:{req_id}]")
        
    return response

# 2. Hardened CORS Configuration
cors_origins = Config.CORS_ORIGINS
if "*" in cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Range", "Accept-Ranges", "X-Request-ID", "X-Response-Time"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Range", "Accept-Ranges", "X-Request-ID", "X-Response-Time"],
    )

# 3. Health & Liveness Endpoints for Cloud Run, Docker & Load Balancers
@app.get("/health")
@app.get("/healthz")
def health_check():
    return {
        "status": "healthy",
        "environment": Config.ENVIRONMENT,
        "timestamp": int(time.time()),
        "service": "climbup-mentor-rag"
    }

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
    google_credentials_json: Optional[str] = None

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
def create_course(
    req: CourseCreateRequest,
    authorization: Optional[str] = Header(None),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    verify_admin_or_instructor_auth(authorization, x_admin_key)
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
def delete_course(
    course_id: str,
    authorization: Optional[str] = Header(None),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    verify_admin_or_instructor_auth(authorization, x_admin_key)
    reload_config()
    success = db.delete_course(course_id)
    return {"status": "success", "message": f"Course {course_id} deleted.", "deleted": success}

@app.delete("/api/resources/{resource_id}")
def delete_resource(
    resource_id: str,
    authorization: Optional[str] = Header(None),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    verify_admin_or_instructor_auth(authorization, x_admin_key)
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
def delete_lesson(
    lesson_id: str,
    authorization: Optional[str] = Header(None),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    verify_admin_or_instructor_auth(authorization, x_admin_key)
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
    
    # 1. Enforce max resource payload size check
    max_bytes = Config.MAX_RESOURCE_SIZE_MB * 1024 * 1024
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file exceeds maximum permitted size of {Config.MAX_RESOURCE_SIZE_MB}MB."
        )
    
    # 2. Sanitize filename against path traversal
    safe_filename = Path(file.filename or "notes.pdf").name
    detected_type = file_type.lower().strip()
    if "." in safe_filename:
        ext = safe_filename.rsplit(".", 1)[-1].lower()
        if ext in ["pdf", "zip", "doc", "docx", "ppt", "pptx", "txt", "ipynb"]:
            detected_type = ext

    result = db.upload_course_resource(
        course_id=course_id,
        title=title.strip(),
        file_bytes=file_bytes,
        filename=safe_filename,
        file_type=detected_type,
        description=description or f"Official course material for {title}"
    )
    return {
        "status": "success",
        "message": f"Resource '{title}' uploaded to Supabase Storage & Database successfully.",
        "resource": result
    }


@app.post("/api/update-config")
def update_config(
    req: ConfigUpdateRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    authorization: Optional[str] = Header(None)
):
    """
    Protected configuration endpoint.
    Guarded by Config.ADMIN_API_KEY and disabled when READONLY_CONFIG is enabled.
    """
    if Config.READONLY_CONFIG:
        raise HTTPException(
            status_code=403,
            detail="Configuration updates are disabled in this environment (READONLY_CONFIG=true)."
        )

    # Enforce strict admin verification
    verify_admin_or_instructor_auth(authorization, x_admin_key)

    env_lines = []
    if Config.ENV_PATH.exists():
        with open(Config.ENV_PATH, "r", encoding="utf-8") as f:
            env_lines = f.readlines()

    keys_to_update = {
        "DEEPGRAM_API_KEY": req.deepgram_key,
        "GEMINI_API_KEY": req.gemini_key,
        "SUPABASE_URL": req.supabase_url,
        "SUPABASE_SERVICE_ROLE_KEY": req.supabase_key,
        "GOOGLE_DRIVE_FOLDER_ID": req.drive_folder_id,
        "GOOGLE_CREDENTIALS_JSON": req.google_credentials_json
    }

    updated_keys = set()
    new_lines = []
    for line in env_lines:
        matched = False
        for k, v in keys_to_update.items():
            if v is not None and line.startswith(f"{k}="):
                # Clean newline injection
                clean_v = str(v).replace("\r", "").replace("\n", "")
                new_lines.append(f"{k}={clean_v}\n")
                updated_keys.add(k)
                matched = True
                break
        if not matched:
            new_lines.append(line)

    for k, v in keys_to_update.items():
        if v is not None and k not in updated_keys:
            clean_v = str(v).replace("\r", "").replace("\n", "")
            new_lines.append(f"{k}={clean_v}\n")

    with open(Config.ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    reload_config()
    return {"status": "success", "message": "Configuration updated successfully."}

@app.get("/api/lessons")
def list_lessons():
    raw_lessons = db.list_lessons()
    sanitized = []
    for l in raw_lessons:
        item = dict(l)
        lid = item.get("id") or item.get("lesson_id")
        if lid:
            item["video_url"] = f"/api/lessons/{lid}/stream"
        sanitized.append(item)
    return sanitized

@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: str):
    lesson = db.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    chunks = db.get_lesson_chunks(lesson_id)
    sanitized = dict(lesson)
    sanitized["video_url"] = f"/api/lessons/{lesson_id}/stream"
    return {
        **sanitized,
        "chunks": chunks
    }


def verify_supabase_user_and_enrollment(
    authorization_header: Optional[str],
    token_param: Optional[str],
    course_id: str
) -> Dict[str, Any]:
    """
    Verifies Supabase JWT token authenticity and checks that the student is enrolled in course_id.
    Returns 401 if unauthenticated, 403 if not enrolled.
    """
    token = None
    if authorization_header and authorization_header.startswith("Bearer "):
        token = authorization_header.split(" ", 1)[1].strip()
    elif token_param:
        token = token_param.strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: No bearer token or token query parameter provided."
        )

    # 1. Verify token authenticity with Supabase Auth
    user_url = f"{Config.SUPABASE_URL}/auth/v1/user"
    auth_headers = {
        "apikey": Config.SUPABASE_KEY,
        "Authorization": f"Bearer {token}"
    }
    try:
        user_res = requests.get(user_url, headers=auth_headers, timeout=6)
        if not user_res.ok:
            raise HTTPException(
                status_code=401,
                detail="Invalid, expired, or revoked student session token."
            )
        user_data = user_res.json()
        user_id = user_data.get("id")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth Error] Supabase user check exception: {e}")
        raise HTTPException(status_code=401, detail="Authentication verification failed.")

    # 2. Check student course enrollment
    service_headers = {
        "apikey": Config.SUPABASE_KEY,
        "Authorization": f"Bearer {Config.SUPABASE_KEY}"
    }
    is_enrolled = False
    try:
        enroll_url = f"{Config.SUPABASE_URL}/rest/v1/course_enrollments?user_id=eq.{user_id}&course_id=eq.{course_id}&select=id"
        enroll_res = requests.get(enroll_url, headers=service_headers, timeout=6)
        is_enrolled = enroll_res.ok and len(enroll_res.json()) > 0
    except Exception as e:
        print(f"[Auth Error] Enrollment check exception: {e}")

    if not is_enrolled:
        # Check if user is the course instructor/creator
        try:
            course_url = f"{Config.SUPABASE_URL}/rest/v1/courses?id=eq.{course_id}&select=instructor_id,instructor_name"
            c_res = requests.get(course_url, headers=service_headers, timeout=6)
            if c_res.ok and c_res.json():
                c_data = c_res.json()[0]
                if c_data.get("instructor_id") == user_id:
                    is_enrolled = True
        except Exception:
            pass

    if not is_enrolled:
        raise HTTPException(
            status_code=403,
            detail="Access Forbidden: You are not enrolled in this course or lack permission to stream this protected lecture."
        )

    return {"user_id": user_id, "user": user_data}


@app.post("/api/lessons/{lesson_id}/stream-token")
async def create_lesson_stream_token(
    lesson_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    """
    Generates a cryptographically signed one-time stream token (HMAC-SHA256, 5-minute expiry).
    Guarantees that video links cannot be copied, shared, or passed to external download tools.
    """
    reload_config()
    lesson = db.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found.")

    client_ip = get_client_ip(request)
    allowed, retry_after = check_rate_limit(client_ip, "stream_token", max_requests=40, window_seconds=60)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Please wait {retry_after} seconds before requesting a new stream token.")

    course_id = lesson.get("course_id")
    is_free_preview = bool(lesson.get("is_free_preview", False))

    user_id = "anonymous_preview"
    if not is_free_preview:
        if not token and not authorization:
            raise HTTPException(status_code=401, detail="Authentication required to request a secure stream token.")
        auth_data = verify_supabase_user_and_enrollment(authorization, token, course_id)
        user_id = auth_data.get("user_id", "enrolled_student")

    signed_token = generate_signed_stream_token(
        lesson_id=lesson_id,
        user_id=user_id,
        client_ip=client_ip,
        ttl_seconds=86400
    )
    return {
        "status": "success",
        "lesson_id": lesson_id,
        "signed_token": signed_token,
        "expires_in_seconds": 86400
    }


@app.api_route("/api/lessons/{lesson_id}/stream", methods=["GET", "HEAD"])
async def stream_lesson_video(
    lesson_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    st: Optional[str] = Query(None)
):
    """
    Hardened Video Streaming Endpoint:
    - Blocks all known download tools (IDM, Wget, curl, yt-dlp, scrapers).
    - Blocks direct address bar / 'Save Link As' browser downloads.
    - Validates short-lived HMAC signed tokens (5-minute expiry) or verified session tokens.
    - Logs every unauthorized download attempt to the Admin Threat Tracker.
    - Streams byte ranges directly from private storage without buffering in memory.
    """
    reload_config()
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")

    # --- 1. ANTI-SCRAPER & DOWNLOAD TOOL DEFENSE (Check FIRST before DB lookups) ---
    threat = detect_download_attempt(request)
    if threat:
        threat_type, threat_details = threat
        db.log_security_threat(
            lesson_id=lesson_id,
            lesson_title="Target Lesson",
            threat_type=threat_type,
            ip_address=client_ip,
            user_agent=user_agent,
            details=threat_details
        )
        raise HTTPException(
            status_code=403,
            detail="Security Alert: Automated downloader tools and direct downloads are strictly prohibited. Attempt logged for instructor review."
        )

    # --- 2. RATE LIMIT CHECK ---
    allowed, retry_after = check_rate_limit(client_ip, f"stream_{lesson_id}", max_requests=360, window_seconds=60)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Streaming rate limit reached. Please wait {retry_after} seconds.")

    lesson = db.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found.")

    course_id = lesson.get("course_id")
    is_free_preview = bool(lesson.get("is_free_preview", False))

    # --- 2. AUTHENTICATION & TOKEN VERIFICATION ---
    verified_user_id = None
    if st:
        is_valid, uid, err_reason = verify_signed_stream_token(st, lesson_id, client_ip)
        if not is_valid:
            db.log_security_threat(
                lesson_id=lesson_id,
                lesson_title=lesson.get("title", "Lecture Video"),
                threat_type="EXPIRED_OR_INVALID_STREAM_TOKEN",
                ip_address=client_ip,
                user_agent=user_agent,
                details=err_reason
            )
            raise HTTPException(status_code=403, detail=f"Signed stream token invalid or expired: {err_reason}")
        verified_user_id = uid
    elif not is_free_preview:
        if not token and not authorization:
            db.log_security_threat(
                lesson_id=lesson_id,
                lesson_title=lesson.get("title", "Lecture Video"),
                threat_type="UNAUTHORIZED_ACCESS_ATTEMPT",
                ip_address=client_ip,
                user_agent=user_agent,
                details="Attempted direct stream without authentication token."
            )
            raise HTTPException(
                status_code=401,
                detail="Authentication required to stream this protected lecture video."
            )
        try:
            auth_info = verify_supabase_user_and_enrollment(authorization, token, course_id)
            verified_user_id = auth_info.get("user_id")
        except HTTPException as he:
            db.log_security_threat(
                lesson_id=lesson_id,
                lesson_title=lesson.get("title", "Lecture Video"),
                threat_type="ENROLLMENT_VERIFICATION_FAILED",
                ip_address=client_ip,
                user_agent=user_agent,
                details=he.detail
            )
            raise he

    # Enforce Anti-Piracy: If HLS encrypted package exists, disable raw progressive MP4 stream
    hls_dir = Config.CHUNKS_DIR / "hls" / lesson_id
    if (hls_dir / "master.m3u8").exists():
        raise HTTPException(
            status_code=403,
            detail="Direct progressive MP4 streaming is disabled for this protected lesson. Playback is strictly enforced via encrypted HLS."
        )

    video_url = lesson.get("video_url", "").strip()
    range_header = request.headers.get("Range")

    # CASE 1: Google Drive video
    drive_file_id = GoogleDriveManager.extract_file_id(video_url)
    if drive_file_id and drive_mgr.is_configured():
        try:
            is_head = (request.method == "HEAD")
            status_code, headers, chunk_iter = drive_mgr.stream_file_range(drive_file_id, range_header, is_head=is_head)
            if is_head:
                return Response(status_code=status_code, headers=headers)
            return StreamingResponse(chunk_iter, status_code=status_code, headers=headers)
        except FileNotFoundError:
            pass  # Fall through to check local storage
        except Exception as e:
            print(f"[Streaming Error] Google Drive streaming error: {e}")
            raise HTTPException(status_code=502, detail="Failed to stream media from Google Drive storage.")

    # CASE 2: Local uploaded MP4 file
    local_filename = Path(video_url.replace("/uploads/", "").replace("uploads/", "")).name
    local_path = (Config.UPLOADS_DIR / local_filename).resolve()
    if not str(local_path).startswith(str(Config.UPLOADS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid media file path.")
    if local_path.exists() and local_path.is_file():
        total_size = local_path.stat().st_size
        start = 0
        end = total_size - 1 if total_size > 0 else 0
        status_code = 200

        MAX_CHUNK_SIZE = 5 * 1024 * 1024
        if range_header and range_header.startswith("bytes="):
            range_val = range_header.replace("bytes=", "").strip()
            parts = range_val.split("-")
            if parts[0]:
                start = int(parts[0])
            if len(parts) > 1 and parts[1]:
                end = int(parts[1])
            else:
                end = min(start + MAX_CHUNK_SIZE - 1, total_size - 1) if total_size > 0 else start
            status_code = 206
        else:
            if total_size > MAX_CHUNK_SIZE:
                end = MAX_CHUNK_SIZE - 1
                status_code = 206

        if total_size > 0 and end >= total_size:
            end = total_size - 1

        content_length = (end - start + 1) if total_size > 0 else 0
        resp_headers = {
            "Content-Type": "video/mp4",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Disposition": "inline",
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
            "X-Content-Type-Options": "nosniff"
        }
        if status_code == 206 and total_size > 0:
            resp_headers["Content-Range"] = f"bytes {start}-{end}/{total_size}"

        if request.method == "HEAD":
            return Response(status_code=status_code, headers=resp_headers)

        def iter_file():
            with open(local_path, "rb") as f:
                f.seek(start)
                bytes_left = content_length
                while bytes_left > 0:
                    read_size = min(1024 * 64, bytes_left)
                    chunk = f.read(read_size)
                    if not chunk:
                        break
                    bytes_left -= len(chunk)
                    yield chunk

        return StreamingResponse(iter_file(), status_code=status_code, headers=resp_headers)

    # CASE 3: External streaming or YouTube fallback
    if video_url.startswith("http"):
        return RedirectResponse(url=video_url, status_code=307)

    raise HTTPException(status_code=404, detail="Video media source not found or format unsupported.")


# --- ENCRYPTED HLS ANTI-PIRACY STREAMING (Udemy/Hotstar grade AES-128) ---
@app.api_route("/api/lessons/{lesson_id}/hls/master.m3u8", methods=["GET", "HEAD"])
async def get_lesson_hls_playlist(
    lesson_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    st: Optional[str] = Query(None)
):
    """
    Serves AES-128 encrypted HLS playlist.
    If HLS directory exists for lesson_id, returns master.m3u8 with tokenized key URI.
    If not yet transcoded to HLS, dynamically packages the source video into AES-128 HLS on-demand.
    """
    client_ip = get_client_ip(request)
    threat = detect_download_attempt(request)
    if threat:
        raise HTTPException(status_code=403, detail="Automated download tools are blocked from playlist access.")

    lesson = db.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found.")

    is_free_preview = bool(lesson.get("is_free_preview", False))
    if st:
        is_valid, uid, err_reason = verify_signed_stream_token(st, lesson_id, client_ip)
        if not is_valid:
            raise HTTPException(status_code=403, detail=f"Signed playlist token invalid or expired: {err_reason}")
    elif not token and not authorization:
        raise HTTPException(status_code=401, detail="Stream token or authentication required for lecture playlist.")
    elif not is_free_preview:
        verify_supabase_user_and_enrollment(authorization, token, lesson.get("course_id"))

    hls_dir = Config.CHUNKS_DIR / "hls" / lesson_id
    playlist_file = hls_dir / "master.m3u8"

    # On-demand HLS packaging for existing lessons that were uploaded before HLS or on fresh containers
    if not playlist_file.exists():
        video_url = lesson.get("video_url", "").strip()
        temp_media_path = None
        is_temp_download = False
        try:
            drive_file_id = GoogleDriveManager.extract_file_id(video_url)
            if drive_file_id and drive_mgr.is_configured():
                temp_media_path = Config.UPLOADS_DIR / f"hls_ondemand_{lesson_id}.tmp"
                if not temp_media_path.exists():
                    download_ok = drive_mgr.download_file(drive_file_id, temp_media_path)
                    if download_ok and temp_media_path.exists():
                        is_temp_download = True
            elif "/uploads/" in video_url or "uploads/" in video_url:
                local_fname = Path(video_url.replace("/uploads/", "").replace("uploads/", "")).name
                local_fpath = (Config.UPLOADS_DIR / local_fname).resolve()
                if local_fpath.exists():
                    temp_media_path = local_fpath

            if temp_media_path and temp_media_path.exists() and HLSTranscoder.is_ffmpeg_available():
                logger.info(f"[HLS On-Demand] Packaging {lesson_id} into AES-128 encrypted HLS...")
                HLSTranscoder.package_video_to_encrypted_hls(
                    lesson_id=lesson_id,
                    input_file_path=temp_media_path,
                    output_hls_dir=hls_dir,
                    segment_duration=6
                )
        except Exception as e:
            logger.warning(f"[HLS On-Demand] Notice during packaging for {lesson_id}: {e}")
        finally:
            if is_temp_download and temp_media_path and temp_media_path.exists():
                try:
                    temp_media_path.unlink()
                except Exception:
                    pass

    if not playlist_file.exists():
        raise HTTPException(status_code=404, detail="HLS stream not yet packaged for this lesson.")

    if request.method == "HEAD":
        return Response(
            status_code=200,
            media_type="application/vnd.apple.mpegurl",
            headers={
                "Cache-Control": "private, no-cache, no-store, must-revalidate",
                "Access-Control-Allow-Origin": "*",
            }
        )

    content = playlist_file.read_text(encoding="utf-8")
    auth_query = f"?token={token}" if token else (f"?st={st}" if st else "")
    if auth_query:
        content = content.replace(f"/api/lessons/{lesson_id}/hls/key", f"/api/lessons/{lesson_id}/hls/key{auth_query}")

    return Response(
        content=content,
        media_type="application/vnd.apple.mpegurl",
        headers={
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.get("/api/lessons/{lesson_id}/hls/key")
async def get_lesson_hls_key(
    lesson_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    st: Optional[str] = Query(None)
):
    """
    Guarded AES-128 decryption key endpoint.
    Only releases the 16-byte key to authorized, enrolled students playing within the app.
    Downloaders and scrapers cannot decrypt .ts segments without this key.
    """
    client_ip = get_client_ip(request)
    threat = detect_download_attempt(request)
    if threat:
        raise HTTPException(status_code=403, detail="Key access blocked for automated tools.")

    lesson = db.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found.")

    is_free_preview = bool(lesson.get("is_free_preview", False))
    if st:
        is_valid, uid, err_reason = verify_signed_stream_token(st, lesson_id, client_ip)
        if not is_valid:
            raise HTTPException(status_code=403, detail=f"Signed key token invalid or expired: {err_reason}")
    elif not is_free_preview:
        if not token and not authorization:
            raise HTTPException(status_code=401, detail="Authentication required for key.")
        verify_supabase_user_and_enrollment(authorization, token, lesson.get("course_id"))

    key_file = Config.CHUNKS_DIR / "hls" / lesson_id / "enc.key"
    if not key_file.exists():
        raise HTTPException(status_code=404, detail="Encryption key not found.")

    key_bytes = key_file.read_bytes()
    return Response(
        content=key_bytes,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "private, no-store, must-revalidate",
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.get("/api/lessons/{lesson_id}/hls/{segment_name}")
async def get_lesson_hls_segment(
    lesson_id: str,
    segment_name: str,
    request: Request
):
    """
    Serves AES-128 encrypted media transport stream (.ts) segments.
    Without the dynamic AES key, segments are pure scrambled ciphertext.
    """
    threat = detect_download_attempt(request)
    if threat:
        raise HTTPException(status_code=403, detail="Direct segment scraping prohibited.")

    clean_seg = Path(segment_name).name
    if not clean_seg.endswith(".ts"):
        raise HTTPException(status_code=400, detail="Invalid media segment.")

    seg_file = (Config.CHUNKS_DIR / "hls" / lesson_id / clean_seg).resolve()
    if not str(seg_file).startswith(str((Config.CHUNKS_DIR / "hls").resolve())):
        raise HTTPException(status_code=400, detail="Access denied.")

    if not seg_file.exists():
        raise HTTPException(status_code=404, detail="Segment not found.")

    return FileResponse(
        path=str(seg_file),
        media_type="video/mp2t",
        headers={
            "Cache-Control": "public, max-age=86400, s-maxage=604800, immutable",
            "Access-Control-Allow-Origin": "*",
        }
    )



@app.api_route("/api/stream/drive/{file_id}", methods=["GET", "HEAD"])
async def stream_drive_file(
    file_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    st: Optional[str] = Query(None)
):
    """
    Protected Google Drive streaming endpoint with byte-range support:
    - Rejects automated downloaders and address-bar downloads.
    - Requires valid signed stream token (st) OR verified Supabase course enrollment.
    - Prevents arbitrary Google Drive file access.
    """
    reload_config()
    clean_id = GoogleDriveManager.extract_file_id(file_id)
    if not clean_id or not drive_mgr.is_configured():
        raise HTTPException(status_code=400, detail="Google Drive storage service not configured.")

    client_ip = get_client_ip(request)
    threat = detect_download_attempt(request)
    if threat:
        threat_type, threat_details = threat
        db.log_security_threat(
            lesson_id=clean_id,
            lesson_title="Direct Drive Media",
            threat_type=threat_type,
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent", ""),
            details=threat_details
        )
        raise HTTPException(
            status_code=403,
            detail="Security Alert: Automated downloader tools and direct downloads are strictly prohibited."
        )

    # Verify authorization: signed stream token or Supabase enrollment
    if st:
        is_valid, uid, err_reason = verify_signed_stream_token(st, clean_id, client_ip)
        if not is_valid:
            # Also check if token was signed for a lesson matching this drive file
            matched_lesson = next((l for l in db.list_lessons() if clean_id in l.get("video_url", "")), None)
            if matched_lesson:
                is_valid, uid, err_reason = verify_signed_stream_token(st, matched_lesson.get("id"), client_ip)
        if not is_valid:
            raise HTTPException(status_code=403, detail=f"Stream token invalid or expired: {err_reason}")
    else:
        if not token and not authorization:
            raise HTTPException(status_code=401, detail="Authentication required to stream protected video.")
        # Find course for this file
        matched_lesson = next((l for l in db.list_lessons() if clean_id in l.get("video_url", "")), None)
        if matched_lesson and matched_lesson.get("course_id"):
            verify_supabase_user_and_enrollment(authorization, token, matched_lesson.get("course_id"))
        else:
            # If not in catalog, require admin authentication
            verify_admin_or_instructor_auth(authorization)

    range_header = request.headers.get("Range")
    try:
        is_head = (request.method == "HEAD")
        status_code, headers, chunk_iter = drive_mgr.stream_file_range(clean_id, range_header, is_head=is_head)
        if is_head:
            return Response(status_code=status_code, headers=headers)
        return StreamingResponse(chunk_iter, status_code=status_code, headers=headers)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Google Drive file not found.")
    except Exception as e:
        print(f"[Streaming Error] stream_drive_file error: {e}")
        raise HTTPException(status_code=502, detail="Failed to stream media from Google Drive storage.")


@app.get("/api/admin/security/alerts")
def get_security_alerts(
    limit: int = 50,
    authorization: Optional[str] = Header(None),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    verify_admin_or_instructor_auth(authorization, x_admin_key)
    """Admin endpoint to inspect live blocked download attempts, scrapers, and unauthorized viewers."""
    threats = db.get_security_threats(limit=limit)
    return {
        "status": "success",
        "total_threats": len(threats),
        "threats": threats
    }


@app.post("/api/admin/security/alerts/clear")
def clear_security_alerts(
    authorization: Optional[str] = Header(None),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    verify_admin_or_instructor_auth(authorization, x_admin_key)
    """Admin endpoint to clear threat logs."""
    db.clear_security_threats()
    return {"status": "success", "message": "Security threat logs cleared."}

class InitDriveUploadRequest(BaseModel):
    filename: str
    mime_type: Optional[str] = "video/mp4"
    file_size: Optional[int] = 0

@app.post("/api/drive/init-upload")
async def init_drive_upload(req: InitDriveUploadRequest, request: Request):
    """
    Initializes a Google Drive Resumable Upload session.
    Returns upload_url directly to frontend so the browser can stream heavy 500MB-2GB video files
    DIRECTLY to Google Drive, completely bypassing Cloud Run's 32MB HTTP request limit!
    """
    reload_config()
    token = GoogleDriveManager.get_access_token()
    if not token:
        raise HTTPException(status_code=500, detail="Google Drive OAuth is not authenticated.")

    fid = Config.GOOGLE_DRIVE_FOLDER_ID
    init_url = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&supportsAllDrives=true'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Upload-Content-Type': req.mime_type or 'video/mp4',
    }
    if req.file_size and req.file_size > 0:
        headers['X-Upload-Content-Length'] = str(req.file_size)

    # Browser Origin header is strictly required by Google Drive to emit Access-Control-Allow-Origin on PUT response
    raw_origin = request.headers.get("origin") or request.headers.get("referer") or ""
    if raw_origin:
        from urllib.parse import urlparse
        p = urlparse(raw_origin)
        headers['Origin'] = f"{p.scheme}://{p.netloc}"
    else:
        headers['Origin'] = "http://127.0.0.1:8000"

    safe_name = req.filename.encode("ascii", "ignore").decode("ascii") or "lecture_video.mp4"
    meta = {
        'name': safe_name,
        'parents': [fid] if fid else []
    }

    try:
        r = requests.post(init_url, headers=headers, json=meta, timeout=15)
        if r.status_code == 401:
            token = GoogleDriveManager.refresh_access_token()
            headers['Authorization'] = f'Bearer {token}'
            r = requests.post(init_url, headers=headers, json=meta, timeout=15)

        if r.status_code == 200 and 'Location' in r.headers:
            return {
                "status": "success",
                "upload_url": r.headers['Location'],
                "filename": safe_name
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to initiate Google Drive upload session: {r.status_code} - {r.text}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Drive init error: {str(e)}")


@app.post("/api/process-video")
async def process_video(
    request: Request,
    file: Optional[UploadFile] = File(None),
    title: str = Form("Applied AI: Vector RAG Architectures"),
    course_name: str = Form("Applied AI & GenAI with RAG Architectures"),
    course_id: str = Form("course-applied-ai-rag"),
    media_url: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    # Enforce admin authentication & rate limit
    verify_admin_or_instructor_auth(authorization, x_admin_key)
    client_ip = get_client_ip(request)
    allowed, retry_after = check_rate_limit(client_ip, "process_video", max_requests=6, window_seconds=600)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Processing rate limit reached. Please wait {retry_after} seconds.")
    """
    Asynchronous RAG Ingestion Endpoint:
    Accepts video upload or Google Drive media URL, initializes a durable job record,
    dispatches the multi-stage ingestion to IngestionJobManager, and immediately returns
    HTTP 202 Accepted (< 250ms latency), completely preventing Cloud Run HTTP 504 timeouts!
    """
    reload_config()
    if not Config.DEEPGRAM_API_KEY:
        raise HTTPException(status_code=400, detail="Deepgram API key is not configured.")
    if not Config.GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="Gemini API key is not configured.")

    clean_title = title.strip() or "Lecture Video"
    clean_course_id = course_id.strip() or "course-applied-ai-rag"
    lesson_id = f"lesson_{uuid.uuid4().hex[:8]}"
    saved_media_path = None
    drive_file_id = None
    video_url = ""

    # Ensure course exists
    db.ensure_course_exists(clean_course_id, title=course_name or clean_title)

    try:
        # Case 1: Video File Upload
        if file and file.filename:
            file_ext = Path(file.filename).suffix.lower() or ".mp4"
            allowed_exts = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".mp3", ".wav", ".m4a"}
            if file_ext not in allowed_exts:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported media format '{file_ext}'. Allowed formats: MP4, MOV, MKV, WEBM, AVI, MP3, WAV, M4A."
                )

            temp_name = f"temp_{lesson_id}{file_ext}"
            saved_media_path = Config.UPLOADS_DIR / temp_name

            # Enforce max upload size
            max_bytes = Config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
            total_read = 0
            with open(saved_media_path, "wb") as buffer:
                while chunk := file.file.read(1024 * 1024):
                    total_read += len(chunk)
                    if total_read > max_bytes:
                        buffer.close()
                        if saved_media_path.exists():
                            saved_media_path.unlink()
                        raise HTTPException(
                            status_code=413,
                            detail=f"Uploaded video exceeds maximum allowed size of {Config.MAX_UPLOAD_SIZE_MB}MB."
                        )
                    buffer.write(chunk)

            # Offload to Google Drive if configured
            gdm = GoogleDriveManager()
            safe_fname = file.filename.encode("ascii", "ignore").decode("ascii") or "lecture_video.mp4"
            if gdm.is_configured():
                mime = file.content_type or "video/mp4"
                drive_res = gdm.upload_file(saved_media_path, filename=safe_fname, mime_type=mime)
                if drive_res:
                    drive_file_id = drive_res.get("id")
                    video_url = drive_res.get("stream_url") or drive_res.get("webViewLink")
                    if saved_media_path.exists():
                        try:
                            saved_media_path.unlink()
                            saved_media_path = None
                        except Exception:
                            pass

            if not video_url and saved_media_path:
                permanent_media_path = Config.UPLOADS_DIR / f"{lesson_id}{file_ext}"
                shutil.copy(saved_media_path, permanent_media_path)
                video_url = f"/uploads/{permanent_media_path.name}"

        elif media_url:
            clean_url = media_url.strip()
            gdm = GoogleDriveManager()
            drive_file_id = gdm.extract_file_id(clean_url)
            video_url = clean_url
        else:
            raise HTTPException(status_code=400, detail="Please upload a video file or provide a video/Drive URL.")

        # Dispatch to IngestionJobManager
        job_mgr = get_job_manager()
        job = job_mgr.submit_job(
            course_id=clean_course_id,
            title=clean_title,
            media_url=video_url,
            file_id=drive_file_id,
            lesson_id=lesson_id,
            local_filepath=str(saved_media_path) if saved_media_path else None
        )

        return JSONResponse(
            status_code=202,
            content={
                "status": "QUEUED",
                "job_id": job["id"],
                "lesson_id": job.get("lesson_id"),
                "title": clean_title,
                "stage": job.get("current_stage", "QUEUED"),
                "progress_percent": job.get("progress_percent", 0),
                "stage_message": job.get("stage_message", "Ingestion job queued."),
                "checkpoints": job.get("checkpoints", {})
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to dispatch video ingestion: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to queue video ingestion: {str(e)}")

@app.post("/api/drive/ingest")
async def ingest_from_drive(req: DriveIngestRequest):
    """Asynchronous ingestion for direct Google Drive vault files."""
    reload_config()
    gdm = GoogleDriveManager()
    if not gdm.is_configured():
        raise HTTPException(status_code=400, detail="Google Drive is not configured.")

    meta = gdm.get_file_metadata(req.file_id)
    title = req.title or (meta.get("name") if meta else "Drive Lecture")
    course_id = req.course_id or "course-applied-ai-rag"

    db.ensure_course_exists(course_id, title=req.course_name or title)

    job_mgr = get_job_manager()
    job = job_mgr.submit_job(
        course_id=course_id,
        title=title,
        file_id=req.file_id
    )

    return JSONResponse(
        status_code=202,
        content={
            "status": "QUEUED",
            "job_id": job["id"],
            "lesson_id": job.get("lesson_id"),
            "title": title,
            "stage": job.get("current_stage", "QUEUED"),
            "progress_percent": job.get("progress_percent", 0),
            "stage_message": job.get("stage_message", "Ingestion job queued.")
        }
    )

@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    """Retrieves authoritative live status of an asynchronous lecture ingestion job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job

@app.get("/api/jobs")
def list_jobs(course_id: Optional[str] = None, limit: int = 20):
    """Lists recent ingestion jobs, optionally filtered by course."""
    return db.list_jobs(course_id=course_id, limit=limit)

@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str):
    """Retries a failed or interrupted ingestion job from its latest checkpoint."""
    job = get_job_manager().retry_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job

@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    """Cancels an in-progress or queued ingestion job."""
    success = get_job_manager().cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Job '{job_id}' could not be cancelled or is already finished.")
    return {"status": "success", "message": f"Job {job_id} cancelled."}


@app.post("/api/chat")
def chat_query(req: ChatRequest, request: Request):
    client_ip = get_client_ip(request)
    allowed, retry_after = check_rate_limit(client_ip, "chat", max_requests=30, window_seconds=60)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Please wait {retry_after} seconds before asking another doubt.")
    reload_config()
    if not Config.GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="Gemini API Key is not configured.")

    try:
        engine = RAGEngine(
            Config.GEMINI_API_KEY,
            db,
            groq_api_key=Config.GROQ_API_KEY,
            groq_model=Config.GROQ_MODEL
        )
        response = engine.answer_query(
            query=req.query,
            lesson_id=req.lesson_id,
            session_id=req.session_id or "default-session"
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("RAG Error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to process doubt query. Please try again.")

@app.post("/api/chat/clear")
def clear_chat_history(req: Dict[str, Any]):
    session_id = req.get("session_id")
    if session_id:
        db.clear_chat_session(session_id)
    return {"status": "success", "message": f"Chat session {session_id} cleared"}

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
