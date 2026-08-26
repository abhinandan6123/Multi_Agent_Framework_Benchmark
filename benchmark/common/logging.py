"""Unified logger -- pipeline stage 3 of Section 3.2.

One instrumentation layer for all three adapters, so that logging fidelity
cannot differ between frameworks. Append-only; the metric layer never mutates
what is written here.

Schema: docs/log_schema.md (frozen contract).
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

SCHEMA_FILES = ("runs", "steps", "llm_calls", "tools", "judge")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunGroupLogger:
    """Owns one run-group directory and its append-only JSONL files."""

    def __init__(self, root: Path, run_group: str) -> None:
        self.dir = root / run_group
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "outputs").mkdir(exist_ok=True)
        (self.dir / "prompts").mkdir(exist_ok=True)
        self.run_group = run_group
        self._lock = threading.Lock()
        self._handles = {
            name: (self.dir / f"{name}.jsonl").open("a", encoding="utf-8")
            for name in SCHEMA_FILES
        }

    def write(self, stream: str, record: dict[str, Any]) -> None:
        if stream not in self._handles:
            raise KeyError(f"unknown log stream {stream!r}; schema is frozen")
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock:                      # concurrency sweep writes in parallel
            self._handles[stream].write(line + "\n")
            self._handles[stream].flush()

    def write_json(self, relative_path: str, payload: Any) -> Path:
        path = self.dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return path

    def close(self) -> None:
        for handle in self._handles.values():
            handle.close()


class MemorySampler:
    """Peak RSS via a 100 ms sampling thread (Section 3.8.4).

    Sampling rather than a single end-of-run reading: orchestration memory is
    transient, and a final measurement would systematically under-report it.
    """

    INTERVAL_SECONDS = 0.1

    def __init__(self) -> None:
        self._proc = psutil.Process()
        self._peak_bytes = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "MemorySampler":
        self._peak_bytes = self._proc.memory_info().rss
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()
        return self

    def _sample(self) -> None:
        while not self._stop.wait(self.INTERVAL_SECONDS):
            try:
                self._peak_bytes = max(self._peak_bytes, self._proc.memory_info().rss)
            except psutil.Error:
                return

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    @property
    def peak_mb(self) -> float:
        return self._peak_bytes / (1024 * 1024)


class RunRecorder:
    """Per-run collector. Accumulates the step/llm/tool records an adapter
    produces and assembles the single `runs.jsonl` record at the end.

    The adapter never writes a runs record itself -- timing, tokens, cost, and
    the success predicate are owned here, so an adapter cannot influence its own
    measured numbers.
    """

    def __init__(self, logger: RunGroupLogger, run_id: str, meta: dict[str, Any]) -> None:
        self._logger = logger
        self.run_id = run_id
        self._meta = meta
        self._llm_calls: list[dict[str, Any]] = []
        self._tool_calls: list[dict[str, Any]] = []
        self._prompt_seq = 0
        self._started_monotonic = 0.0
        self.started_at = ""
        self.ended_at = ""
        self.latency_seconds = 0.0

    # -- emitters handed to the instrumented client / tool layer -------------

    def emit_llm_call(self, record: dict[str, Any]) -> None:
        self._prompt_seq += 1
        prompt_rel = f"prompts/{self.run_id}/call_{self._prompt_seq:03d}.json"
        self._logger.write_json(
            prompt_rel,
            {
                "request_params": record.pop("request_params", {}),
                "messages": record.pop("messages", []),
            },
        )
        record["prompt_path"] = prompt_rel
        record["started_at"] = utcnow()
        self._llm_calls.append(record)
        self._logger.write("llm_calls", record)

    def emit_tool_call(self, record: dict[str, Any]) -> None:
        self._tool_calls.append(record)
        self._logger.write("tools", record)

    # -- lifecycle -----------------------------------------------------------

    def __enter__(self) -> "RunRecorder":
        self.started_at = utcnow()
        self._started_monotonic = time.monotonic()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.latency_seconds = time.monotonic() - self._started_monotonic
        self.ended_at = utcnow()

    # -- assembly ------------------------------------------------------------

    def finalise(
        self,
        result: Any,                      # RunResult
        *,
        peak_rss_mb: float,
        llm_seconds: float,
        schema_valid: bool,
        hard_gate_passed: bool,
    ) -> dict[str, Any]:
        for step in result.steps:
            record = asdict(step) | {"run_id": self.run_id, **_step_meta(self._meta)}
            self._logger.write("steps", record)

        tool_seconds = sum(c.get("duration_seconds", 0.0) for c in self._tool_calls)
        tokens = _sum_usage(self._llm_calls)

        success = bool(
            result.terminated_cleanly and schema_valid and hard_gate_passed
        )
        failure_category = (
            None if success
            else (result.failure_category.value if result.failure_category
                  else _infer_category(schema_valid, hard_gate_passed))
        )

        output_path = None
        if result.output is not None:
            output_path = f"outputs/{self.run_id}.json"
            self._logger.write_json(output_path, result.output)

        record = {
            "run_id": self.run_id,
            **self._meta,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "latency_seconds": self.latency_seconds,
            "llm_seconds": llm_seconds,
            "tool_seconds": tool_seconds,
            # Asserted non-negative by the metric layer (invariant 6).
            "overhead_seconds": self.latency_seconds - llm_seconds - tool_seconds,
            "step_count": len(result.steps),
            "llm_call_count": len(self._llm_calls),
            "tool_call_count": len(self._tool_calls),
            **tokens,
            "peak_rss_mb": peak_rss_mb,
            "status": "success" if success else "failure",
            "failure_category": failure_category,
            "failure_detail": result.failure_detail,
            "traceback": result.traceback,
            "schema_valid": schema_valid,
            "hard_gate_passed": hard_gate_passed,
            "terminated_cleanly": result.terminated_cleanly,
            "output_path": output_path,
            "notes": None,
        }
        self._logger.write("runs", record)
        return record


def _step_meta(meta: dict[str, Any]) -> dict[str, Any]:
    return {k: meta[k] for k in ("framework", "task_id") if k in meta}


def _sum_usage(calls: list[dict[str, Any]]) -> dict[str, int]:
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    for call in calls:
        usage = call.get("usage") or {}
        totals["input_tokens"] += usage.get("input_tokens", 0)
        totals["output_tokens"] += usage.get("output_tokens", 0)
        totals["cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
        totals["cache_write_tokens"] += usage.get("cache_creation_input_tokens", 0)
    return totals


def _infer_category(schema_valid: bool, hard_gate_passed: bool) -> str:
    if not schema_valid:
        return "schema_invalid"
    if not hard_gate_passed:
        return "constraint_violation"
    return "exception"
