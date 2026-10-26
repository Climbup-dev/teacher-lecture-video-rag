import os
import smtplib
import threading
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional, Dict, Any
from backend.config import Config

logger = logging.getLogger("climbup.notifier")

class EmailNotifier:
    """
    pracTQ Mentor Studio Email Notification Service.
    Automatically alerts instructors and mentors upon completion of the AI lecture pipeline
    (Deepgram Nova-2, Gemini Concept Boundaries, Vector Embeddings & Practice Quizzes).
    """

    SYSTEM_NAME = "pracTQ Mentor Studio"

    @classmethod
    def get_mentor_emails(cls, db) -> List[str]:
        """
        Gathers distinct mentor and instructor emails from:
        1. Supabase profiles with role in ('mentor', 'instructor', 'admin', 'coordinator')
        2. Configured MENTOR_EMAILS environment variables
        """
        emails = set()

        # 1. Supabase Profiles lookup
        if db.supabase_url and db.supabase_key:
            try:
                headers = db._get_headers()
                res = db.session.get(
                    f"{db.supabase_url}/rest/v1/profiles?select=email,role",
                    headers=headers,
                    timeout=5
                )
                if res.ok and isinstance(res.json(), list):
                    for p in res.json():
                        role = (p.get("role") or "").lower().strip()
                        em = (p.get("email") or "").strip().lower()
                        if role in ("mentor", "instructor", "admin", "coordinator") and "@" in em:
                            emails.add(em)
            except Exception as e:
                logger.warning(f"Failed to query mentor profiles from Supabase: {e}")

        # 2. Configured MENTOR_EMAILS from environment
        env_emails = getattr(Config, "MENTOR_EMAILS", [])
        if isinstance(env_emails, list):
            for em in env_emails:
                if isinstance(em, str) and "@" in em.strip():
                    emails.add(em.strip().lower())
        elif isinstance(env_emails, str):
            for em in env_emails.split(","):
                if "@" in em.strip():
                    emails.add(em.strip().lower())

        # Fallback to default admin email if none resolved
        if not emails:
            emails.add("amirshaikh320340@gmail.com")

        return sorted(list(emails))

    @classmethod
    def send_mentor_completion_email(
        cls,
        db,
        lesson_id: str,
        title: str,
        course_name: str,
        duration_seconds: int,
        total_chunks: int,
        studio_url: Optional[str] = None
    ) -> bool:
        """
        Synchronously formats and sends the notification email to mentors.
        Safely fails with log warnings if SMTP is not configured or fails.
        """
        recipients = cls.get_mentor_emails(db)
        if not recipients:
            logger.info("No mentor emails resolved for notification.")
            return False

        mins = duration_seconds // 60
        secs = duration_seconds % 60
        duration_label = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        target_studio_url = studio_url or f"http://localhost:{Config.PORT}"

        subject = f"[{cls.SYSTEM_NAME}] AI Pipeline Completed: {title}"

        # HTML Email Body with modern pracTQ Mentor Studio styling
        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b0f19; color: #e2e8f0; margin: 0; padding: 24px; }}
    .container {{ max-width: 620px; margin: 0 auto; background: #131b2e; border: 1px solid #1e293b; border-radius: 14px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
    .header {{ background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); padding: 28px; text-align: center; border-bottom: 1px solid #3730a3; }}
    .badge {{ display: inline-block; padding: 4px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #38d399; background: rgba(56, 211, 153, 0.12); border: 1px solid rgba(56, 211, 153, 0.25); border-radius: 20px; margin-bottom: 10px; }}
    .title {{ font-size: 22px; font-weight: 700; color: #ffffff; margin: 0 0 6px 0; }}
    .subtitle {{ font-size: 13px; color: #94a3b8; margin: 0; }}
    .content {{ padding: 28px; }}
    .card {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 10px; padding: 18px; margin: 20px 0; }}
    .meta-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #1e293b; font-size: 13px; }}
    .meta-row:last-child {{ border-bottom: none; }}
    .meta-label {{ color: #94a3b8; font-weight: 500; }}
    .meta-val {{ color: #f8fafc; font-weight: 600; text-align: right; }}
    .steps-list {{ margin: 18px 0; padding: 0; list-style: none; }}
    .step-item {{ display: flex; align-items: center; margin-bottom: 10px; font-size: 13px; color: #cbd5e1; }}
    .step-icon {{ display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; background: rgba(56, 211, 153, 0.15); color: #38d399; border-radius: 50%; font-size: 11px; font-weight: 700; margin-right: 12px; flex-shrink: 0; }}
    .security-note {{ background: rgba(99, 102, 241, 0.08); border-left: 3px solid #6366f1; padding: 12px 16px; border-radius: 0 8px 8px 0; font-size: 12px; color: #a5b4fc; margin-top: 20px; }}
    .btn-wrap {{ text-align: center; margin: 30px 0 10px 0; }}
    .btn {{ display: inline-block; background: #6366f1; color: #ffffff !important; padding: 14px 32px; border-radius: 8px; font-size: 14px; font-weight: 700; text-decoration: none; box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4); }}
    .footer {{ padding: 20px 28px; background: #090d16; text-align: center; font-size: 11px; color: #64748b; border-top: 1px solid #1e293b; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="badge">pracTQ AI Engine</div>
      <h1 class="title">{cls.SYSTEM_NAME}</h1>
      <p class="subtitle">Automated Ingestion & Pedagogical RAG Pipeline</p>
    </div>
    <div class="content">
      <p style="font-size: 15px; color: #f1f5f9; margin-top: 0;">
        Hello Mentor,
      </p>
      <p style="font-size: 14px; color: #94a3b8; line-height: 1.6;">
        A new lecture video has finished full AI ingestion and is now completely synchronized. The video was made immediately accessible to enrolled students via encrypted, DRM-hardened streaming upon upload.
      </p>
      
      <div class="card">
        <div class="meta-row">
          <span class="meta-label">Lecture Title</span>
          <span class="meta-val">{title}</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">Course</span>
          <span class="meta-val">{course_name}</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">Lesson ID</span>
          <span class="meta-val" style="font-family: monospace;">{lesson_id}</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">Lecture Duration</span>
          <span class="meta-val">{duration_label}</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">Indexed Concept Chunks</span>
          <span class="meta-val">{total_chunks} Chunks (768-dim)</span>
        </div>
      </div>

      <h3 style="font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: #94a3b8; margin: 24px 0 12px 0;">Completed AI Pipeline Stages:</h3>
      <div class="steps-list">
        <div class="step-item"><span class="step-icon">✓</span> 16kHz Audio Extraction (FFmpeg WAV)</div>
        <div class="step-item"><span class="step-icon">✓</span> Deepgram Nova-2 Word-Level Diarization & Timestamps</div>
        <div class="step-item"><span class="step-icon">✓</span> Gemini Semantic Concept Boundaries & HyDE Query Synthesis</div>
        <div class="step-item"><span class="step-icon">✓</span> 768-dim Vector Embeddings & Supabase pgvector Sync</div>
        <div class="step-item"><span class="step-icon">✓</span> Auto-synthesis of Practice Quizzes (pracTQ Assessment Bank)</div>
      </div>

      <div class="security-note">
        🔒 <strong>Zero Security Exposure:</strong> All video streams remain protected behind short-lived HMAC session tokens, anti-piracy downloader guards, and enrollment checks. Direct mp4 links are not exposed.
      </div>

      <div class="btn-wrap">
        <a href="{target_studio_url}" class="btn">Open in pracTQ Mentor Studio</a>
      </div>
    </div>
    <div class="footer">
      Sent automatically by {cls.SYSTEM_NAME} &bull; ClimbUP Education Infrastructure
    </div>
  </div>
</body>
</html>"""

        # Plain text fallback
        plain_text = f"""{cls.SYSTEM_NAME} - Automated AI Ingestion Notification

Hello Mentor,

A new lecture video has been fully processed and indexed by the AI pipeline:

Lecture Title: {title}
Course: {course_name}
Lesson ID: {lesson_id}
Duration: {duration_label}
Concept Chunks: {total_chunks}

Completed Stages:
[OK] 16kHz Audio Extraction (FFmpeg WAV)
[OK] Deepgram Nova-2 Word-Level Diarization & Timestamps
[OK] Gemini Semantic Concept Boundaries & HyDE Query Synthesis
[OK] 768-dim Vector Embeddings & Supabase pgvector Sync
[OK] Practice Quizzes (pracTQ Assessment Bank) Auto-synthesized

The lecture is live and accessible via secure encrypted streaming.
Open in pracTQ Mentor Studio: {target_studio_url}

Sent automatically by {cls.SYSTEM_NAME}
"""

        # Dispatch via SMTP if configured
        smtp_host = getattr(Config, "SMTP_HOST", "smtp.gmail.com")
        smtp_port = getattr(Config, "SMTP_PORT", 587)
        smtp_user = getattr(Config, "SMTP_USER", "")
        smtp_password = getattr(Config, "SMTP_PASSWORD", "")
        smtp_from = getattr(Config, "SMTP_FROM", f"{cls.SYSTEM_NAME} <notifications@practq.com>")

        # Always record notification in DB / local store for in-app audit
        try:
            notification_record = {
                "lesson_id": lesson_id,
                "title": title,
                "recipients": recipients,
                "status": "SENT" if (smtp_user and smtp_password) else "SIMULATED_LOG",
                "timestamp": None
            }
            if hasattr(db, "log_mentor_notification"):
                db.log_mentor_notification(notification_record)
        except Exception:
            pass

        if not smtp_user or not smtp_password:
            logger.info(
                f"[{cls.SYSTEM_NAME}] SMTP credentials not set. Simulated notification logged for {len(recipients)} mentors: {recipients}. "
                f"Lecture: '{title}' ({lesson_id})"
            )
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = smtp_from
            msg["To"] = ", ".join(recipients)

            msg.attach(MIMEText(plain_text, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, recipients, msg.as_string())

            logger.info(f"[{cls.SYSTEM_NAME}] Successfully sent completion email to mentors {recipients} for lecture '{title}'")
            return True
        except Exception as e:
            logger.error(f"[{cls.SYSTEM_NAME}] SMTP dispatch failed: {e}")
            return False

    @classmethod
    def notify_mentors_async(
        cls,
        db,
        lesson_id: str,
        title: str,
        course_name: str,
        duration_seconds: int,
        total_chunks: int,
        studio_url: Optional[str] = None
    ):
        """Dispatches email notification safely in a background daemon thread."""
        def _worker():
            try:
                cls.send_mentor_completion_email(
                    db=db,
                    lesson_id=lesson_id,
                    title=title,
                    course_name=course_name,
                    duration_seconds=duration_seconds,
                    total_chunks=total_chunks,
                    studio_url=studio_url
                )
            except Exception as e:
                logger.warning(f"[{cls.SYSTEM_NAME}] Background email dispatcher notice: {e}")

        threading.Thread(target=_worker, daemon=True).start()
