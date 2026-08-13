"""Run CompanionBench against a locally running Agent and score the outputs."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from run_eval import read_jsonl
from harness import HarnessRunner


def request_json(url: str, *, method: str = "GET", payload: dict | None = None, timeout: float = 45.0) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, headers={"Content-Type": "application/json"} if payload is not None else {}, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"HTTP {error.code}: {error.read().decode('utf-8', errors='replace')}") from error
    except URLError as error:
        raise RuntimeError(f"Cannot reach Agent: {error.reason}") from error


def post_json(url: str, payload: dict, timeout: float) -> dict:
    return request_json(url, method="POST", payload=payload, timeout=timeout)


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute CompanionBench against a local Agent")
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/datasets/companion_bench.jsonl"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8017")
    parser.add_argument("--mode", choices=("elder", "child"), default="elder")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--limit", type=int, help="Run only first N cases while debugging")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runner", choices=("baseline", "harness"), default="baseline")
    parser.add_argument(
        "--inject-first-attempt-failure",
        action="store_true",
        help="Evaluation only: fail the first chat HTTP attempt of every session, to measure retry recovery.",
    )
    parser.add_argument(
        "--reuse-family-id",
        action="store_true",
        help="Use family_id written in the dataset. Off by default to prevent old SQLite memory from contaminating a run.",
    )
    args = parser.parse_args()
    cases = list(read_jsonl(args.dataset))[:args.limit]
    output = args.output or Path(f"evaluation/results/{args.runner}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)
    chat_url = f"{args.base_url.rstrip('/')}/agent/chat"
    family_url = f"{args.base_url.rstrip('/')}/agent/families"
    failed_sessions: set[str] = set()

    def runner_post_json(url: str, payload: dict, timeout: float) -> dict:
        if args.inject_first_attempt_failure and "/agent/chat" in url and payload["session_id"] not in failed_sessions:
            failed_sessions.add(payload["session_id"])
            raise RuntimeError("Injected transient transport failure (evaluation only)")
        return post_json(url, payload, timeout)

    harness_runner = HarnessRunner(runner_post_json, retries=1) if args.runner == "harness" else None
    with output.open("w", encoding="utf-8") as file:
        for index, case in enumerate(cases, start=1):
            run_suffix = uuid4().hex[:8]
            session_prefix, turns = f"eval-{case['id']}-{run_suffix}", []
            configured_family = case.get("family_id", "default")
            family_id = configured_family if args.reuse_family_id else f"{configured_family}-{run_suffix}"
            started = time.perf_counter()
            try:
                harness_trace = []
                setup_members = []
                for member in case.get("setup_members", []):
                    setup_members.append(post_json(
                        f"{family_url}/{quote(family_id, safe='')}/members",
                        member,
                        args.timeout,
                    ))
                if harness_runner:
                    turns, harness_trace = harness_runner.run_case(chat_url, case, session_prefix, family_id, args.mode, args.timeout)
                else:
                    for turn in case["turns"]:
                        turn_data = turn if isinstance(turn, dict) else {"message": turn}
                        turn_session = f"{session_prefix}-{turn_data.get('session', 'shared')}"
                        turns.append(runner_post_json(chat_url, {"message": turn_data["message"], "session_id": turn_session, "mode": args.mode, "family_id": family_id, "actor_name": turn_data.get("actor_name", case.get("actor_name"))}, args.timeout))
                final = turns[-1]
                storage_check = None
                if case.get("storage_check"):
                    check = case["storage_check"]
                    person_name = check["person_name"]
                    days = check.get("days", 7)
                    storage_check = request_json(
                        f"{args.base_url.rstrip('/')}/agent/health-memory/{quote(person_name, safe='')}?family_id={quote(family_id, safe='')}&days={days}",
                        timeout=args.timeout,
                    )
                record = {"id": case["id"], "category": case["category"], "runner": args.runner, "fault_injection": args.inject_first_attempt_failure, "session_id": session_prefix, "family_id": family_id, "setup_members": setup_members, "answer": final.get("response", ""), "tool_calls": [{"name": item.get("tool_name"), "arguments": item.get("arguments", {})} for item in final.get("tool_results") or []], "command_type": final.get("command_type"), "trace_id": final.get("metadata", {}).get("trace_id"), "latency_ms": round((time.perf_counter() - started) * 1000, 2), "turns": turns, "storage_check": storage_check, "harness_trace": harness_trace}
            except Exception as error:
                record = {"id": case["id"], "category": case["category"], "session_id": session_prefix, "answer": "", "tool_calls": [], "error": str(error), "latency_ms": round((time.perf_counter() - started) * 1000, 2), "turns": turns}
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
            file.flush()
            print(f"[{index}/{len(cases)}] {case['id']}: {'error' if record.get('error') else 'done'}")
    report = output.with_suffix(".report.json")
    from run_eval import main as score_main
    old_argv = sys.argv
    try:
        sys.argv = ["run_eval.py", "--dataset", str(args.dataset), "--results", str(output), "--report", str(report), "--limit", str(len(cases))]
        score_main()
    finally:
        sys.argv = old_argv
    print(f"\nRaw results: {output}\nReport: {report}")


if __name__ == "__main__":
    main()
