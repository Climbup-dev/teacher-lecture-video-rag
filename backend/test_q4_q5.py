import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import Config
from backend.db_adapter import DBAdapter
from backend.rag_engine import RAGEngine

db = DBAdapter()
rag = RAGEngine(Config.GEMINI_API_KEY, db)
lesson_id = 'masterclass_os_3hours'

print("=" * 65)
print("TESTING Q4 (Hour 3 - Deadlocks & Banker's Algorithm)...")
q4 = "How does the Banker's Algorithm prevent deadlocks, and what are the 4 Coffman conditions explained by the professor?"
res4 = rag.answer_query(q4, lesson_id)
print("\n[Q4 ANSWER]:")
print(res4['answer'])
print("\n[Q4 TIMESTAMPS]:", res4['video_timestamps'])

print("\n" + "=" * 65)
print("TESTING Q5 (Hour 3 - Virtual Memory & TLB Paging)...")
q5 = "How does Translation Lookaside Buffer (TLB) paging reduce memory access overhead in virtual memory systems?"
res5 = rag.answer_query(q5, lesson_id)
print("\n[Q5 ANSWER]:")
print(res5['answer'])
print("\n[Q5 TIMESTAMPS]:", res5['video_timestamps'])
print("=" * 65)
