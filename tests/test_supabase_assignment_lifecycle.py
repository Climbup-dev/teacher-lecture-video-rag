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

def test_supabase_lifecycle():
    print("=" * 70)
    print("VERIFYING SUPABASE ASSIGNMENT & CHECKED SUBMISSION LIFECYCLE")
    print("=" * 70)

    db = DBAdapter()
    engine = AssignmentEngine(db)

    # Pick an existing lesson
    lesson_id = "lesson_9593572d"
    lesson = db.get_lesson(lesson_id)
    assert lesson is not None, f"Lesson {lesson_id} not found"
    course_id = lesson.get("course_id")
    print(f"[1] Target Course: {course_id}, Target Lesson: {lesson_id}")

    # 1. Admin creates / generates an assignment
    print("\n--- STEP 1: Creating Assignment ---")
    assignment_id = f"assign_test_{int(time.time())}"
    raw_assignment = {
        "id": assignment_id,
        "lesson_id": lesson_id,
        "course_id": course_id,
        "title": "Python Data Mastery: Automated ETL Pipeline",
        "scenario_context": "Fintech Transaction Ingestion Engine",
        "description": "Design an automated ETL pipeline handling dirty transaction payloads.",
        "starter_code": "def process_transactions(records):\n    # TODO\n    return []\n",
        "max_score": 100,
        "due_date": "2026-11-20",
        "status": "draft",
        "problems": [
            {
                "problem_number": 1,
                "tier": "Basic",
                "marks": 25,
                "problem_statement": "Validate account numbers and non-negative balance.",
                "acceptance_criteria": ["Raise ValueError on invalid balance", "Format checking"],
                "expected_deliverable": "Validation function"
            },
            {
                "problem_number": 2,
                "tier": "Intermediate",
                "marks": 35,
                "problem_statement": "Transform currency records with current exchange rates.",
                "acceptance_criteria": ["Linear time complexity O(N)", "Precision decimal rounding"],
                "expected_deliverable": "Transformation generator"
            },
            {
                "problem_number": 3,
                "tier": "Advanced",
                "marks": 40,
                "problem_statement": "Implement idempotent deduplication across concurrent batches.",
                "acceptance_criteria": ["Zero duplicate transactions", "Thread-safe state tracking"],
                "expected_deliverable": "Deduplicator pipeline class"
            }
        ],
        "rubric": {
            "logic_and_correctness": 50,
            "syntax_and_quality": 25,
            "edge_cases": 15,
            "approach_clarity": 10
        }
    }

    saved = db.save_assignment(raw_assignment)
    print("Saved Assignment ID:", saved.get("id"))
    assert saved.get("id") == assignment_id, "Assignment ID mismatch"

    # 2. Check directly in Supabase course_assignments via REST API
    print("\n--- STEP 2: Verifying Direct Supabase course_assignments Row ---")
    headers = {
        "apikey": Config.SUPABASE_KEY,
        "Authorization": f"Bearer {Config.SUPABASE_KEY}"
    }
    r_sb = requests.get(
        f"{Config.SUPABASE_URL}/rest/v1/course_assignments?id=eq.{assignment_id}&select=*",
        headers=headers
    )
    assert r_sb.status_code == 200, f"Supabase query failed: {r_sb.text}"
    rows = r_sb.json()
    assert len(rows) == 1, "Assignment row not found in Supabase course_assignments!"
    sb_row = rows[0]
    print("Found row in Supabase course_assignments:")
    print("  ID:", sb_row.get("id"))
    print("  Course ID:", sb_row.get("course_id"))
    print("  Title:", sb_row.get("title"))
    print("  Starter Code Length:", len(sb_row.get("starter_code") or ""))
    print("  Instructions Count:", len(sb_row.get("instructions") or []))

    # 3. Fetch via db.get_assignment_by_id and db.get_assignment_by_lesson
    print("\n--- STEP 3: Verifying DBAdapter Fetch ---")
    fetched = db.get_assignment_by_id(assignment_id)
    assert fetched is not None, "get_assignment_by_id returned None"
    assert len(fetched.get("problems", [])) == 3, "Problems array not unpacked properly"
    assert fetched.get("scenario_context") == "Fintech Transaction Ingestion Engine"
    print("Unpacked Problems:", len(fetched.get("problems")))
    print("Unpacked Scenario:", fetched.get("scenario_context"))

    # 4. Admin updates & publishes assignment
    print("\n--- STEP 4: Admin Publishes Assignment ---")
    publish_res = db.update_assignment(assignment_id, {"status": "published", "title": "Published ETL Pipeline"})
    assert publish_res is True, "Failed to update assignment status"

    pub_fetched = db.get_assignment_by_lesson(lesson_id, status="published")
    assert pub_fetched is not None, "get_assignment_by_lesson published returned None"
    assert pub_fetched.get("status") == "published"
    print("Published Assignment Verified from Supabase! Status:", pub_fetched.get("status"))

    # 5. AI Evaluation and Submission Storage (Checking Assignment)
    print("\n--- STEP 5: Student Submits & AI Grades Assignment ---")
    # Get a valid profile user for FK constraint
    prof_res = requests.get(
        f"{Config.SUPABASE_URL}/rest/v1/profiles?limit=1&select=id,email",
        headers=headers
    )
    user_id = prof_res.json()[0]["id"]
    user_email = prof_res.json()[0]["email"]

    student_code = """
def process_transactions(records):
    seen = set()
    valid = []
    for r in records:
        if r.get('balance', 0) < 0:
            raise ValueError('Negative balance')
        tx_id = r.get('id')
        if tx_id not in seen:
            seen.add(tx_id)
            valid.append(r)
    return valid
"""
    graded_eval = engine.evaluate_submission(
        assignment_id=assignment_id,
        student_id=user_id,
        student_name="Test Candidate",
        student_email=user_email,
        submission_code=student_code,
        approach_notes="Used set for O(1) deduplication and early validation."
    )

    print("Graded Submission:")
    print("  Submission ID:", graded_eval.get("id"))
    print("  AI Score:", graded_eval.get("ai_score") or graded_eval.get("score"))
    print("  Status:", graded_eval.get("status"))
    feedback = graded_eval.get("ai_feedback") or {}
    print("  Strengths:", feedback.get("strengths", [])[:2])
    print("  Teacher Summary:", feedback.get("teacher_summary"))

    # 6. Verify Checked Submission in Supabase assignment_submissions
    print("\n--- STEP 6: Verifying Supabase assignment_submissions Row ---")
    r_sub = requests.get(
        f"{Config.SUPABASE_URL}/rest/v1/assignment_submissions?assignment_id=eq.{assignment_id}&select=*",
        headers=headers
    )
    assert r_sub.status_code == 200, f"Submission query failed: {r_sub.text}"
    sub_rows = r_sub.json()
    assert len(sub_rows) >= 1, "Submission row not found in Supabase assignment_submissions!"
    sub_row = sub_rows[0]
    print("Found row in Supabase assignment_submissions:")
    print("  Submission ID:", sub_row.get("id"))
    print("  User ID:", sub_row.get("user_id"))
    print("  Score in Supabase:", sub_row.get("score"))
    print("  Status in Supabase:", sub_row.get("status"))
    print("  Feedback length in Supabase:", len(sub_row.get("feedback") or ""))

    # 7. Verify Teacher Portal List Submissions
    print("\n--- STEP 7: Teacher Portal Submissions List ---")
    submissions_list = db.list_assignment_submissions(assignment_id)
    assert len(submissions_list) >= 1, "list_assignment_submissions returned empty"
    first_sub = submissions_list[0]
    print("Teacher portal loaded submission:")
    print("  Student:", first_sub.get("student_email") or first_sub.get("student_id"))
    print("  Score:", first_sub.get("score"))
    print("  Feedback Object Present:", isinstance(first_sub.get("ai_feedback"), dict))

    # 8. Clean up test records
    print("\n--- STEP 8: Cleaning Up Test Records from Supabase ---")
    requests.delete(f"{Config.SUPABASE_URL}/rest/v1/assignment_submissions?assignment_id=eq.{assignment_id}", headers=headers)
    requests.delete(f"{Config.SUPABASE_URL}/rest/v1/course_assignments?id=eq.{assignment_id}", headers=headers)
    print("Cleaned up temporary assignment and submission successfully.")

    print("\n" + "=" * 70)
    print("LIFECYCLE TEST COMPLETED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    test_supabase_lifecycle()
