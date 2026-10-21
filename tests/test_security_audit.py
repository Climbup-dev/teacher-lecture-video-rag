import sys
import unittest
from fastapi.testclient import TestClient
from backend.app import app
from backend.security import (
    generate_signed_stream_token, 
    verify_signed_stream_token,
    check_rate_limit,
    detect_download_attempt
)

class SecurityAuditTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_blocked_downloader_user_agents(self):
        """Verify that automated downloaders (IDM, yt-dlp, curl, etc.) are strictly blocked."""
        for tool in ["yt-dlp/2024.08.01", "Mozilla/5.0 (Windows) Internet Download Manager 6.42", "Wget/1.21", "curl/8.4.0"]:
            response = self.client.get(
                "/api/lessons/lesson_test/stream",
                headers={"User-Agent": tool}
            )
            self.assertEqual(response.status_code, 403, f"Downloader {tool} should receive 403 Forbidden")
            self.assertIn("Security Alert", response.json().get("detail", ""))

    def test_02_blocked_direct_browser_address_bar_download(self):
        """Verify that direct browser navigation downloads outside the video player are blocked."""
        response = self.client.get(
            "/api/lessons/lesson_test/stream",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate"
            }
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Security Alert", response.json().get("detail", ""))

    def test_03_unauthenticated_stream_access_denied(self):
        """Verify that unauthenticated users cannot stream protected content."""
        response = self.client.get(
            "/api/lessons/lesson_nonexistent/stream",
            headers={"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36"}
        )
        # Should be 404 if lesson not found, or 401 if lesson is protected
        self.assertIn(response.status_code, [401, 404])

    def test_04_forged_stream_token_denied(self):
        """Verify that forged, tampered, or expired tokens are rejected."""
        response = self.client.get(
            "/api/lessons/lesson_test/stream?st=forged.signature123",
            headers={"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36"}
        )
        self.assertIn(response.status_code, [403, 404])

    def test_05_unauthorized_admin_endpoints_denied(self):
        """Verify that administrative and destructive endpoints require valid admin credentials."""
        # DELETE lesson
        res = self.client.delete("/api/lessons/test_lesson")
        self.assertEqual(res.status_code, 401)

        # DELETE course
        res = self.client.delete("/api/courses/test_course")
        self.assertEqual(res.status_code, 401)

        # POST update-config
        res = self.client.post("/api/update-config", json={"deepgram_key": "fake"})
        self.assertEqual(res.status_code, 401)

    def test_06_signed_token_generation_and_speed(self):
        """Verify that HMAC stream tokens generate and verify in sub-millisecond time for fast playback."""
        import time
        start = time.perf_counter()
        token = generate_signed_stream_token("lesson_abc123", "user_test_999", "127.0.0.1", ttl_seconds=300)
        gen_time_ms = (time.perf_counter() - start) * 1000

        self.assertIn(".", token)
        self.assertLess(gen_time_ms, 5.0, "Token generation must take < 5ms for fast user access")

        start_v = time.perf_counter()
        is_valid, uid, err = verify_signed_stream_token(token, "lesson_abc123", "127.0.0.1")
        verify_time_ms = (time.perf_counter() - start_v) * 1000

        self.assertTrue(is_valid)
        self.assertEqual(uid, "user_test_999")
        self.assertLess(verify_time_ms, 1.0, "Token verification must take < 1ms for instant video playback")

    def test_07_rate_limiter_enforcement(self):
        """Verify sliding window rate limiting prevents abuse."""
        ip = "192.168.100.99"
        # 3 requests allowed
        ok1, _ = check_rate_limit(ip, "test_action", max_requests=2, window_seconds=10)
        ok2, _ = check_rate_limit(ip, "test_action", max_requests=2, window_seconds=10)
        ok3, retry = check_rate_limit(ip, "test_action", max_requests=2, window_seconds=10)

        self.assertTrue(ok1)
        self.assertTrue(ok2)
        self.assertFalse(ok3)
        self.assertGreaterEqual(retry, 1)

if __name__ == "__main__":
    unittest.main()
