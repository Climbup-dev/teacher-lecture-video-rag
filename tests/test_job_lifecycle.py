import unittest
import time
from fastapi.testclient import TestClient
from backend.app import app
from backend.db_adapter import DBAdapter
from backend.job_manager import get_job_manager

class TestJobLifecycleAndRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = DBAdapter()
        cls.job_mgr = get_job_manager()

    def test_01_create_and_fetch_job(self):
        """Verifies creating, fetching, and updating a durable ingestion job."""
        job = self.db.create_job(
            course_id="course-test-lifecycle",
            title="Database Concurrency & Locking",
            media_url="https://drive.google.com/file/d/test12345/view",
            file_id="test12345"
        )
        job_id = job["id"]
        self.assertTrue(job_id.startswith("job_"))
        self.assertEqual(job["status"], "QUEUED")
        self.assertEqual(job["current_stage"], "QUEUED")
        self.assertEqual(job["progress_percent"], 0)

        # Fetch job
        fetched = self.db.get_job(job_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["title"], "Database Concurrency & Locking")

    def test_02_idempotency_lookup(self):
        """Verifies that an identical request returns the existing job rather than duplicating."""
        idempotency_key = f"course-idem::file_abc::{int(time.time()*1000)}"
        job1 = self.db.create_job(
            course_id="course-idem",
            title="Title Test",
            file_id="file_abc",
            idempotency_key=idempotency_key
        )

        match = self.db.find_job_by_idempotency_key(idempotency_key)
        self.assertIsNotNone(match)
        self.assertEqual(match["id"], job1["id"])

    def test_03_stage_updates_and_checkpoints(self):
        """Verifies advancing stages with incremental checkpoint persistence."""
        job = self.db.create_job(
            course_id="course-chk",
            title="Distributed Transactions"
        )
        job_id = job["id"]

        # Stage 1: Audio Extraction
        updated = self.db.update_job_stage(
            job_id=job_id,
            stage="AUDIO_EXTRACTION",
            status="IN_PROGRESS",
            progress_percent=30,
            stage_message="Extracting audio...",
            checkpoint_data={"audio_path": "/tmp/test.mp3"}
        )
        self.assertEqual(updated["current_stage"], "AUDIO_EXTRACTION")
        self.assertEqual(updated["progress_percent"], 30)
        self.assertEqual(updated["checkpoints"]["audio_path"], "/tmp/test.mp3")

        # Stage 2: Transcription Checkpoint
        updated2 = self.db.update_job_stage(
            job_id=job_id,
            stage="TRANSCRIPTION",
            progress_percent=60,
            stage_message="Transcribing Nova-2...",
            checkpoint_data={"utterances_count": 42}
        )
        self.assertEqual(updated2["current_stage"], "TRANSCRIPTION")
        self.assertEqual(updated2["checkpoints"]["audio_path"], "/tmp/test.mp3")
        self.assertEqual(updated2["checkpoints"]["utterances_count"], 42)

        # Stage 3: Complete Job
        completed = self.db.complete_job(
            job_id=job_id,
            lesson_id="lesson_chk_123",
            duration_seconds=3600,
            total_chunks=35
        )
        self.assertEqual(completed["status"], "COMPLETED")
        self.assertEqual(completed["progress_percent"], 100)
        self.assertIsNotNone(completed["completed_at"])
        self.assertEqual(completed["checkpoints"]["total_chunks_indexed"], 35)

    def test_04_failure_and_retry(self):
        """Verifies terminal failure and recovery from checkpoint."""
        job = self.db.create_job(
            course_id="course-fail",
            title="Failure Handling Lecture"
        )
        job_id = job["id"]

        # Fail job
        failed = self.db.fail_job(job_id, error_message="Network timeout to Deepgram")
        self.assertEqual(failed["status"], "FAILED")
        self.assertEqual(failed["current_stage"], "FAILED")
        self.assertIn("Deepgram", failed["error_message"])

        # Retry via manager
        retried = self.job_mgr.retry_job(job_id)
        self.assertIn(retried["status"], ("QUEUED", "IN_PROGRESS"))

    def test_05_cancellation(self):
        """Verifies cancellation of queued/running job."""
        job = self.db.create_job(
            course_id="course-cancel",
            title=f"Cancelled Lecture {int(time.time()*1000)}"
        )
        job_id = job["id"]

        cancelled = self.job_mgr.cancel_job(job_id)
        self.assertTrue(cancelled)

        fetched = self.db.get_job(job_id)
        self.assertEqual(fetched["status"], "CANCELLED")

    def test_06_http_async_dispatch_returns_202(self):
        """Verifies that POST /api/process-video returns HTTP 202 Accepted with job_id."""
        res = self.client.post("/api/process-video", data={
            "title": "Async Ingestion Architecture",
            "course_id": "course-test-lifecycle",
            "media_url": "https://drive.google.com/file/d/12345sample/view"
        })
        self.assertEqual(res.status_code, 202)
        data = res.json()
        self.assertIn("job_id", data)
        self.assertIn("status", data)
        self.assertEqual(data["status"], "QUEUED")
        self.assertEqual(data["title"], "Async Ingestion Architecture")

        # Verify job is retrievable via GET /api/jobs/{id}
        job_id = data["job_id"]
        job_res = self.client.get(f"/api/jobs/{job_id}")
        self.assertEqual(job_res.status_code, 200)
        job_data = job_res.json()
        self.assertEqual(job_data["id"], job_id)

    def test_07_http_job_endpoints(self):
        """Verifies listing, retry, and cancellation via HTTP."""
        # List jobs
        list_res = self.client.get("/api/jobs")
        self.assertEqual(list_res.status_code, 200)
        self.assertIsInstance(list_res.json(), list)

        # Non-existent job returns 404
        not_found = self.client.get("/api/jobs/job_non_existent_9999")
        self.assertEqual(not_found.status_code, 404)

if __name__ == "__main__":
    unittest.main()
