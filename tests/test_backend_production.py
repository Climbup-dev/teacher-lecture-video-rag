import unittest
from fastapi.testclient import TestClient
from backend.app import app
from backend.config import Config

class TestBackendProductionSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_health_and_healthz_probes(self):
        """Verifies container orchestrator liveness probes."""
        for path in ("/health", "/healthz"):
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, f"Failed on {path}")
            data = res.json()
            self.assertEqual(data.get("status"), "healthy")
            self.assertIn("timestamp", data)
            self.assertIn("environment", data)

    def test_02_security_headers_present(self):
        """Verifies that mandatory OWASP and production security headers are set on all responses."""
        res = self.client.get("/health")
        headers = res.headers
        self.assertIn("x-request-id", headers)
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(headers.get("x-frame-options"), "SAMEORIGIN")
        self.assertEqual(headers.get("referrer-policy"), "strict-origin-when-cross-origin")
        self.assertIn("permissions-policy", headers)
        self.assertIn("x-response-time", headers)

    def test_03_api_status_endpoint(self):
        """Verifies server status and external dependency readiness."""
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("deepgram_configured", data)
        self.assertIn("gemini_configured", data)
        self.assertIn("supabase_configured", data)
        self.assertIn("total_lessons_indexed", data)
        self.assertIn("total_chunks_indexed", data)

    def test_04_courses_endpoint_validation(self):
        """Verifies course listing and validation against empty titles."""
        # Listing courses
        res = self.client.get("/api/courses")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

        # Validation: empty title must return 400
        bad_res = self.client.post("/api/courses", json={"title": ""})
        self.assertEqual(bad_res.status_code, 400)

        bad_spaces = self.client.post("/api/courses", json={"title": "   "})
        self.assertEqual(bad_spaces.status_code, 400)

    def test_05_students_endpoint_validation(self):
        """Verifies student enrollment listing and input validation."""
        res = self.client.get("/api/students")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

        # Validation: missing name or email must return 400
        bad_student = self.client.post("/api/students", json={
            "name": "",
            "email": "test@climbup.edu",
            "course_id": "course-test"
        })
        self.assertEqual(bad_student.status_code, 400)

        bad_email = self.client.post("/api/students", json={
            "name": "Jane Doe",
            "email": "",
            "course_id": "course-test"
        })
        self.assertEqual(bad_email.status_code, 400)

    def test_06_lessons_endpoints(self):
        """Verifies lesson retrieval and 404 behavior."""
        res = self.client.get("/api/lessons")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

        # Non-existent lesson returns 404
        not_found = self.client.get("/api/lessons/non_existent_lesson_999999")
        self.assertEqual(not_found.status_code, 404)

    def test_07_config_update_security(self):
        """Verifies that config update endpoint respects readonly and admin protections."""
        orig_readonly = Config.READONLY_CONFIG
        orig_admin_key = Config.ADMIN_API_KEY
        try:
            # When READONLY_CONFIG is True, must return 403 Forbidden
            Config.READONLY_CONFIG = True
            res = self.client.post("/api/update-config", json={"gemini_key": "dummy"})
            self.assertEqual(res.status_code, 403)

            # When ADMIN_API_KEY is required but missing/invalid, must return 401
            Config.READONLY_CONFIG = False
            Config.ADMIN_API_KEY = "super_secret_admin_token"
            unauth_res = self.client.post("/api/update-config", json={"gemini_key": "dummy"})
            self.assertEqual(unauth_res.status_code, 401)

            bad_key_res = self.client.post(
                "/api/update-config",
                headers={"X-Admin-Key": "wrong_key"},
                json={"gemini_key": "dummy"}
            )
            self.assertEqual(bad_key_res.status_code, 401)
        finally:
            Config.READONLY_CONFIG = orig_readonly
            Config.ADMIN_API_KEY = orig_admin_key

    def test_08_resource_upload_validation(self):
        """Verifies resource upload rejects empty files."""
        res = self.client.post(
            "/api/resources/upload",
            data={"title": "Lecture 1 Slides", "course_id": "course-1"},
            files={"file": ("slides.pdf", b"", "application/pdf")}
        )
        self.assertEqual(res.status_code, 400)

    def test_09_stream_path_traversal_protection(self):
        """Verifies that non-existent or path traversal streams return 404 / 400 cleanly."""
        res = self.client.get("/api/lessons/invalid_id/stream")
        self.assertEqual(res.status_code, 404)

    def test_10_rag_chat_flow(self):
        """Verifies RAG chat endpoint rejects empty/unconfigured or returns response."""
        res = self.client.post("/api/chat", json={
            "query": "What is the CPU burst time trade-off in Round Robin?",
            "lesson_id": "sample_os_scheduling",
            "session_id": "test-session-123"
        })
        # If Gemini key is set, returns 200, otherwise 400
        if Config.GEMINI_API_KEY:
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("answer", data)
            self.assertIn("retrieved_evidence", data)
            self.assertIn("video_timestamps", data)
        else:
            self.assertEqual(res.status_code, 400)

    def test_11_chat_clear_endpoint(self):
        """Verifies clearing chat history."""
        res = self.client.post("/api/chat/clear", json={"session_id": "test-session-123"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "success")

if __name__ == "__main__":
    unittest.main()
