import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tools import load_pdf
from agent import answer_question

TEST_QUESTIONS = [
    ("How many days to return?", ["days", "return"]),
    ("When is the refund period?", ["refund", "days"]),
    ("What is the warranty?", ["warranty"]),
    ("Is there a dog clause?", ["not found", "insufficient"]),
]


def run_tests(pdf_path):
    doc_id = load_pdf(pdf_path)
    passed = 0

    for i, (question, expected) in enumerate(TEST_QUESTIONS, 1):
        result = answer_question(question, doc_id)
        answer_lower = result["answer"].lower()
        match = any(word.lower() in answer_lower for word in expected)

        tag = "PASS" if match else "FAIL"
        if match:
            passed += 1

        print(f"[{tag}] Q{i}: {question}")
        print(f"  Answer: {result['answer'][:200]}")
        print(f"  Status: {result['status']}  |  Calls used: {result['calls_used']}")
        print()

    print(f"{passed} of {len(TEST_QUESTIONS)} passed")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_questions.py <path-to-pdf>")
        sys.exit(1)
    run_tests(sys.argv[1])
