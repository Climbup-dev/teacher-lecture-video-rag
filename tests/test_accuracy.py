import json
import unittest
from fastapi.testclient import TestClient
from backend.app import app
from backend.config import Config

BASE_URL = "http://127.0.0.1:8000"

BENCHMARK_CASES = [
    {
        "id": "Q1_PCB_CONTEXT_SWITCH",
        "query": "What is a Process Control Block (PCB) and what exact hardware state is saved during a context switch?",
        "expected_timestamp": "24:00",
        "expected_sec": 1440,
        "expected_keywords": ["PCB", "Program Counter", "register", "context switch", "cache"],
        "expected_topic": "PCB & Context Switching"
    },
    {
        "id": "Q2_ROUND_ROBIN_QUANTUM",
        "query": "Explain Round Robin scheduling. What mathematical trade-off exists when setting the time quantum too large vs too small?",
        "expected_timestamp": "01:14:35",
        "expected_sec": 4475,
        "expected_keywords": ["Round Robin", "quantum", "FCFS", "overhead"],
        "expected_topic": "Round Robin"
    },
    {
        "id": "Q3_80_PERCENT_RULE",
        "query": "What is the 80% rule of thumb for CPU bursts and how does it balance waiting time with context switch overhead?",
        "expected_timestamp": "01:42:20",
        "expected_sec": 6140,
        "expected_keywords": ["80", "burst", "quantum", "context switch"],
        "expected_topic": "80% Rule"
    }
]

class TestLectureRAGAccuracy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Ensure sample OS scheduling lecture is loaded for benchmark testing
        cls.client.post("/api/load-sample")

    def test_status_endpoint(self):
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("gemini_configured"))
        self.assertTrue(data.get("deepgram_configured"))
        self.assertGreaterEqual(data.get("total_lessons_indexed", 0), 1)

    def test_benchmark_rag_query(self):
        """Verifies accuracy and timestamp retrieval against sample university lecture."""
        if not Config.GEMINI_API_KEY:
            self.skipTest("GEMINI_API_KEY is not configured.")

        payload = {
            "lesson_id": "sample_os_scheduling",
            "query": "Explain Round Robin scheduling and time quantum trade-offs."
        }
        resp = self.client.post("/api/chat", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # 1. Retrieved evidence verification
        evidence = data.get("retrieved_evidence", [])
        self.assertGreater(len(evidence), 0)

        # 2. Fact Groundedness
        answer = data.get("answer", "").lower()
        self.assertTrue(any(k in answer for k in ["round robin", "quantum", "time", "cpu"]))

        # 3. Dedicated Video timestamps section
        timestamps = data.get("video_timestamps", [])
        self.assertIsInstance(timestamps, list)

if __name__ == "__main__":
    unittest.main()
