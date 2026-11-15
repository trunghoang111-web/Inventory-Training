"""Test runner for all 20 golden policy cases in tests/golden_cases.json."""
import json
import unittest
from pathlib import Path
from backend.grading import (
    check_threshold, calculate_current_result, is_on_time,
    calculate_qualified_rate, check_readiness
)

class TestGoldenCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        golden_file = Path(__file__).resolve().parents[1] / "tests" / "golden_cases.json"
        with open(golden_file, "r", encoding="utf-8") as f:
            cls.cases = json.load(f)

    def test_all_golden_cases(self):
        passed = 0
        for case in self.cases:
            cid = case["id"]
            kind = case["kind"]
            expected = case["expected"]

            if kind == "threshold":
                actual = check_threshold(
                    kind=case["type"],
                    score=case["score"],
                    critical_failed=case["critical_failed"],
                    missing_observations=case.get("missing_observations", 0)
                )
            elif kind == "current_result":
                actual = calculate_current_result(case["attempts"])
            elif kind == "deadline":
                actual = is_on_time(case["submitted_at"])
            elif kind == "dashboard":
                actual = calculate_qualified_rate(case["real_required"], case["qualified"])
            elif kind == "readiness":
                actual = check_readiness(case)
            else:
                self.fail(f"Unknown golden case kind: {kind}")

            self.assertEqual(
                actual, expected,
                f"Golden Case {cid} failed! Expected {expected}, got {actual}"
            )
            passed += 1

        print(f"\nALL {passed}/20 GOLDEN CASES PASSED!")

if __name__ == "__main__":
    unittest.main()
