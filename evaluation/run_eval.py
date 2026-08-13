"""Offline, reproducible scorer for CompanionBench.

The runner accepts saved results so model calls are not hidden inside scoring.
This permits comparing prompts, models, and memory strategies on identical
outputs.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List


def read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        for number, line in enumerate(file, start=1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"Invalid JSON on {path}:{number}") from error


def tool_match(expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
    calls = actual.get("tool_calls", [])
    if not expected.get("should_call"):
        return not calls
    for call in calls:
        if call.get("name") != expected.get("name"):
            continue
        arguments = call.get("arguments", {})
        def value_matches(key: str, value: Any) -> bool:
            observed = arguments.get(key)
            # Weather providers commonly normalise "上海徐汇区" to "徐汇区".
            # Either representation resolves to the same requested district.
            if key == "location" and isinstance(observed, str) and isinstance(value, str):
                return observed == value or observed in value or value in observed
            return observed == value

        if all(value_matches(key, value) for key, value in expected.get("arguments", {}).items()):
            return True
    return False


def answer_match(expected: Dict[str, Any], answer: str) -> bool:
    required = expected.get("contains", [])
    forbidden = expected.get("not_contains", [])
    return all(token in answer for token in required) and not any(token in answer for token in forbidden)


def storage_match(expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
    """Assert persisted health memory, independently of the model's wording."""
    events = (actual.get("storage_check") or {}).get("events", [])
    required_symptoms = expected.get("symptoms", [])
    forbidden_symptoms = expected.get("not_symptoms", [])
    observed = [str(event.get("symptom", "")) for event in events]
    return (
        all(any(symptom in item for item in observed) for symptom in required_symptoms)
        and not any(any(symptom in item for item in observed) for symptom in forbidden_symptoms)
        and (not expected.get("min_events") or len(events) >= expected["min_events"])
    )


def score_case(case: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
    answer = actual.get("answer", "")
    checks: List[bool] = []
    if "tool" in case["expected"]:
        checks.append(tool_match(case["expected"]["tool"], actual))
    if "answer" in case["expected"]:
        checks.append(answer_match(case["expected"]["answer"], answer))
    if "command_type" in case["expected"]:
        checks.append(actual.get("command_type") == case["expected"]["command_type"])
    if "storage" in case["expected"]:
        checks.append(storage_match(case["expected"]["storage"], actual))
    return {
        "id": case["id"],
        "category": case["category"],
        "passed": bool(checks) and all(checks),
        "checks_passed": sum(checks),
        "checks_total": len(checks),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=Path("evaluation/reports/latest.json"))
    parser.add_argument("--limit", type=int, help="Score only the first N dataset cases")
    args = parser.parse_args()

    cases = list(read_jsonl(args.dataset))
    if args.limit is not None:
        cases = cases[:args.limit]
    outputs = {item["id"]: item for item in read_jsonl(args.results)}
    scored = [score_case(case, outputs.get(case["id"], {})) for case in cases]
    by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in scored:
        by_category[item["category"]].append(item)

    def rate(items: List[Dict[str, Any]]) -> float:
        return round(sum(item["passed"] for item in items) / len(items), 4) if items else 0.0

    report = {
        "dataset": str(args.dataset),
        "cases": len(scored),
        "passed": sum(item["passed"] for item in scored),
        "task_success_rate": rate(scored),
        "by_category": {category: rate(items) for category, items in sorted(by_category.items())},
        "failures": [item for item in scored if not item["passed"]],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
