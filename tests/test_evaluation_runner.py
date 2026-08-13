import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class EvaluationRunnerTest(unittest.TestCase):
    def test_example_outputs_score_perfectly(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "evaluation/run_eval.py",
                    "--dataset", "evaluation/datasets/companion_bench.jsonl",
                    "--results", "evaluation/datasets/example_results.jsonl",
                    "--report", str(report),
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"task_success_rate": 1.0', completed.stdout)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["passed"], 21)

    def test_family_memory_benchmark_has_broad_cross_user_coverage(self):
        sys.path.insert(0, str(PROJECT_ROOT / "evaluation"))
        from run_eval import read_jsonl

        cases = list(read_jsonl(PROJECT_ROOT / "evaluation/datasets/family_memory_bench.jsonl"))
        self.assertEqual(len(cases), 15)
        self.assertIn("family_profile", {case["category"] for case in cases})
        self.assertIn("family_isolation", {case["category"] for case in cases})
        self.assertTrue(any(case.get("setup_members") for case in cases))

    def test_challenge_and_fault_benchmarks_are_valid(self):
        sys.path.insert(0, str(PROJECT_ROOT / "evaluation"))
        from run_eval import read_jsonl

        challenge = list(read_jsonl(PROJECT_ROOT / "evaluation/datasets/family_memory_challenge_bench.jsonl"))
        fault = list(read_jsonl(PROJECT_ROOT / "evaluation/datasets/harness_fault_injection_bench.jsonl"))
        self.assertEqual(len(challenge), 8)
        self.assertEqual(len(fault), 3)
        self.assertIn("challenge_negation", {case["category"] for case in challenge})
        self.assertEqual({case["category"] for case in fault}, {"fault_recovery"})

    def test_holdout_benchmark_is_kept_separate_from_challenge_set(self):
        sys.path.insert(0, str(PROJECT_ROOT / "evaluation"))
        from run_eval import read_jsonl

        holdout = list(read_jsonl(PROJECT_ROOT / "evaluation/datasets/family_memory_holdout_bench.jsonl"))
        challenge = list(read_jsonl(PROJECT_ROOT / "evaluation/datasets/family_memory_challenge_bench.jsonl"))
        self.assertEqual(len(holdout), 5)
        self.assertTrue({case["id"] for case in holdout}.isdisjoint({case["id"] for case in challenge}))


if __name__ == "__main__":
    unittest.main()
