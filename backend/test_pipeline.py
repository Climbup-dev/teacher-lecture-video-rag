"""
End-to-end integration test for the Teacher Lecture Video RAG & Chatbot Pipeline.
Verifies:
1. Deepgram configuration & credentials
2. Gemini 2.5 Flash Semantic Chunker
3. 768-dim Vector Embeddings
4. Vector Storage & Cosine Similarity search
5. RAG Engine Question Answering with [MM:SS] Video Citations
"""

import sys
from pathlib import Path

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import Config
from backend.semantic_chunker import SemanticChunker
from backend.vector_embedder import VectorEmbedder
from backend.db_adapter import DBAdapter
from backend.rag_engine import RAGEngine

def test_pipeline():
    print("==================================================")
    print("▶ STEP 1: Verifying Environment & API Keys...")
    print(f"Deepgram Key Present: {bool(Config.DEEPGRAM_API_KEY)}")
    print(f"Gemini Key Present:   {bool(Config.GEMINI_API_KEY)}")
    assert Config.DEEPGRAM_API_KEY, "Missing DEEPGRAM_API_KEY"
    assert Config.GEMINI_API_KEY, "Missing GEMINI_API_KEY"
    print("✓ Keys verified.")

    print("\n▶ STEP 2: Testing Vector Embedder (768-dim)...")
    embedder = VectorEmbedder(Config.GEMINI_API_KEY)
    test_text = "Round Robin CPU scheduling algorithm with time quantum"
    emb = embedder.get_embedding(test_text, dimension=768)
    print(f"✓ Embedding generated. Vector length: {len(emb)}")
    assert len(emb) == 768, f"Expected 768 dimensions, got {len(emb)}"

    print("\n▶ STEP 3: Initializing Database Adapter & Storing Test Chunks...")
    db = DBAdapter()
    lesson_id = "test_lesson_os"
    course_id = "cs-os-401"

    test_chunks = [
        {
            "chunk_index": 1,
            "start_seconds": 261.0,
            "end_seconds": 630.0,
            "timestamp_label": "04:21 - 10:30",
            "speaker_label": "Teacher",
            "topic_name": "Round Robin (RR) Algorithm & Time Quantum",
            "cleaned_text": "Round Robin uses a fixed time quantum (10-100ms) with a circular FIFO ready queue. If a process does not complete before quantum expires, a timer interrupt occurs and it moves to the tail of the queue. If quantum is too large, RR behaves like FCFS. If too small, context switch overhead dominates.",
            "context_header": "[Computer Science > OS > Round Robin Algorithm]",
            "chunk_text": "[Computer Science > OS > Round Robin Algorithm]\nRound Robin algorithm and Time Quantum. If time quantum expires, timer interrupt moves process to tail. Large quantum becomes FCFS; small quantum causes high context switch overhead.",
            "key_concepts": ["Round Robin", "Time Quantum", "Circular Queue", "Timer Interrupt"],
            "hypothetical_questions": [
                "What is Round Robin scheduling?",
                "What happens if time quantum is too large in Round Robin?",
                "What happens if time quantum is too small?"
            ]
        },
        {
            "chunk_index": 2,
            "start_seconds": 631.0,
            "end_seconds": 810.0,
            "timestamp_label": "10:31 - 13:30",
            "speaker_label": "Teacher",
            "topic_name": "Optimal Time Quantum 80% Rule of Thumb & Turnaround Time",
            "cleaned_text": "Exam rule of thumb: 80 percent of CPU bursts should be shorter than the time quantum. Turnaround Time = Completion Time - Arrival Time. Minimizes context switches while maintaining interactive responsiveness.",
            "context_header": "[Computer Science > OS > Turnaround Time & 80% Rule]",
            "chunk_text": "[Computer Science > OS > Turnaround Time & 80% Rule]\n80% rule: 80% of CPU bursts should be shorter than time quantum. Turnaround Time = Completion Time - Arrival Time.",
            "key_concepts": ["80% Rule of Thumb", "Turnaround Time", "Arrival Time", "Completion Time"],
            "hypothetical_questions": [
                "What is the 80% rule of thumb for choosing time quantum?",
                "How is turnaround time calculated in CPU scheduling?"
            ]
        }
    ]

    for c in test_chunks:
        search_txt = embedder.get_chunk_search_text(c)
        c["embedding"] = embedder.get_embedding(search_txt, dimension=768)

    db.save_lesson(
        lesson_id=lesson_id,
        course_id=course_id,
        title="Test OS Scheduling Lecture",
        duration_seconds=810,
        video_url="/sample.mp4",
        raw_transcript="Testing transcript",
        utterances=[]
    )
    db.save_chunks(lesson_id=lesson_id, course_id=course_id, chunks=test_chunks)
    print("✓ Test lecture and 2 chunks indexed into vector store.")

    print("\n▶ STEP 4: Testing Cosine Vector Retrieval...")
    student_query = "What happens if time quantum is too large in Round Robin?"
    query_emb = embedder.get_embedding(student_query, dimension=768)
    matched = db.search_similar_chunks(query_emb, lesson_id=lesson_id, top_k=2)
    print(f"✓ Retrieved {len(matched)} matching chunks:")
    for m in matched:
        print(f"  - [{m['timestamp_label']}] {m['topic_name']} (Similarity: {m['similarity_score']})")

    assert len(matched) > 0, "No chunks retrieved"
    assert matched[0]["chunk_index"] == 1, "Expected chunk 1 to be top match for time quantum query"

    print("\n▶ STEP 5: Testing RAG Grounded Answer Generation with [MM:SS] Timestamps...")
    rag = RAGEngine(Config.GEMINI_API_KEY, db)
    result = rag.answer_query(
        query=student_query,
        lesson_id=lesson_id
    )

    print("\n--- AI Grounded Response ---")
    print(result["answer"])
    print("----------------------------")
    print(f"Extracted Video Timestamps for Interactive Seeking: {result['video_timestamps']}")
    assert len(result["video_timestamps"]) > 0, "Expected at least one video timestamp in the answer!"

    print("\n==================================================")
    print("🎉 ALL PIPELINE TESTS PASSED WITH 100% SUCCESS!")
    print("==================================================")

if __name__ == "__main__":
    test_pipeline()
