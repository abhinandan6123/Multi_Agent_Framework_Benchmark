"""Metric computation -- pipeline stage 4 of Section 3.2.

Reads raw JSONL logs, writes the tidy CSVs of docs/log_schema.md. Cost is
derived here rather than logged, so a pricing correction never requires
re-running an experiment.

Runs with no API access, which is what makes the reproducibility contract in
Section 3.2 real: given the published logs, every number in Section 5 can be
regenerated offline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_CSV = REPO_ROOT / "results" / "csv"

VALID_FAILURE_CATEGORIES = {
    "exception", "timeout", "step_limit", "schema_invalid",
    "constraint_violation", "tool_error", "transport_error",
}


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return iter(())
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def compute_cost(row: pd.Series, pricing: dict[str, Any], model: str) -> float:
    rates = pricing[model]
    per_million = 1_000_000
    return (
        row["input_tokens"] * rates["input"]
        + row["output_tokens"] * rates["output"]
        + row["cache_read_tokens"] * rates["input"] * pricing["cache_read_multiplier"]
        + row["cache_write_tokens"] * rates["input"] * pricing["cache_write_multiplier"]
    ) / per_million


def build_attempts(run_group_dir: Path, cfg: dict[str, Any]) -> pd.DataFrame:
    df = pd.DataFrame(read_jsonl(run_group_dir / "runs.jsonl"))
    if df.empty:
        raise ValueError(f"no runs recorded in {run_group_dir}")
    df["cost_usd"] = df.apply(
        compute_cost, axis=1, pricing=cfg["pricing"], model=cfg["llm"]["model"]
    )
    df["total_tokens"] = df["input_tokens"] + df["output_tokens"]
    df["success"] = df["status"] == "success"
    return df


def assert_invariants(attempts: pd.DataFrame, runs: pd.DataFrame, cfg: dict[str, Any],
                      *, strict: bool) -> list[str]:
    """Checked rather than assumed. See docs/log_schema.md.

    `strict` is off for pilot runs (where a partial grid is expected) and on for
    the measured run group that the paper reports.
    """
    problems: list[str] = []
    n_frameworks = len(cfg["frameworks"])
    n_tasks = len(cfg["tasks"])
    runs_per_cell = cfg["experiment"]["runs_per_cell"]
    expected = n_frameworks * n_tasks * runs_per_cell

    if strict and len(runs) != expected:
        problems.append(f"expected {expected} replications, found {len(runs)}")

    cell_counts = runs.groupby(["framework", "task_id"]).size()
    if strict:
        bad = cell_counts[cell_counts != runs_per_cell]
        if not bad.empty:
            problems.append(f"cells with wrong run count: {bad.to_dict()}")

    finals = attempts.groupby(["framework", "task_id", "replication"])[
        "is_final_attempt"
    ].sum()
    if (finals != 1).any():
        problems.append("some replications lack exactly one is_final_attempt")

    derived = (attempts["terminated_cleanly"]
               & attempts["schema_valid"]
               & attempts["hard_gate_passed"])
    if not (derived == attempts["success"]).all():
        problems.append("success flag inconsistent with its three components")

    fails = attempts[~attempts["success"]]["failure_category"]
    unknown = set(fails.dropna().unique()) - VALID_FAILURE_CATEGORIES
    if unknown:
        problems.append(f"failure_category outside the closed set: {unknown}")
    if attempts[attempts["success"]]["failure_category"].notna().any():
        problems.append("successful attempt carries a failure_category")

    if (attempts["overhead_seconds"] < -1e-6).any():
        problems.append("negative framework overhead (latency < llm + tool time)")

    if attempts["config_hash"].nunique() > 1:
        problems.append("run group mixes multiple config hashes")

    if (attempts["framework_version"] == "PENDING_INSTALL").any():
        problems.append("a run recorded framework_version=PENDING_INSTALL")

    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_group_dir", type=Path)
    parser.add_argument("--config", type=Path,
                        default=REPO_ROOT / "benchmark" / "config.yaml")
    parser.add_argument("--strict", action="store_true",
                        help="Enforce the full-grid invariants (measured runs).")
    args = parser.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    attempts = build_attempts(args.run_group_dir, cfg)
    runs = attempts[attempts["is_final_attempt"]].copy()

    retries = (attempts.groupby(["framework", "task_id", "replication"]).size() - 1)
    runs = runs.merge(
        retries.rename("attempts_used").reset_index(),
        on=["framework", "task_id", "replication"], how="left",
    )
    runs["attempts_used"] = runs["attempts_used"].fillna(0) + 1
    runs["recovered_after_failure"] = runs["success"] & (runs["attempts_used"] > 1)

    problems = assert_invariants(attempts, runs, cfg, strict=args.strict)
    if problems:
        for problem in problems:
            print(f"INVARIANT VIOLATION: {problem}")
        raise SystemExit(1)

    RESULTS_CSV.mkdir(parents=True, exist_ok=True)
    attempts.to_csv(RESULTS_CSV / "attempts.csv", index=False)
    runs.to_csv(RESULTS_CSV / "runs.csv", index=False)

    steps = pd.DataFrame(read_jsonl(args.run_group_dir / "steps.jsonl"))
    if not steps.empty:
        steps.to_csv(RESULTS_CSV / "steps.csv", index=False)

    print(f"wrote {len(runs)} replications / {len(attempts)} attempts "
          f"to {RESULTS_CSV}")


if __name__ == "__main__":
    main()
