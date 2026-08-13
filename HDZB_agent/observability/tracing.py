"""Small dependency-free trace store for debugging and evaluation."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional
from uuid import uuid4


class TraceStore:
    """Keep a bounded, JSON-serialisable history of Agent executions."""

    def __init__(self, max_traces: int = 500) -> None:
        self._traces: Deque[Dict[str, Any]] = deque(maxlen=max_traces)

    def record(
        self,
        *,
        session_id: str,
        input_text: str,
        result: Dict[str, Any],
        total_latency_ms: float,
        mode: str,
    ) -> Dict[str, Any]:
        tool_results = result.get("tool_results") or []
        trace = {
            "trace_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "mode": mode,
            "input": input_text,
            "success": bool(result.get("success")),
            "tool_used": bool(result.get("tool_used")),
            "steps": [
                {
                    "type": "tool_call",
                    "tool": item.get("tool_name"),
                    "arguments": item.get("arguments", {}),
                    "success": not str(item.get("result", "")).startswith("工具"),
                }
                for item in tool_results
            ],
            "tool_results": tool_results,
            "final_answer": result.get("response", ""),
            "total_latency_ms": round(total_latency_ms, 2),
        }
        self._traces.append(trace)
        return trace

    def list(self, limit: int = 50, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        traces = reversed(self._traces)
        if session_id:
            traces = (trace for trace in traces if trace["session_id"] == session_id)
        return list(traces)[:limit]
