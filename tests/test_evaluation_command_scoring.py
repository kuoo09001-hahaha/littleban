import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_ROOT = PROJECT_ROOT / "evaluation"
if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))


class EvaluationCommandScoringTest(unittest.TestCase):
    def test_scores_expected_command_type(self):
        from run_eval import score_case

        case = {"id": "reminder", "category": "reminder", "expected": {"command_type": "SET_ALARM"}}
        self.assertTrue(score_case(case, {"command_type": "SET_ALARM"})["passed"])
        self.assertFalse(score_case(case, {"command_type": None})["passed"])


if __name__ == "__main__":
    unittest.main()
