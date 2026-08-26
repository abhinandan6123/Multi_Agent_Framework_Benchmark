"""The run harness -- builds the interleaved schedule and executes it.

Owns the two things adapters must not: the run schedule (Section 3.1) and the
retry policy (Section 3.8.3).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from .llm import InstrumentedClient, LLMConfig
from .logging import MemorySampler, RunGroupLogger, RunRecorder
from .types import FailureCategory, FrameworkAdapter, RunResult, TaskInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "benchmark" / "config.yaml"
RAW_LOGS = REPO_ROOT / "experiments" / "raw_logs"

RETRYABLE = {
    FailureCategory.TIMEOUT,
    FailureCategory.TRANSPORT_ERROR,
    FailureCategory.SCHEMA_INVALID,
}
# `tool_error` is deliberately absent: an agent misusing a tool is framework
# behaviour we want to measure, not transient noise to retry away.


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    _assert_locked(cfg)
    return cfg


def _assert_locked(cfg: dict[str, Any]) -> None:
    """Fail fast on unlocked configuration.

    The project's standing rule is that a factor is not controlled until it has
    actually been controlled. A `PENDING` value reaching a measured run would
    silently produce results whose configuration is unknown, so it is an error
    here rather than a footnote later.
    """
    flat = json.dumps(cfg)
    for token in ("PENDING\"", "\"PENDING"):
        if token in flat:
            raise ValueError(
                "config.yaml still contains PENDING values; lock them before running. "
                "PENDING_INSTALL is permitted only until record_environment.py runs."
            )


def config_hash(cfg: dict[str, Any]) -> str:
    payload = json.dumps(cfg, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def build_schedule(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Interleaved round-robin over all (framework, task) cells.

    Never cell-by-cell: provider-side latency or load drift during the
    measurement window would otherwise be absorbed entirely by whichever
    framework ran last (Section 3.1, Section 3.9).
    """
    frameworks = [f["name"].lower() for f in cfg["frameworks"]]
    tasks = [t["id"] for t in cfg["tasks"]]
    runs_per_cell = cfg["experiment"]["runs_per_cell"]

    schedule: list[dict[str, Any]] = []
    for replication in range(runs_per_cell):
        cells = [(fw, task) for fw in frameworks for task in tasks]
        # Seed derived from the global seed plus the replication index, so the
        # whole schedule is reproducible from one number in the config.
        random.Random(cfg["experiment"]["random_seed"] + replication).shuffle(cells)
        for framework, task_id in cells:
            schedule.append(
                {"framework": framework, "task_id": task_id, "replication": replication}
            )
    for position, entry in enumerate(schedule):
        entry["schedule_position"] = position
    return schedule


def execute_run(
    adapter: FrameworkAdapter,
    task: TaskInstance,
    logger: RunGroupLogger,
    meta: dict[str, Any],
    llm_config: LLMConfig,
    validate: Callable[[dict[str, Any] | None], bool],
    hard_gate: Callable[[dict[str, Any] | None], bool],
) -> dict[str, Any]:
    """One attempt. Never raises: a crash in one adapter must not abort the
    group, so every error becomes a logged failure record."""
    run_id = meta["run_id"]
    recorder = RunRecorder(logger, run_id, meta)
    client = InstrumentedClient(llm_config, recorder.emit_llm_call, run_id)
    adapter.client = client                      # type: ignore[attr-defined]
    adapter.emit_tool_call = recorder.emit_tool_call  # type: ignore[attr-defined]

    adapter.build(task)                          # before timing starts

    with MemorySampler() as memory, recorder:
        try:
            result = adapter.run(task)
        except TimeoutError:
            result = RunResult(
                output=None, steps=[], terminated_cleanly=False,
                failure_category=FailureCategory.TIMEOUT,
                failure_detail="run exceeded timeout_seconds",
            )
        except Exception as exc:                 # noqa: BLE001
            result = RunResult(
                output=None, steps=[], terminated_cleanly=False,
                failure_category=FailureCategory.EXCEPTION,
                failure_detail=f"{type(exc).__name__}: {exc}"[:2000],
                traceback=traceback.format_exc()[:8000],
            )

    return recorder.finalise(
        result,
        peak_rss_mb=memory.peak_mb,
        llm_seconds=client.total_llm_seconds,
        schema_valid=validate(result.output),
        hard_gate_passed=hard_gate(result.output),
    )


def run_with_retries(
    *,
    cfg: dict[str, Any],
    make_attempt: Callable[[int], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Harness-level retry. Every attempt is a separate logged record with its
    own tokens and latency -- a retry is never invisible in the cost or timing
    figures (Section 3.8.3)."""
    policy = cfg["experiment"]["retry_policy"]
    max_retries = policy["max_retries"]
    base = policy["backoff_base_seconds"]

    attempts: list[dict[str, Any]] = []
    for attempt_index in range(max_retries + 1):
        record = make_attempt(attempt_index)
        attempts.append(record)
        if record["status"] == "success":
            break
        category = record.get("failure_category")
        if category not in {c.value for c in RETRYABLE}:
            break
        if attempt_index < max_retries:
            time.sleep(base * (2 ** attempt_index))

    for record in attempts:
        record["is_final_attempt"] = False
    attempts[-1]["is_final_attempt"] = True
    return attempts


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the benchmark.")
    parser.add_argument("--frameworks", nargs="*", default=None)
    parser.add_argument("--tasks", nargs="*", default=None)
    parser.add_argument("--runs", type=int, default=None,
                        help="Override runs_per_cell (use 1 for a pilot).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the schedule and exit; makes no API calls.")
    args = parser.parse_args()

    cfg = load_config()
    if args.runs is not None:
        cfg["experiment"]["runs_per_cell"] = args.runs

    schedule = build_schedule(cfg)
    if args.frameworks:
        wanted = {f.lower() for f in args.frameworks}
        schedule = [e for e in schedule if e["framework"] in wanted]
    if args.tasks:
        schedule = [e for e in schedule if e["task_id"] in args.tasks]

    run_group = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    print(f"run_group={run_group}  attempts_planned={len(schedule)}  "
          f"config_hash={config_hash(cfg)}")

    if args.dry_run:
        for entry in schedule[:20]:
            print(entry)
        if len(schedule) > 20:
            print(f"... {len(schedule) - 20} more")
        return

    logger = RunGroupLogger(RAW_LOGS, run_group)
    logger.write_json("manifest.json", {
        "run_group": run_group,
        "config_hash": config_hash(cfg),
        "config": cfg,
        "schedule": schedule,
    })
    # Adapter dispatch and TaskInstance loading are wired in
    # benchmark/common/registry.py and benchmark/common/tasks.py.
    raise SystemExit(
        "Adapters are not yet implemented. Run with --dry-run to inspect the "
        "schedule; see docs/experiment_log.md for implementation status."
    )


if __name__ == "__main__":
    main()
