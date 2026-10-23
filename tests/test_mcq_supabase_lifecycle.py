import os
import sys
import json
import time

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.db_adapter import DBAdapter
from backend.assignment_engine import AssignmentEngine
from backend.config import Config
import requests

def test_mcq_lifecycle():
    print("=" * 70)
    print("VERIFYING SUPABASE MCQ & QUIZ ATTEMPT LIFECYCLE")
    print("=" * 70)

    db = DBAdapter()
    engine = AssignmentEngine(db)

    lesson_id = "lesson_9593572d"
    lesson = db.get_lesson(lesson_id)
    assert lesson is not None, f"Lesson {lesson_id} not found"

    print(f"[Target Lesson] ID: {lesson_id}, Title: {lesson.get('title')}")

    # 1. Generate or retrieve MCQs
    print("\n--- STEP 1: Generate / Retrieve MCQs ---")
    quiz = engine.generate_mcq_quiz(lesson_id, count=5)
    assert "questions" in quiz, "Quiz response must contain 'questions'"
    questions = quiz["questions"]
    print(f"Generated {len(questions)} MCQs for client.")
    assert len(questions) == 5, f"Expected 5 questions, got {len(questions)}"

    # Security check: Zero answer leakage
    for q in questions:
        assert "correct_answer" not in q, "SECURITY LEAK: correct_answer leaked to client!"
        assert "explanation" not in q, "SECURITY LEAK: explanation leaked to client!"

    print("Zero-answer leakage verified! All client questions are cheat-proof.")

    # 2. Verify Supabase course_quizzes Row
    print("\n--- STEP 2: Verifying Supabase course_quizzes Table ---")
    headers = {
        "apikey": Config.SUPABASE_KEY,
        "Authorization": f"Bearer {Config.SUPABASE_KEY}"
    }
    quiz_id = f"quiz_{lesson_id}"
    r_sb = requests.get(
        f"{Config.SUPABASE_URL}/rest/v1/course_quizzes?id=eq.{quiz_id}&select=*",
        headers=headers
    )
    assert r_sb.status_code == 200, f"Query failed: {r_sb.text}"
    rows = r_sb.json()
    assert len(rows) >= 1, "Quiz record not found in Supabase course_quizzes!"
    print("Found row in Supabase course_quizzes:")
    print("  ID:", rows[0].get("id"))
    print("  Course ID:", rows[0].get("course_id"))
    print("  Title:", rows[0].get("title"))
    print("  Questions in DB:", len(rows[0].get("questions") or []))

    # 3. Simulate Student Submission with numeric indices (0, 1, 2, 3)
    print("\n--- STEP 3: Student Answers Verification (Numeric Option Indices) ---")
    prof_res = requests.get(
        f"{Config.SUPABASE_URL}/rest/v1/profiles?limit=1&select=id",
        headers=headers
    )
    student_id = prof_res.json()[0]["id"]

    # Retrieve bank truth to test an accurate answer
    bank = db.get_mcq_bank(lesson_id)
    letter_to_idx = {"A": 0, "B": 1, "C": 2, "D": 3}
    first_q = bank[0]
    first_q_ans_idx = letter_to_idx.get(first_q.get("correct_answer", "A"), 0)

    simulated_answers = {
        str(first_q.get("id")): first_q_ans_idx,  # Correct index!
    }

    verify_result = engine.verify_mcq_answers(
        lesson_id=lesson_id,
        user_answers=simulated_answers,
        student_id=student_id
    )

    print("Verification Result:")
    print("  Score:", verify_result.get("score"), "Correct:", verify_result.get("correct"))
    print("  Total:", verify_result.get("total"), "Total Questions:", verify_result.get("total_questions"))
    print("  Percentage:", verify_result.get("percentage"))
    print("  Status:", verify_result.get("status"))

    assert verify_result.get("score") == 1, "Index 0/1/2/3 mapping failed to award correct score!"
    assert verify_result.get("correct") == 1, "Dual field 'correct' missing in result!"
    assert "results" in verify_result and len(verify_result["results"]) == 1

    first_res = verify_result["results"][0]
    assert first_res.get("is_correct") is True
    print("  First Question Explanation:", first_res.get("explanation")[:80], "...")

    # 4. Verify Supabase quiz_attempts Table
    print("\n--- STEP 4: Verifying Supabase quiz_attempts Row ---")
    r_att = requests.get(
        f"{Config.SUPABASE_URL}/rest/v1/quiz_attempts?quiz_id=eq.{quiz_id}&user_id=eq.{student_id}&order=completed_at.desc&limit=1",
        headers=headers
    )
    assert r_att.status_code == 200, f"Attempt query failed: {r_att.text}"
    att_rows = r_att.json()
    assert len(att_rows) >= 1, "Quiz attempt not saved in Supabase quiz_attempts!"
    print("Found row in Supabase quiz_attempts:")
    print("  Attempt ID:", att_rows[0].get("id"))
    print("  Quiz ID:", att_rows[0].get("quiz_id"))
    print("  User ID:", att_rows[0].get("user_id"))
    print("  Score in DB:", att_rows[0].get("score"))
    print("  Total Questions in DB:", att_rows[0].get("total_questions"))

    # Cleanup attempt
    requests.delete(f"{Config.SUPABASE_URL}/rest/v1/quiz_attempts?id=eq.{att_rows[0].get('id')}", headers=headers)
    print("Cleaned up temporary quiz attempt.")

    print("\n" + "=" * 70)
    print("ALL MCQ LIFECYCLE TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    test_mcq_lifecycle()
