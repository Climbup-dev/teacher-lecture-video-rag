import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)
client.post("/api/load-sample")

test_samples = [
    {
        "tier": "10M Micro-Lesson",
        "query": "3 minute 10 second par sir ne kya explain kiya tha?",
        "type": "Exact Timestamp (MM:SS)"
    },
    {
        "tier": "1H Standard Lecture",
        "query": "Round Robin me time quantum chhota rakhne se kya dikkat hoti hai?",
        "type": "Conceptual & Algorithm Trade-off"
    },
    {
        "tier": "2H Deep-Dive Class",
        "query": "Isme overhead kis wajah se aata hai?",
        "type": "Follow-Up with Antecedent Resolution"
    },
    {
        "tier": "4H Marathon Masterclass",
        "query": "At what time was the 80% rule of thumb explained and why?",
        "type": "Reverse Temporal with Jump Points"
    },
    {
        "tier": "All Durations (Abstention)",
        "query": "Python me binary search tree kaise implement karte hain?",
        "type": "Out-of-Scope (Strict Abstention)"
    }
]

print("="*80)
print("GENERATING REAL STUDENT QUESTION & ANSWER SAMPLES")
print("="*80)

# Pre-set session for follow-up test
client.post("/api/chat", json={
    "lesson_id": "sample_os_scheduling",
    "session_id": "demo_session",
    "query": "Explain Round Robin scheduling."
})

responses = []
for s in test_samples:
    sess = "demo_session" if "overhead" in s["query"] else f"eval_{int(time.time()*1000)%10000}"
    resp = client.post("/api/chat", json={
        "lesson_id": "sample_os_scheduling",
        "session_id": sess,
        "query": s["query"]
    })
    data = resp.json()
    sample_res = {
        "tier": s["tier"],
        "type": s["type"],
        "query": s["query"],
        "answer": data.get("answer"),
        "timestamps": data.get("video_timestamps"),
        "evidence_count": len(data.get("retrieved_evidence", []))
    }
    responses.append(sample_res)
    print(f"[{s['tier']}] Question: {s['query']}")
    print(f"  Type: {s['type']}")
    print(f"  Answer Preview: {data.get('answer', '')[:160]}...")
    print(f"  Video Timestamps Attached: {data.get('video_timestamps')}")
    print(f"  Retrieved Evidence Chunks: {len(data.get('retrieved_evidence', []))}")
    print("-" * 80)

with open("tests/live_qa_report_samples.json", "w", encoding="utf-8") as f:
    json.dump(responses, f, indent=2)

print("Saved samples to tests/live_qa_report_samples.json")
