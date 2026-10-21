import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import json
from fastapi.testclient import TestClient
from backend.app import app
from backend.config import Config

client = TestClient(app)

# Ensure sample OS lecture is loaded
client.post("/api/load-sample")

TEST_CASES = [
    {
        "id": "TC1_SIMPLE_FACTUAL",
        "category": "Simple Factual",
        "query": "What is the difference between preemptive and non-preemptive scheduling?",
        "expected_chunk_index": 1,
        "expected_keywords": ["preemptive", "interrupt"],
        "should_abstain": False
    },
    {
        "id": "TC2_EXACT_TIMESTAMP",
        "category": "Exact Timestamp (Hinglish)",
        "query": "03:10 par sir ne kya explain kiya tha?",
        "expected_chunk_index": 2,
        "expected_keywords": ["context switch", "registers"],
        "should_abstain": False
    },
    {
        "id": "TC3_TIME_INTERVAL",
        "category": "Time Interval (Hinglish)",
        "query": "5 se 8 minute ke beech kya discuss hua?",
        "expected_chunk_index": 3,
        "expected_keywords": ["round robin", "quantum"],
        "should_abstain": False
    },
    {
        "id": "TC4_HINGLISH_CONCEPTUAL",
        "category": "Hinglish Conceptual",
        "query": "Round robin me time quantum agar bahut chota ho jaye toh kya dikkat hoti hai?",
        "expected_chunk_index": 3,
        "expected_keywords": ["overhead", "context switch"],
        "should_abstain": False
    },
    {
        "id": "TC5_FORMULA_TECHNICAL",
        "category": "Technical Formula",
        "query": "Turnaround time calculate karne ka exact formula kya hai?",
        "expected_chunk_index": 4,
        "expected_keywords": ["completion", "arrival"],
        "should_abstain": False
    },
    {
        "id": "TC6_FOLLOW_UP",
        "category": "Follow-Up Pronoun",
        "initial_query": "Explain Round Robin scheduling.",
        "query": "Isme overhead kis wajah se aata hai?",
        "expected_chunk_index": 3,
        "expected_keywords": ["context switch", "quantum"],
        "should_abstain": False
    },
    {
        "id": "TC7_OUT_OF_SCOPE",
        "category": "Out-of-Scope (Abstention)",
        "query": "Python me binary search tree kaise implement karte hain?",
        "expected_chunk_index": None,
        "expected_keywords": ["not discussed", "not cover", "does not discuss", "nahi"],
        "should_abstain": True
    },
    {
        "id": "TC8_REVERSE_TEMPORAL",
        "category": "Reverse Temporal",
        "query": "At what time was the 80% rule of thumb explained?",
        "expected_chunk_index": 4,
        "expected_keywords": ["10:31", "80%"],
        "should_abstain": False
    }
]

def run_baseline_eval():
    results = []
    print("\n" + "="*80)
    print("RUNNING RAG EVALUATION SUITE")
    print("="*80)
    
    for tc in TEST_CASES:
        session_id = f"baseline_eval_{tc['id']}"
        start_t = time.time()
        
        # If follow-up test case, run initial query first
        if "initial_query" in tc:
            client.post("/api/chat", json={
                "lesson_id": "sample_os_scheduling",
                "session_id": session_id,
                "query": tc["initial_query"]
            })

        resp = client.post("/api/chat", json={
            "lesson_id": "sample_os_scheduling",
            "session_id": session_id,
            "query": tc["query"]
        })
        elapsed = round(time.time() - start_t, 3)

        if resp.status_code != 200:
            results.append({
                "id": tc["id"],
                "category": tc["category"],
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text}",
                "elapsed": elapsed
            })
            continue

        data = resp.json()
        answer = data.get("answer", "")
        evidence = data.get("retrieved_evidence", [])
        timestamps = data.get("video_timestamps", [])

        # Check retrieval relevance
        retrieved_chunk_indices = []
        for e in evidence:
            tlabel = e.get("timestamp_label", "")
            if "00:00" in tlabel: retrieved_chunk_indices.append(1)
            elif "02:06" in tlabel: retrieved_chunk_indices.append(2)
            elif "04:21" in tlabel: retrieved_chunk_indices.append(3)
            elif "10:31" in tlabel: retrieved_chunk_indices.append(4)

        retrieval_hit = False
        if tc["expected_chunk_index"] is not None:
            retrieval_hit = (tc["expected_chunk_index"] in retrieved_chunk_indices)
        else:
            # For out of scope, retrieval hit means abstention
            retrieval_hit = True

        # Check answer correctness / keywords
        ans_lower = answer.lower()
        keyword_hits = [k for k in tc["expected_keywords"] if k.lower() in ans_lower]
        keyword_ratio = len(keyword_hits) / max(1, len(tc["expected_keywords"]))
        
        # Abstention check
        abstention_ok = True
        if tc["should_abstain"]:
            abstention_ok = any(w in ans_lower for w in ["not discuss", "does not", "not covered", "nahi", "outside", "does not specifically"])

        is_passed = retrieval_hit and (keyword_ratio >= 0.5) and abstention_ok

        res_entry = {
            "id": tc["id"],
            "category": tc["category"],
            "query": tc["query"],
            "retrieval_hit": retrieval_hit,
            "retrieved_chunks": retrieved_chunk_indices,
            "keyword_hits": f"{len(keyword_hits)}/{len(tc['expected_keywords'])}",
            "abstention_ok": abstention_ok,
            "passed": is_passed,
            "latency_s": elapsed,
            "answer_preview": answer[:140].replace('\n', ' ')
        }
        results.append(res_entry)
        print(f"[{'PASS' if is_passed else 'FAIL'}] {tc['id']} ({tc['category']}) - {elapsed}s")
        if not is_passed:
            print(f"   Query: {tc['query']}")
            print(f"   Retrieved Chunks: {retrieved_chunk_indices} (Expected: {tc['expected_chunk_index']})")
            print(f"   Keyword Hits: {keyword_hits}")
            print(f"   Answer: {answer[:160]}...")

    print("\n" + "="*80)
    passed_count = sum(1 for r in results if r.get("passed"))
    print(f"SUMMARY: {passed_count}/{len(results)} Passed ({round(passed_count/len(results)*100, 1)}%)")
    print("="*80)
    
    with open("tests/baseline_eval_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_baseline_eval()
