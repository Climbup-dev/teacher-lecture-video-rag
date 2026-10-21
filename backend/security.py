import hmac
import hashlib
import base64
import json
import time
import threading
from typing import Optional, Tuple, Dict, Any, List
from fastapi import Request, HTTPException
import requests
from backend.config import Config

BLOCKED_TOOL_SUBSTRINGS = [
    "idm", "internet download manager", "wget", "curl", "python-requests",
    "python-urllib", "yt-dlp", "youtube-dl", "aria2", "fdm", "free download manager",
    "downline", "downloadmanager", "okhttp", "postman", "insomnia", "httpie",
    "playwright", "puppeteer", "selenium", "go-http-client", "libcurl", "jdownloader",
    "videodownloadhelper", "cococut", "ant download manager", "eagleget", "flashget"
]

# --- SLIDING WINDOW IN-MEMORY RATE LIMITER ---
_rate_limit_lock = threading.Lock()
_rate_limit_records: Dict[str, List[float]] = {}

def check_rate_limit(
    client_ip: str, 
    endpoint_key: str, 
    max_requests: int = 60, 
    window_seconds: int = 60
) -> Tuple[bool, int]:
    """
    Thread-safe sliding-window rate limiter per client IP + endpoint.
    Returns (is_allowed, remaining_requests_or_retry_after).
    """
    now = time.time()
    key = f"{client_ip}:{endpoint_key}"

    with _rate_limit_lock:
        timestamps = _rate_limit_records.get(key, [])
        # Prune old timestamps
        cutoff = now - window_seconds
        valid_timestamps = [ts for ts in timestamps if ts > cutoff]

        if len(valid_timestamps) >= max_requests:
            retry_after = int(valid_timestamps[0] + window_seconds - now) + 1
            _rate_limit_records[key] = valid_timestamps
            return False, max(1, retry_after)

        valid_timestamps.append(now)
        _rate_limit_records[key] = valid_timestamps
        remaining = max_requests - len(valid_timestamps)
        return True, remaining


def get_signing_secret() -> bytes:
    seed = Config.SUPABASE_KEY or Config.ADMIN_API_KEY or "climbup-secure-video-salt-987"
    return hashlib.sha256(seed.encode("utf-8")).digest()


def generate_signed_stream_token(
    lesson_id: str,
    user_id: str,
    client_ip: str = "",
    ttl_seconds: int = 300
) -> str:
    """
    Generates a cryptographically signed, short-lived (5 min default) token
    specifically tied to a lesson, user, and IP address.
    """
    payload = {
        "lid": str(lesson_id),
        "uid": str(user_id),
        "ip": str(client_ip or ""),
        "exp": int(time.time()) + ttl_seconds
    }
    payload_json = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("ascii").rstrip("=")

    secret = get_signing_secret()
    signature = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")

    return f"{payload_b64}.{sig_b64}"


def verify_signed_stream_token(
    token_str: str,
    lesson_id: str,
    client_ip: str = ""
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Verifies token signature, expiration, and lesson binding.
    Returns: (is_valid, user_id, error_reason)
    """
    if not token_str or "." not in token_str:
        return False, None, "Invalid or missing signed stream token format."

    parts = token_str.split(".")
    if len(parts) != 2:
        return False, None, "Malformed stream token structure."

    payload_b64, sig_b64 = parts[0], parts[1]
    secret = get_signing_secret()
    expected_sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode("ascii").rstrip("=")

    if not hmac.compare_digest(sig_b64, expected_sig_b64):
        return False, None, "Cryptographic token signature verification failed."

    # Pad base64 if needed
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    try:
        payload_bytes = base64.urlsafe_b64decode(padded)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        return False, None, f"Failed to decode token payload: {e}"

    if int(payload.get("exp", 0)) < int(time.time()):
        return False, None, "Signed stream token has expired (tokens are valid for 5 minutes only)."

    if payload.get("lid") != lesson_id:
        return False, None, "Signed token does not match requested lesson."

    return True, payload.get("uid"), None


def detect_download_attempt(request: Request) -> Optional[Tuple[str, str]]:
    """
    Detects third-party scrapers, download tools, or direct browser download attempts.
    Returns (threat_type, details) if detected, otherwise None.
    """
    headers = request.headers
    ua = (headers.get("user-agent") or "").lower().strip()
    sec_fetch_dest = (headers.get("sec-fetch-dest") or "").lower().strip()
    sec_fetch_mode = (headers.get("sec-fetch-mode") or "").lower().strip()
    client_ip = get_client_ip(request)

    # 1. Check known scraper / downloader user agents
    for tool in BLOCKED_TOOL_SUBSTRINGS:
        if tool in ua:
            return "BLOCKED_DOWNLOADER_TOOL", f"Known downloader tool '{tool}' detected in User-Agent ({ua[:60]})."

    # 2. Check direct browser address-bar download or 'Save Link As'
    if sec_fetch_dest == "document" and sec_fetch_mode == "navigate":
        return "DIRECT_URL_DOWNLOAD_ATTEMPT", "Direct browser navigation/download attempted outside authorized video player."

    return None


def get_client_ip(request: Request) -> str:
    """Extracts true client IP respecting Cloud Run / reverse proxy headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def verify_admin_or_instructor_auth(
    authorization_header: Optional[str] = None,
    x_admin_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Enforces authorization for administrative and destructive operations:
    1. Direct match with configured ADMIN_API_KEY / X-Admin-Key.
    2. Supabase Bearer token with verified role: admin, instructor, coordinator.
    Raises HTTPException 401 or 403 on failure.
    """
    admin_secret = Config.ADMIN_API_KEY
    auth_token = None
    if authorization_header and authorization_header.startswith("Bearer "):
        auth_token = authorization_header.split(" ", 1)[1].strip()

    # Check 1: X-Admin-Key or admin secret match
    provided_key = x_admin_key or auth_token
    if admin_secret and provided_key and hmac.compare_digest(provided_key, admin_secret):
        return {"role": "admin", "user_id": "admin_key"}

    # Check 2: Verify with Supabase Auth
    if not auth_token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: Provide valid X-Admin-Key or Authorization Bearer token."
        )

    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        # If Supabase is not configured, require admin_secret
        if not admin_secret:
            raise HTTPException(
                status_code=403,
                detail="Administrative operations are disabled until ADMIN_API_KEY or Supabase is configured."
            )
        raise HTTPException(status_code=403, detail="Invalid administrative credentials.")

    user_url = f"{Config.SUPABASE_URL}/auth/v1/user"
    auth_headers = {
        "apikey": Config.SUPABASE_KEY,
        "Authorization": f"Bearer {auth_token}"
    }

    try:
        user_res = requests.get(user_url, headers=auth_headers, timeout=6)
        if not user_res.ok:
            raise HTTPException(status_code=401, detail="Invalid, expired, or revoked admin session token.")
        user_data = user_res.json()
        user_id = user_data.get("id")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication verification failed: {e}")

    # Check user role in Supabase
    service_headers = {
        "apikey": Config.SUPABASE_KEY,
        "Authorization": f"Bearer {Config.SUPABASE_KEY}"
    }

    allowed_roles = {"admin", "instructor", "coordinator", "superadmin"}

    # 1. Check user_metadata
    user_metadata = user_data.get("user_metadata", {})
    if user_metadata.get("role") in allowed_roles:
        return {"role": user_metadata.get("role"), "user_id": user_id, "user": user_data}

    # 2. Check profiles table
    try:
        prof_url = f"{Config.SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}&select=role"
        prof_res = requests.get(prof_url, headers=service_headers, timeout=5)
        if prof_res.ok and prof_res.json():
            role = prof_res.json()[0].get("role", "")
            if role in allowed_roles:
                return {"role": role, "user_id": user_id, "user": user_data}
    except Exception:
        pass

    raise HTTPException(
        status_code=403,
        detail="Access Forbidden: Administrative or Instructor privileges are required for this action."
    )
