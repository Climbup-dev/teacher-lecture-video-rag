import hmac
import hashlib
import base64
import json
import time
from typing import Optional, Tuple, Dict, Any
from fastapi import Request
from backend.config import Config

BLOCKED_TOOL_SUBSTRINGS = [
    "idm", "internet download manager", "wget", "curl", "python-requests",
    "python-urllib", "yt-dlp", "youtube-dl", "aria2", "fdm", "free download manager",
    "downline", "downloadmanager", "okhttp", "postman", "insomnia", "httpie",
    "playwright", "puppeteer", "selenium", "go-http-client", "libcurl", "jdownloader",
    "videodownloadhelper", "cococut", "ant download manager", "eagleget", "flashget"
]

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

    # 1. Check known scraper / downloader user agents
    for tool in BLOCKED_TOOL_SUBSTRINGS:
        if tool in ua:
            return "BLOCKED_DOWNLOADER_TOOL", f"Known downloader tool '{tool}' detected in User-Agent ({ua[:60]})."

    # 2. Check direct browser address-bar download or 'Save Link As'
    # HTML5 video elements use sec-fetch-dest: 'video' or 'audio' or 'empty', mode: 'no-cors' or 'cors'
    # Direct browser tab opening or download uses sec-fetch-dest: 'document' and sec-fetch-mode: 'navigate'
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
