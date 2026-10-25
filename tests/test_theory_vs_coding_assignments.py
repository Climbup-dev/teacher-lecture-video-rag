import unittest
import json
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import patch
from backend.db_adapter import DBAdapter
from backend.assignment_engine import AssignmentEngine

class TestTheoryVsCodingAssignments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = DBAdapter()
        cls.engine = AssignmentEngine(cls.db)

    def test_classify_pure_theory_topics(self):
        # 1. DBMS Normalization and ACID
        lesson_dbms = {
            "title": "Database Management Systems: Relational Model & Normalization (1NF, 2NF, 3NF)",
            "summary": "Explains relational schema design, functional dependencies, 1NF, 2NF, 3NF, BCNF, and ACID transaction properties.",
            "course_id": "cs-dbms-101"
        }
        res = self.engine.classify_assignment_mode(lesson_dbms, lesson_dbms["summary"])
        self.assertEqual(res["assignment_type"], "THEORY", f"DBMS Normalization & ACID should be classified as THEORY. Got: {res}")

        # 2. OS CPU Scheduling & Process States (Mentions algorithm names and C concepts conceptually)
        lesson_os = {
            "title": "Operating Systems: CPU Scheduling Algorithms & Process State Transitions",
            "summary": "Theoretical overview of process scheduling, FCFS, SJF, Round Robin, context switching, starvation, and deadlock conditions.",
            "course_id": "cs-os-102"
        }
        res_os = self.engine.classify_assignment_mode(lesson_os, lesson_os["summary"])
        self.assertEqual(res_os["assignment_type"], "THEORY", f"OS scheduling concepts should be classified as THEORY. Got: {res_os}")

        # 3. Computer Networks OSI & TCP/IP
        lesson_net = {
            "title": "Computer Networks: OSI 7-Layer Reference Model & TCP/IP Architecture",
            "summary": "Detailed exploration of physical, data link, network, transport, session, presentation, and application layers.",
            "course_id": "cs-net-103"
        }
        res_net = self.engine.classify_assignment_mode(lesson_net, lesson_net["summary"])
        self.assertEqual(res_net["assignment_type"], "THEORY", f"Networking OSI model should be classified as THEORY. Got: {res_net}")

    def test_classify_coding_topics(self):
        # 1. Python Functions & Coding
        lesson_py = {
            "title": "Learn Python: Programming From Scratch, Functions, and Recursion",
            "summary": "Hands-on coding tutorial for beginners learning python syntax, writing code along with functions and recursion.",
            "course_id": "cs-py-101"
        }
        res_py = self.engine.classify_assignment_mode(lesson_py, lesson_py["summary"])
        self.assertEqual(res_py["assignment_type"], "CODING", f"Python programming from scratch should be CODING. Got: {res_py}")

        # 2. Hands-on SQL queries
        lesson_sql = {
            "title": "Learn SQL Beginner to Advanced: Full Course with Hands-On Practice Queries",
            "summary": "Hands on crash course writing queries, SELECT, JOIN, GROUP BY, subqueries and building a database project.",
            "course_id": "cs-sql-201"
        }
        res_sql = self.engine.classify_assignment_mode(lesson_sql, lesson_sql["summary"])
        self.assertEqual(res_sql["assignment_type"], "CODING", f"Hands-on SQL practice queries should be CODING. Got: {res_sql}")

    def test_quality_gate_for_theory_allows_empty_starter_code(self):
        theory_assignment = {
            "title": "Mission: Database Schema Normalization Audit",
            "scenario_context": "You are a database consultant auditing an unnormalized university database schema.",
            "description": "Comprehensive theory assignment evaluating student understanding of database normalization and anomalies.",
            "assignment_type": "THEORY",
            "max_score": 100,
            "starter_code": "",  # Empty on purpose for theory
            "problems": [
                {
                    "problem_number": 1,
                    "tier": "Basic",
                    "goal_type": "THEORY",
                    "marks": 50,
                    "problem_statement": "Identify 1NF and 2NF violations in the provided student enrollment schema and explain why functional dependencies cause update anomalies.",
                    "starter_code": "",
                    "test_cases": [],
                    "conceptual_checkpoints": [
                        "Identifies repeating groups or multi-valued attributes violating 1NF",
                        "Identifies partial dependencies on composite primary key violating 2NF",
                        "Explains insertion, deletion, and update anomalies clearly"
                    ],
                    "acceptance_criteria": ["All normalization rules explained clearly with schema examples"]
                },
                {
                    "problem_number": 2,
                    "tier": "Intermediate",
                    "goal_type": "THEORY",
                    "marks": 50,
                    "problem_statement": "Decompose the relation into 3NF and verify lossless-join and dependency-preservation properties.",
                    "starter_code": "",
                    "test_cases": [],
                    "conceptual_checkpoints": [
                        "Identifies transitive dependencies",
                        "Produces decomposed relations in 3NF",
                        "Explains lossless-join property"
                    ],
                    "acceptance_criteria": ["Schema is decomposed into valid 3NF with preserved dependencies"]
                }
            ],
            "rubric": {
                "max_score": 100,
                "breakdown": [
                    {"category": "Correctness", "points": 60},
                    {"category": "Completeness", "points": 40}
                ]
            }
        }
        lesson = {
            "title": "DBMS Normalization & Relational Theory",
            "summary": "Covers 1NF, 2NF, 3NF, functional dependencies and ACID properties."
        }
        report = self.engine.validate_assignment_quality(theory_assignment, lesson)
        self.assertTrue(report["passed"], f"Quality gate should pass for valid theory assignment: {report.get('warnings')}")
        self.assertGreaterEqual(report["quality_score"], 80)
        
        # Verify check 6 passed without starter code
        check_6 = next((c for c in report["checks"] if "Starter Code" in c["name"]), None)
        self.assertIsNotNone(check_6)
        self.assertTrue(check_6["passed"], "Check 6 should pass for THEORY without requiring starter code")

    def test_theory_goal_verification_evaluates_checkpoints(self):
        assignment = {
            "id": "test-theory-asgn-999",
            "lesson_id": "lesson_00565279",
            "course_id": "course_f24b2b3a",
            "title": "DBMS Theory Assignment",
            "assignment_type": "THEORY",
            "max_score": 100,
            "problems": [
                {
                    "problem_number": 1,
                    "tier": "Basic",
                    "goal_type": "THEORY",
                    "marks": 30,
                    "problem_statement": "Explain ACID properties and why isolation levels matter in concurrent transactions.",
                    "conceptual_checkpoints": [
                        "Explains Atomicity, Consistency, Isolation, and Durability",
                        "Describes dirty reads or non-repeatable reads in concurrent execution"
                    ],
                    "acceptance_criteria": ["Clear explanation of ACID properties and dirty reads"]
                },
                {
                    "problem_number": 2,
                    "tier": "Intermediate",
                    "goal_type": "THEORY",
                    "marks": 35,
                    "problem_statement": "Explain 2-Phase Locking (2PL) protocol.",
                    "conceptual_checkpoints": ["Growing phase", "Shrinking phase"],
                    "acceptance_criteria": ["Clear explanation of 2PL phases"]
                }
            ]
        }

        # Comprehensive answer covering all conceptual checkpoints
        good_submission = """
        ACID Properties in Relational Databases:
        1. Atomicity: Every transaction is treated as a single indivisible unit; either all statements execute successfully, or the entire transaction is aborted and rolled back.
        2. Consistency: Ensures that any transaction brings the database from one valid state to another, strictly satisfying all constraints, cascades, triggers, and foreign keys.
        3. Isolation: Concurrent transactions execute independently without interference, ensuring intermediate states of uncommitted transactions are never visible to other transactions.
        4. Durability: Once a transaction commits, its modifications are permanently recorded in non-volatile storage (write-ahead log / redo log) and will not be lost even in catastrophic power failure.

        Concurrency Anomalies and Isolation Levels:
        A dirty read occurs when Transaction 1 updates a row without committing, and Transaction 2 reads that uncommitted modification. If Transaction 1 subsequently aborts and issues a ROLLBACK, Transaction 2 has computed with invalid, phantom data that was never officially committed.
        A non-repeatable read occurs when Transaction 1 reads a row, Transaction 2 commits an update to that row, and Transaction 1 reads it again, observing inconsistent values within the same transaction.
        Higher isolation levels such as Read Committed, Repeatable Read, and Serializable eliminate dirty reads using shared read locks or Multi-Version Concurrency Control (MVCC) snapshots.
        """

        with patch.object(self.db, "get_assignment_by_id", return_value=assignment):
            result = self.engine.verify_goal(
                assignment_id="test-theory-asgn-999",
                goal_number=1,
                student_code=good_submission
            )

        self.assertTrue(result["passed"], f"Good theory answer should pass: {result}")
        self.assertEqual(result["goal_number"], 1)
        self.assertEqual(result["goal_type"], "THEORY")
        self.assertTrue(result["unlocked_next_goal"])
        self.assertGreaterEqual(result["marks_earned"], 20)
        self.assertIn("test_results", result)
        self.assertGreaterEqual(len(result["test_results"]), 1)

    def test_db_adapter_serialization_preserves_assignment_type(self):
        assignment_obj = {
            "id": "asgn-test-theory-1",
            "course_id": "course-123",
            "lesson_id": "lesson-456",
            "title": "DBMS ACID and Concurrency Theory",
            "assignment_type": "THEORY",
            "scenario_context": "Banking transaction ledger analysis.",
            "starter_code": "",
            "status": "published",
            "max_score": 100,
            "problems": [
                {
                    "problem_number": 1,
                    "tier": "Basic",
                    "goal_type": "THEORY",
                    "marks": 50,
                    "problem_statement": "Explain Dirty Reads and Lost Updates.",
                    "starter_code": "",
                    "test_cases": [],
                    "conceptual_checkpoints": ["Dirty reads", "Lost updates"]
                },
                {
                    "problem_number": 2,
                    "tier": "Advanced",
                    "goal_type": "THEORY",
                    "marks": 50,
                    "problem_statement": "Explain Serializability and Conflict Serializability.",
                    "starter_code": "",
                    "test_cases": [],
                    "conceptual_checkpoints": ["Precedence graph", "Conflict serializability"]
                }
            ]
        }

        serialized = self.db._serialize_assignment_for_supabase(assignment_obj)
        self.assertIn("description", serialized)
        desc_json = json.loads(serialized["description"])
        self.assertEqual(desc_json.get("assignment_type"), "THEORY")
        self.assertEqual(desc_json["problems"][0].get("goal_type"), "THEORY")

        deserialized = self.db._deserialize_assignment_from_supabase(serialized)
        self.assertEqual(deserialized.get("assignment_type"), "THEORY")
        self.assertEqual(deserialized["problems"][0].get("goal_type"), "THEORY")
        self.assertEqual(deserialized["problems"][1].get("goal_type"), "THEORY")

    def test_verify_goal_rejects_unmodified_starter_code(self):
        starter = "def reverse_string(s: str) -> str:\n    # TODO: Implement string reversal\n    pass"
        coding_assignment = {
            "id": "asgn-coding-stub-1",
            "title": "Python String Reversal Assignment",
            "assignment_type": "CODING",
            "problems": [
                {
                    "problem_number": 1,
                    "tier": "Basic",
                    "goal_type": "CODING",
                    "marks": 25,
                    "problem_statement": "Write a function that reverses a given string.",
                    "starter_code": starter,
                    "test_cases": [
                        {"input_description": "'hello'", "expected_output": "'olleh'", "is_hidden": False}
                    ]
                }
            ]
        }

        with patch.object(self.db, "get_assignment_by_id", return_value=coding_assignment):
            # 1. Student submits exactly the starter code without any modification
            res = self.engine.verify_goal("asgn-coding-stub-1", 1, starter)
            self.assertFalse(res["passed"], "Unmodified starter code must NOT pass!")
            self.assertEqual(res["marks_earned"], 0, "Unmodified starter code must get 0 marks!")
            self.assertEqual(res["status"], "needs_revision")
            self.assertIn("starter template", res["feedback"].lower())

    def test_verify_goal_rejects_empty_and_stub_code(self):
        coding_assignment = {
            "id": "asgn-coding-stub-2",
            "title": "Python Algorithm Assignment",
            "assignment_type": "CODING",
            "problems": [
                {
                    "problem_number": 1,
                    "tier": "Basic",
                    "goal_type": "CODING",
                    "marks": 25,
                    "problem_statement": "Implement binary search.",
                    "starter_code": "",
                    "test_cases": [
                        {"input_description": "[1, 2, 3], 2", "expected_output": "1", "is_hidden": False}
                    ]
                }
            ]
        }

        with patch.object(self.db, "get_assignment_by_id", return_value=coding_assignment):
            # Test a: only comments
            res_comments = self.engine.verify_goal("asgn-coding-stub-2", 1, "# TODO: will write later\n# note: binary search\n")
            self.assertFalse(res_comments["passed"])
            self.assertEqual(res_comments["marks_earned"], 0)

            # Test b: only 'pass'
            res_pass = self.engine.verify_goal("asgn-coding-stub-2", 1, "pass")
            self.assertFalse(res_pass["passed"])
            self.assertEqual(res_pass["marks_earned"], 0)

            # Test c: function with only pass / NotImplementedError
            func_stub = "def binary_search(arr, target):\n    \"\"\"Docstring\"\"\"\n    raise NotImplementedError()\n"
            res_ast_stub = self.engine.verify_goal("asgn-coding-stub-2", 1, func_stub)
            self.assertFalse(res_ast_stub["passed"])
            self.assertEqual(res_ast_stub["marks_earned"], 0)
            self.assertIn("stubs", res_ast_stub["feedback"].lower())

    def test_verify_goal_rejects_syntax_errors(self):
        coding_assignment = {
            "id": "asgn-coding-stub-3",
            "title": "Python Assignment",
            "assignment_type": "CODING",
            "problems": [
                {
                    "problem_number": 1,
                    "tier": "Basic",
                    "goal_type": "CODING",
                    "marks": 25,
                    "problem_statement": "Implement a function.",
                    "starter_code": "",
                    "test_cases": []
                }
            ]
        }

        with patch.object(self.db, "get_assignment_by_id", return_value=coding_assignment):
            res_syntax = self.engine.verify_goal("asgn-coding-stub-3", 1, "def broken(\n    return 1")
            self.assertFalse(res_syntax["passed"])
            self.assertEqual(res_syntax["marks_earned"], 0)
            self.assertIn("syntax error", res_syntax["feedback"].lower())

    def test_verify_goal_passes_valid_implementation(self):
        coding_assignment = {
            "id": "asgn-coding-valid-1",
            "title": "Python String Reversal Assignment",
            "assignment_type": "CODING",
            "problems": [
                {
                    "problem_number": 1,
                    "tier": "Basic",
                    "goal_type": "CODING",
                    "marks": 25,
                    "problem_statement": "Write a function that reverses a given string.",
                    "starter_code": "def reverse_string(s: str) -> str:\n    pass",
                    "test_cases": [
                        {"input_description": "'hello'", "expected_output": "'olleh'", "is_hidden": False}
                    ]
                }
            ]
        }

        mock_llm_response = json.dumps({
            "passed": True,
            "marks_awarded": 25,
            "test_evaluations": [
                {
                    "test_index": 0,
                    "passed": True,
                    "observed_output_or_behavior": "'olleh'",
                    "notes": "Passed reverse string check"
                }
            ],
            "feedback": "Excellent solution! All test cases passed."
        })

        with patch.object(self.db, "get_assignment_by_id", return_value=coding_assignment), \
             patch.object(self.engine, "_call_llm", return_value=mock_llm_response):
            valid_code = "def reverse_string(s: str) -> str:\n    return s[::-1]\n"
            res = self.engine.verify_goal("asgn-coding-valid-1", 1, valid_code)
            self.assertTrue(res["passed"])
            self.assertEqual(res["marks_earned"], 25)
            self.assertEqual(res["status"], "passed")
            self.assertTrue(res["unlocked_next_goal"])

    def test_classify_introductory_lecture_as_theory(self):
        # Lesson 1: 2m 41s lecture introducing Python without writing code
        lesson_intro = {
            "title": "1.Python for Absolute Beginners   Learn Python from Scratch in 2025! 1080p (2m 41s)",
            "duration": "2m 41s",
            "duration_seconds": 161,
            "raw_transcript": "Welcome to Python. High level programming language. Created in 1991 by Guido van Rossum. Used in Web development, PUBG game engines, and automation of emails and excel sheets."
        }
        res = self.engine.classify_assignment_mode(lesson_intro, lesson_intro["raw_transcript"])
        self.assertEqual(res["assignment_type"], "THEORY", "Introductory motivational overview lecture must be classified as THEORY so beginners are not overwhelmed.")


if __name__ == "__main__":
    unittest.main()

