# Comparative Evaluation of Multi-Agent AI Frameworks for Real-World Task Automation

A reproducible benchmarking study of **LangGraph**, **CrewAI**, and **AutoGen** across performance, efficiency, reliability, resource usage, and engineering (developer-productivity) dimensions.

## Status

**Phase 1 — Methods & Reproducibility Core** (2026-08-23). Section 3 is written,
all constants are locked, and the shared harness is implemented. Framework
adapters are not yet built and no experiments have been run — see
`docs/experiment_log.md` for the running log and the explicit pending list.

## Project Structure

```text
multi-agent-framework-benchmark/
│
├── paper/              # Full-version and IEEE-version manuscript workspaces
├── benchmark/          # Framework adapters, shared harness, config.yaml
├── tasks/              # T1–T5 task scope specs
├── experiments/        # Configs, raw logs, run outputs
├── results/            # CSVs, statistics, summaries
├── figures/            # Generated plots
├── tables/             # Generated tables
├── appendices/         # Prompts, configs, extra results, cost breakdown, hyperparameters
├── docs/                # Research decisions, task specs, metric definitions, experiment log
└── README.md
```

## Key Documents

- `docs/research_decisions.md` — locked and pending research decisions (source of truth).
- `docs/task_specifications.md` — index of the five-task suite (T1–T5).
- `docs/metric_definitions.md` — precise definitions for every metric reported.
- `docs/experiment_log.md` — running day-by-day log (update daily).
- `benchmark/config.yaml` — single source of truth for experiment configuration.
- `docs/log_schema.md` — **frozen contract** for raw logs and derived CSVs.
- `paper/full_version/section_03_methodology.md` — the written methodology (Section 3).

## Frameworks Compared

- LangGraph
- CrewAI
- AutoGen

## Task Suite

- T1: Research Synthesis Agent
- T2: Customer Support Triage
- T3: Data Cleaning Pipeline
- T4: Travel Planning Assistant
- T5: Code Review and Refactoring Agent

## Locked Configuration

| Factor | Value |
|---|---|
| Model | `claude-sonnet-5` (Anthropic first-party API), 1M context |
| Parameters | `max_tokens` 4096, `thinking` disabled, `effort` medium |
| Sampling | **Not controllable** — Sonnet 5 rejects `temperature`/`top_p`/`top_k` |
| Runs | 10 per (framework, task) cell → 150 runs, interleaved round-robin, seed 20260823 |
| Evaluation | Hybrid: deterministic rules/golden refs for hard gates; blinded 3-judge `claude-opus-5` ensemble for rubrics only |
| Pricing snapshot | 2026-08-23, \$3.00/\$15.00 per MTok (standard list, not intro rate) |
| Host | Apple M4 Pro, 14 cores, 24 GB, macOS 15.3.1, CPython 3.11.7 |

Framework versions are **not** hand-written — they are recorded by
`benchmark/scripts/record_environment.py` and the metric layer refuses any run
group still carrying `PENDING_INSTALL`.

## Running It

```bash
python benchmark/scripts/record_environment.py        # record actual versions
python -m benchmark.common.harness --dry-run          # inspect the run schedule
python -m benchmark.common.harness --runs 1           # pilot (needs adapters + API key)
python -m benchmark.common.metrics <run_group_dir> --strict   # derive CSVs, offline
```

The metric and analysis stages need **no API access**: given the published raw
logs, every number in the results section can be regenerated offline.

## Reproducibility Rule

Do not claim a factor is controlled until it has actually been controlled. Unknown configuration values are marked `PENDING` in `benchmark/config.yaml` and `docs/research_decisions.md` until locked.
