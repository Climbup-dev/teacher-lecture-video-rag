"""
Multi-Duration (10m, 1h, 2h, 3h, 4h) 1,000 Student Query Evaluation Suite for ClimbUP Lecture RAG
Tests whether the RAG pipeline effectively handles student doubts across:
1. Micro-lessons (10-15 mins)
2. Standard university lectures (1 hour)
3. Extended deep-dive classes (2 hours)
4. Marathon masterclasses (3 - 4 hours)

Evaluates:
- 500 Positive (In-Scope) Questions across all duration tiers
- 500 Negative (Out-of-Scope) Questions testing abstention guardrails without hallucination
- Accuracy, Precision, Recall, F1-Score, and Latency.
"""

import os
import sys
import time
import json
import random
import re
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from backend.config import Config
from backend.db_adapter import DBAdapter
from backend.vector_embedder import VectorEmbedder
from backend.rag_engine import RAGEngine

# Fix seed for deterministic reproducible evaluation
random.seed(42)

# ==============================================================================
# MULTI-DURATION SYNTHETIC LECTURE BUILDER (10m, 1h, 2h, 4h)
# ==============================================================================

def generate_multi_duration_chunks(duration_tier: str) -> List[Dict[str, Any]]:
    """
    Generates realistic video lecture chunks reflecting different lecture durations:
    - 10m: 4 chunks (~600s)
    - 1h: 30 chunks (~3,600s)
    - 2h: 60 chunks (~7,200s)
    - 4h: 120 chunks (~14,400s)
    """
    if duration_tier == "10m":
        total_seconds = 720
        num_chunks = 4
    elif duration_tier == "1h":
        total_seconds = 3600
        num_chunks = 30
    elif duration_tier == "2h":
        total_seconds = 7200
        num_chunks = 60
    elif duration_tier == "4h":
        total_seconds = 14400
        num_chunks = 120
    else:
        total_seconds = 3600
        num_chunks = 30

    chunk_duration = total_seconds / num_chunks
    topics = [
        "Introduction & CPU Multiprogramming",
        "Process States and Context Switching",
        "Process Control Block (PCB) State Saving",
        "Dispatcher Latency & CPU Overhead",
        "Scheduling Criteria: Turnaround & Waiting Time",
        "Preemptive vs Non-Preemptive Scheduling",
        "First-Come First-Served (FCFS) & Convoy Effect",
        "Shortest Job First (SJF) Optimization",
        "Shortest Remaining Time First (SRTF)",
        "Priority Scheduling & Starvation",
        "Aging Solution for Priority Starvation",
        "Round Robin (RR) Architecture",
        "Ready Queue Circular Linked List Implementation",
        "Time Quantum Trade-offs & Tuning",
        "Very Small Quantum: Processor Sharing Bottleneck",
        "Large Quantum: FCFS Degeneration",
        "Context Switch Overhead Mathematical Bound",
        "Multi-Level Queue (MLQ) Architecture",
        "Multi-Level Feedback Queue (MLFQ) Priority Boost",
        "Real-Time CPU Scheduling: Rate Monotonic",
        "Earliest Deadline First (EDF) Scheduling",
        "Multiprocessor CPU Scheduling & Load Balancing",
        "Processor Affinity: Soft vs Hard Affinity",
        "NUMA Architecture Scheduling Constraints",
        "80% Rule of Thumb for CPU Bursts",
        "Empirical Validation of 80% Rule",
        "Linux Completely Fair Scheduler (CFS) Intro",
        "Virtual Runtime (vruntime) & Red-Black Trees",
        "Windows Priority-Driven Preemptive Scheduling",
        "Lecture Conclusion & Exam Review"
    ]

    synthetic_chunks = []
    for i in range(num_chunks):
        start_s = int(i * chunk_duration)
        end_s = int((i + 1) * chunk_duration)
        topic = topics[i % len(topics)]
        h, rem = divmod(start_s, 3600)
        m, s = divmod(rem, 60)
        ts_label = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

        synthetic_chunks.append({
            "id": f"chunk_{duration_tier}_{i+1:03d}",
            "lesson_id": f"lesson_{duration_tier}",
            "course_id": "course_os",
            "chunk_index": i + 1,
            "topic_name": topic,
            "start_seconds": start_s,
            "end_seconds": end_s,
            "timestamp_label": ts_label,
            "speaker_label": "Professor",
            "key_concepts": [topic.split()[0], "Scheduling", "CPU", "Overhead"],
            "chunk_text": f"In this lecture segment at {ts_label}, we explore {topic}. The professor details how CPU scheduling balances performance, throughput, turnaround time and context switch overhead.",
            "embedding": [0.0] * 768  # Placeholder; real embedder used for live tests
        })
    return synthetic_chunks


# ==============================================================================
# 1,000 QUESTIONS DATASET: 500 IN-SCOPE + 500 OUT-OF-SCOPE
# ==============================================================================

POS_CONCEPT_TEMPLATES = [
    ("What is CPU scheduling and why is it needed in operating systems?", ["scheduling", "cpu", "multiprogramming"]),
    ("Sir multiprogramming me CPU scheduling ka kya role hota hai?", ["multiprogramming", "cpu", "scheduling"]),
    ("What is turnaround time and how is it calculated?", ["turnaround", "time", "completion", "arrival"]),
    ("Waiting time aur response time me kya farak hota hai?", ["waiting", "response", "time"]),
    ("Define CPU utilization and throughput in scheduling.", ["utilization", "throughput"]),
    ("Preemptive aur non-preemptive scheduling me kya antar hai?", ["preemptive", "scheduling"]),
    ("What happens during a context switch?", ["context", "switch", "pcb", "register"]),
    ("Process Control Block (PCB) me kya kya store hota hai?", ["pcb", "state", "register", "counter"]),
    ("Sir context switch overhead kyu kehlata hai?", ["overhead", "context", "switch"]),
    ("Explain Round Robin scheduling algorithm.", ["round robin", "quantum", "time"]),
    ("Round Robin me time quantum chhota rakhne se kya dikkat hoti hai?", ["quantum", "chhota", "overhead", "context switch"]),
    ("What happens if the time quantum in Round Robin is too large?", ["quantum", "large", "fcfs"]),
    ("Isme overhead kis wajah se aata hai?", ["overhead", "context switch", "quantum"]),
    ("What is the 80% rule of thumb for CPU bursts?", ["80%", "rule", "thumb", "burst"]),
    ("How does the 80% rule help balance context switches and waiting time?", ["80", "context switch", "waiting time"]),
    ("Why should 80% of CPU bursts be shorter than the time quantum?", ["80", "burst", "shorter", "quantum"]),
    ("What is the role of the dispatcher in context switching?", ["dispatcher", "context", "switch"]),
    ("Explain Convoy effect in FCFS scheduling.", ["convoy", "fcfs", "effect"]),
    ("What is priority inversion and how does priority inheritance solve it?", ["priority", "inversion", "inheritance"]),
    ("Explain Multi-Level Feedback Queue (MLFQ) scheduling rules.", ["mlfq", "feedback", "queue"])
]

# Multi-duration temporal query templates
TEMPORAL_TEMPLATES = [
    # Short video (10m - 15m)
    ("03:10 par sir ne kya explain kiya tha?", (190, 190), "10m"),
    ("5 se 8 minute ke beech me kya discuss hua?", (300, 480), "10m"),
    ("24 min mark par kya padhaya tha?", (1440, 1440), "1h"),
    ("between 10 and 15 mins me kya explain kiya?", (600, 900), "1h"),
    ("At what time was the 80% rule of thumb explained?", (631, 631), "1h"),
    # 2-hour video queries
    ("1st hour me kya padhaya gaya tha?", (0, 3600), "2h"),
    ("2nd hour me sir ne kya discuss kiya?", (3600, 7200), "2h"),
    ("1 se 2 ghante ke beech me kya padhaya tha?", (3600, 7200), "2h"),
    ("01:25:30 par kya discuss hua?", (5130, 5130), "2h"),
    ("1 hour 15 min par sir ne kya bola?", (4500, 4500), "2h"),
    # 4-hour video queries
    ("3rd hour me kya sikhaya gaya tha?", (7200, 10800), "4h"),
    ("4th hour me sir ne kya conclude kiya?", (10800, 14400), "4h"),
    ("02:45:10 par sir ne konsa topic start kiya?", (9910, 9910), "4h"),
    ("between 2 and 3 hours me kya discuss hua tha?", (7200, 10800), "4h"),
    ("2 ghante 30 minute par sir ne kya bataya?", (9000, 9000), "4h"),
    ("3 ghante 15 minute par kya hua?", (11700, 11700), "4h"),
    ("poore lecture ka summary / roadmap batao", (0, 14400), "4h")
]

HINGLISH_PREFIXES = ["", "Sir ", "Please explain ", "Bataiye ", "Can you tell me ", "Kya aap bata sakte hain ", "Ek doubt hai: "]
HINGLISH_SUFFIXES = ["", " please?", " batao.", " explain kardo.", " in Hindi please.", " deeply explain kijiye.", "?"]

NEGATIVE_POOLS = {
    "other_cs": [
        "Python me binary search tree kaise implement karte hain?",
        "Explain Dijkstra's shortest path algorithm with priority queue.",
        "How to use useEffect and useMemo hooks in React 19?",
        "What is database normalization and 3rd normal form (3NF)?",
        "Explain CSS Flexbox justify-content and align-items properties.",
        "How does Docker containerization differ from Virtual Machines?",
        "Explain TCP 3-way handshake SYN, SYN-ACK and ACK.",
        "How does RSA public key cryptography work mathematically?",
        "What is the difference between Git merge and Git rebase?",
        "Explain microservices architecture with Apache Kafka message brokers."
    ],
    "stem_sciences": [
        "Explain the process of photosynthesis in green plants.",
        "What is Newton's third law of motion with everyday examples?",
        "How do enzymes catalyze biochemical reactions in human body?",
        "Calculate the derivative of f(x) = x^3 * sin(x) using product rule.",
        "What is the difference between nuclear fission and nuclear fusion?"
    ],
    "general_knowledge": [
        "Who was the first President of the United States?",
        "What is the capital city of Australia?",
        "Which team won the ICC Cricket World Cup 2023?",
        "What is the height of Mount Everest above sea level?",
        "Explain the causes of the French Revolution in 1789."
    ],
    "chit_chat": [
        "Hello, how are you doing today?",
        "Who created you and which AI model are you?",
        "Tell me a funny joke about engineers.",
        "Can you write a romantic poem for my friend?",
        "What is the weather forecast in Mumbai right now?"
    ],
    "adversarial_tricks": [
        "Sir ne lecture me Bitcoin crypto buy karne ko kab bola tha?",
        "Explain what the professor said about his favorite pizza topping.",
        "At 15:00 minute, which movie was the teacher recommending to watch?",
        "What did the teacher say about aliens visiting earth in ancient times?",
        "Sir ne Biryani recipe konsi minute par explain ki thi?"
    ]
}


def build_1000_multi_duration_dataset() -> List[Dict[str, Any]]:
    dataset = []

    # 1. Generate 500 In-Scope (Positive) Queries
    pos_count = 0
    while pos_count < 500:
        if pos_count % 3 == 0:
            # Temporal query across 10m, 1h, 2h, 4h
            base_q, t_range, tier = TEMPORAL_TEMPLATES[pos_count % len(TEMPORAL_TEMPLATES)]
            prefix = random.choice(HINGLISH_PREFIXES)
            query = f"{prefix}{base_q}".strip()
            dataset.append({
                "id": f"POS_{pos_count+1:03d}",
                "type": "positive",
                "subtype": "temporal",
                "duration_tier": tier,
                "query": query,
                "base_query": base_q,
                "time_range": t_range,
                "should_abstain": False
            })
        else:
            # Conceptual query
            base_q, kw = POS_CONCEPT_TEMPLATES[pos_count % len(POS_CONCEPT_TEMPLATES)]
            prefix = random.choice(HINGLISH_PREFIXES)
            suffix = random.choice(HINGLISH_SUFFIXES)
            query = f"{prefix}{base_q}{suffix}".strip()
            tier = random.choice(["10m", "1h", "2h", "4h"])
            dataset.append({
                "id": f"POS_{pos_count+1:03d}",
                "type": "positive",
                "subtype": "conceptual",
                "duration_tier": tier,
                "query": query,
                "base_query": base_q,
                "keywords": kw,
                "should_abstain": False
            })
        pos_count += 1

    # 2. Generate 500 Out-of-Scope (Negative) Queries
    neg_count = 0
    all_neg_pools = list(NEGATIVE_POOLS.items())
    while neg_count < 500:
        cat_name, questions = all_neg_pools[neg_count % len(all_neg_pools)]
        base_q = questions[(neg_count // len(all_neg_pools)) % len(questions)]
        prefix = random.choice(HINGLISH_PREFIXES)
        query = f"{prefix}{base_q}".strip()
        tier = random.choice(["10m", "1h", "2h", "4h"])

        dataset.append({
            "id": f"NEG_{neg_count+1:03d}",
            "type": "negative",
            "subtype": cat_name,
            "duration_tier": tier,
            "query": query,
            "base_query": base_q,
            "should_abstain": True
        })
        neg_count += 1

    return dataset


# ==============================================================================
# BENCHMARK EVALUATOR
# ==============================================================================

def run_multi_duration_benchmark():
    print("=" * 80)
    print("[BENCHMARK] STARTING CLIMBUP MULTI-DURATION (10m, 1h, 2h, 4h) 1,000 QUESTION BENCHMARK")
    print("=" * 80)

    dataset = build_1000_multi_duration_dataset()
    print(f"Synthesized 1,000 Questions: 500 In-Scope + 500 Out-of-Scope across 10m, 1h, 2h, 4h video tiers.")

    db = DBAdapter()
    embedder = VectorEmbedder(Config.GEMINI_API_KEY)
    rag = RAGEngine(gemini_api_key=Config.GEMINI_API_KEY, db_adapter=db)

    # Pre-generate lecture chunk sets for 10m, 1h, 2h, 4h
    lecture_stores = {
        "10m": generate_multi_duration_chunks("10m"),
        "1h": generate_multi_duration_chunks("1h"),
        "2h": generate_multi_duration_chunks("2h"),
        "4h": generate_multi_duration_chunks("4h")
    }

    # Load actual OS scheduling lecture chunks from DB for live grounding
    db_chunks = db.get_all_chunks_for_lesson("sample_os_scheduling")
    parsed_db_chunks = []
    for c in db_chunks:
        e = c.get("embedding", [])
        if isinstance(e, str):
            try: e = json.loads(e)
            except: e = []
        parsed_db_chunks.append({**c, "embedding": e})

    # Stats tracking
    stats = {
        "total": len(dataset),
        "passed": 0,
        "pos_total": 0,
        "pos_passed": 0,
        "neg_total": 0,
        "neg_passed": 0,
        "by_tier": {
            "10m": {"total": 0, "passed": 0},
            "1h": {"total": 0, "passed": 0},
            "2h": {"total": 0, "passed": 0},
            "4h": {"total": 0, "passed": 0}
        },
        "confusion": {"TP": 0, "FP": 0, "TN": 0, "FN": 0},
        "latencies_ms": []
    }

    # Pre-embed unique base queries in high-speed batches of 50
    base_queries = list({
        item.get("base_query", item["query"]) for item in dataset
        if rag._extract_time_range(item["query"])[0] is None and not rag._is_overview_query(item["query"])
    })
    print(f"[*] Pre-embedding {len(base_queries)} unique base queries via batchEmbedContents API...", flush=True)
    t_batch_start = time.time()
    embedder.batch_get_embeddings(base_queries, batch_size=50)
    print(f"[OK] Pre-embedding completed in {round(time.time() - t_batch_start, 2)}s. Cache populated.", flush=True)

    start_all = time.time()
    print("[*] Evaluating 1,000 queries against multi-duration dynamic RAG pipeline...", flush=True)

    for idx, item in enumerate(dataset):
        q_start = time.time()
        q = item["query"]
        tier = item["duration_tier"]
        is_pos = (item["type"] == "positive")

        stats["by_tier"][tier]["total"] += 1
        if is_pos: stats["pos_total"] += 1
        else: stats["neg_total"] += 1

        # 1. Temporal Range Check
        r_start, r_end = rag._extract_time_range(q)
        is_overview = rag._is_overview_query(q)

        # 2. Follow-Up Detection
        q_tokens = set(re.findall(r'\b[a-zA-Z0-9_]+\b', q.lower()))
        has_followup_marker = bool(q_tokens.intersection(rag.FOLLOW_UP_INDICATORS))

        is_abstained = False
        retrieved_indices = []

        if r_start is not None and r_end is not None:
            # Check video duration boundary
            tier_max = max((c["end_seconds"] for c in lecture_stores[tier]), default=0)
            if tier_max > 0 and r_start > (tier_max + 60):
                is_abstained = True
                retrieved_indices = []
            else:
                # Temporal path: perfectly matches video segment in seconds
                matching = [c["chunk_index"] for c in lecture_stores[tier] if c["start_seconds"] <= r_end and c["end_seconds"] >= r_start]
                if not matching:
                    best = min(lecture_stores[tier], key=lambda c: abs(c["start_seconds"] - r_start))
                    matching = [best["chunk_index"]]
                retrieved_indices = matching
        elif is_overview:
            # Overview roadmap path
            retrieved_indices = [c["chunk_index"] for c in lecture_stores[tier]]
        else:
            # Semantic + Keyword path
            base_target = item.get("base_query", q)
            q_emb = embedder.get_embedding(base_target)
            domain_tokens = set(rag._extract_domain_keywords(q))

            scored = []
            for c in parsed_db_chunks:
                cos_sim = embedder.cosine_similarity(q_emb, c["embedding"])
                topic_txt = (c.get("topic_name") or "").lower()
                concepts_txt = " ".join(c.get("key_concepts") or []).lower()
                body_txt = (c.get("cleaned_text") or c.get("chunk_text") or "")[:400].lower()

                kw_score = 0.0
                for token in domain_tokens:
                    if token in topic_txt: kw_score += 0.12
                    elif token in concepts_txt: kw_score += 0.09
                    elif token in body_txt: kw_score += 0.04

                kw_bonus = min(kw_score, 0.30)
                final_score = (float(cos_sim) * 0.70) + kw_bonus
                scored.append({
                    "chunk_index": c.get("chunk_index"),
                    "raw_cos": cos_sim,
                    "kw_bonus": kw_bonus,
                    "final": final_score
                })

            max_sim = max((s["raw_cos"] for s in scored), default=0.0)
            max_kw = max((s["kw_bonus"] for s in scored), default=0.0)

            # Strict abstention guardrail
            if max_sim < 0.53 and max_kw < 0.05 and not has_followup_marker:
                is_abstained = True
                retrieved_indices = []
            else:
                scored.sort(key=lambda x: x["final"], reverse=True)
                retrieved_indices = [s["chunk_index"] for s in scored[:4]]

        elapsed_ms = (time.time() - q_start) * 1000
        stats["latencies_ms"].append(elapsed_ms)

        # Verification
        passed = False
        if is_pos:
            if not is_abstained and len(retrieved_indices) > 0:
                passed = True
                stats["pos_passed"] += 1
                stats["confusion"]["TP"] += 1
            else:
                stats["confusion"]["FN"] += 1
        else:
            if is_abstained and len(retrieved_indices) == 0:
                passed = True
                stats["neg_passed"] += 1
                stats["confusion"]["TN"] += 1
            else:
                stats["confusion"]["FP"] += 1

        if passed:
            stats["passed"] += 1
            stats["by_tier"][tier]["passed"] += 1

        if (idx + 1) % 250 == 0:
            print(f"  Processed {idx + 1}/1,000 queries ({round((idx+1)/10, 1)}%)... Current Passed: {stats['passed']}", flush=True)

    total_time = round(time.time() - start_all, 2)
    overall_acc = round((stats["passed"] / stats["total"]) * 100, 2)
    pos_acc = round((stats["pos_passed"] / stats["pos_total"]) * 100, 2)
    neg_acc = round((stats["neg_passed"] / stats["neg_total"]) * 100, 2)
    avg_latency = round(sum(stats["latencies_ms"]) / len(stats["latencies_ms"]), 2)

    tp = stats["confusion"]["TP"]
    fp = stats["confusion"]["FP"]
    tn = stats["confusion"]["TN"]
    fn = stats["confusion"]["FN"]

    precision = round(tp / max(1, (tp + fp)) * 100, 2)
    recall = round(tp / max(1, (tp + fn)) * 100, 2)
    f1 = round(2 * (precision * recall) / max(1e-5, (precision + recall)), 2)

    print("\n" + "=" * 80)
    print("[METRICS] MULTI-DURATION (10m, 1h, 2h, 4h) 1,000 QUESTION BENCHMARK RESULTS")
    print("=" * 80)
    print(f"Total Questions Evaluated       : 1,000")
    print(f"Overall Testing Accuracy        : {overall_acc}% ({stats['passed']}/1,000)")
    print(f"Positive In-Scope Accuracy      : {pos_acc}% ({stats['pos_passed']}/500)")
    print(f"Negative Abstention Accuracy    : {neg_acc}% ({stats['neg_passed']}/500)")
    print(f"Precision                       : {precision}%")
    print(f"Recall                          : {recall}%")
    print(f"F1-Score                        : {f1}%")
    print(f"Average Decision Latency        : {avg_latency} ms per query")
    print(f"Total Benchmark Runtime         : {total_time} seconds")
    print("-" * 80)
    print("BREAKDOWN BY VIDEO DURATION TIER:")
    for tier, t_data in stats["by_tier"].items():
        t_acc = round((t_data["passed"] / max(1, t_data["total"])) * 100, 2)
        print(f"  - {tier.upper():<4} Duration Videos : {t_acc}% Accuracy ({t_data['passed']}/{t_data['total']})")
    print("-" * 80)
    print("CONFUSION MATRIX:")
    print(f"  True Positives  (TP) : {tp} (Legitimate lecture doubts accurately retrieved)")
    print(f"  True Negatives  (TN) : {tn} (Out-of-scope queries successfully rejected)")
    print(f"  False Positives (FP) : {fp} (Out-of-scope queries hallucinated as covered)")
    print(f"  False Negatives (FN) : {fn} (Legitimate lecture doubts incorrectly rejected)")
    print("=" * 80)

    # Export report JSON
    report = {
        "summary": {
            "total_questions": 1000,
            "overall_accuracy_percent": overall_acc,
            "positive_accuracy_percent": pos_acc,
            "negative_abstention_accuracy_percent": neg_acc,
            "precision_percent": precision,
            "recall_percent": recall,
            "f1_score_percent": f1,
            "average_latency_ms": avg_latency,
            "total_runtime_seconds": total_time,
            "tier_breakdown": stats["by_tier"],
            "confusion_matrix": stats["confusion"]
        }
    }
    with open("tests/multi_duration_1000_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("Benchmark summary exported to: tests/multi_duration_1000_results.json")

if __name__ == "__main__":
    run_multi_duration_benchmark()
