"""A lightweight harness around the existing Agent HTTP API.

It intentionally does not replace the product Agent.  It standardises an
evaluation run into observable steps and retries only transport failures.
"""

from __future__ import annotations

import time
from typing import Callable


class HarnessRunner:
    def __init__(self, post_json: Callable, retries: int = 1):
        self.post_json = post_json
        self.retries = retries

    def run_turn(self, url: str, payload: dict, timeout: float) -> tuple[dict, dict]:
        """Execute one turn with a small, explicit transport retry policy."""
        started = time.perf_counter()
        step = {
            "type": "agent_http_call",
            "session_id": payload["session_id"],
            "attempts": 0,
            "success": False,
        }
        last_error = None
        for attempt in range(1, self.retries + 2):
            step["attempts"] = attempt
            try:
                response = self.post_json(url, payload, timeout)
                step.update({
                    "success": True,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "trace_id": response.get("metadata", {}).get("trace_id"),
                    "tool_used": response.get("tool_used", False),
                })
                return response, step
            except Exception as error:  # transport error, not an Agent answer
                last_error = str(error)
        step.update({"error": last_error, "latency_ms": round((time.perf_counter() - started) * 1000, 2)})
        raise RuntimeError(last_error)

    def run_case(self, chat_url: str, case: dict, session_prefix: str, family_id: str, mode: str, timeout: float) -> tuple[list[dict], list[dict]]:
        turns, steps = [], [{"type": "harness_start", "runner": "harness", "family_id": family_id}]
        for turn in case["turns"]:
            turn_data = turn if isinstance(turn, dict) else {"message": turn}
            session_id = f"{session_prefix}-{turn_data.get('session', 'shared')}"
            payload = {
                "message": turn_data["message"],
                "session_id": session_id,
                "mode": mode,
                "family_id": family_id,
                "actor_name": turn_data.get("actor_name", case.get("actor_name")),
            }
            response, step = self.run_turn(chat_url, payload, timeout)
            turns.append(response)
            steps.append(step)
        steps.append({"type": "harness_complete", "success": True})
        return turns, steps
