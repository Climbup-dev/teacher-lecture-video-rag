import json
import urllib.request
import time
import unittest

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
    },
    {
        "id": "Q4_BANKERS_ALGORITHM",
        "query": "How does the Banker's Algorithm prevent deadlocks, and what are the 4 Coffman conditions explained by the professor?",
        "expected_timestamp": "02:18:45",
        "expected_sec": 8325,
        "expected_keywords": ["Coffman", "Mutual Exclusion", "Hold and Wait", "No Preemption", "Circular Wait", "Safe State", "Banker"],
        "expected_topic": "Deadlock & Banker's"
    },
    {
        "id": "Q5_TLB_VIRTUAL_MEMORY",
        "query": "How does Translation Lookaside Buffer (TLB) paging reduce memory access overhead in virtual memory systems?",
        "expected_timestamp": "02:45:10",
        "expected_sec": 9910,
        "expected_keywords": ["TLB", "Translation Lookaside Buffer", "EAT", "paging", "hit ratio"],
        "expected_topic": "Virtual Memory & TLB"
    }
]

def parse_ts(ts_str):
    parts = ts_str.replace("[", "").replace("]", "").strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0

class TestLectureRAGAccuracy(unittest.TestCase):
    def test_status_endpoint(self):
        req = urllib.request.Request(f"{BASE_URL}/api/status")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("gemini_configured"))
            self.assertTrue(data.get("deepgram_configured"))
            self.assertGreaterEqual(data.get("total_lessons_indexed", 0), 1)

    def test_all_benchmark_queries(self):
        for case in BENCHMARK_CASES:
            with self.subTest(case=case["id"]):
                payload = json.dumps({
                    "lesson_id": "masterclass_os_3hours",
                    "query": case["query"]
                }).encode("utf-8")
                
                req = urllib.request.Request(
                    f"{BASE_URL}/api/chat",
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                with urllib.request.urlopen(req, timeout=30) as resp:
                    self.assertEqual(resp.status, 200)
                    data = json.loads(resp.read().decode("utf-8"))

                # 1. Top chunk retrieval precision
                evidence = data.get("retrieved_evidence", [])
                self.assertGreater(len(evidence), 0)
                top_chunk = evidence[0]
                top_sec = top_chunk.get("start_seconds", 0)
                self.assertLessEqual(abs(top_sec - case["expected_sec"]), 60)

                # 2. Fact Groundedness
                answer = data.get("answer", "").lower()
                matched = [k for k in case["expected_keywords"] if k.lower() in answer]
                self.assertGreaterEqual(len(matched) / len(case["expected_keywords"]), 0.70)

                # 3. Timestamp alignment
                timestamps = data.get("video_timestamps", [])
                self.assertGreater(len(timestamps), 0)

if __name__ == "__main__":
    unittest.main()
