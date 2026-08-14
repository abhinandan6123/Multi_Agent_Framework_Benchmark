# Comparative Evaluation of Multi-Agent AI Frameworks for Real-World Task Automation

A reproducible benchmarking study of **LangGraph**, **CrewAI**, and **AutoGen** across performance, efficiency, reliability, resource usage, and engineering (developer-productivity) dimensions.

## Status

**Phase 0 — Setup** (started 2026-08-14). See `docs/experiment_log.md` for the running log.

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

## Reproducibility Rule

Do not claim a factor is controlled until it has actually been controlled. Unknown configuration values are marked `PENDING` in `benchmark/config.yaml` and `docs/research_decisions.md` until locked.
