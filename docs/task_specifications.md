# Task Specifications — Index

All five specifications are complete as of Phase 1 (2026-08-23). The suite stays
at five: a smaller, well-controlled benchmark is stronger than a large, poorly
controlled one, and every task multiplies out across 3 frameworks × 10 runs.
Authoritative specs live in `tasks/<task_folder>/scope.md`.

The tasks are chosen to differ in **coordination pattern**, not just subject
matter — five tasks demanding the same control flow would measure one framework
capability five times.

| ID | Name | Coordination pattern | Spec | Fixtures |
|---|---|---|---|---|
| T1 | Research Synthesis Agent | Parallel fan-out, then merge | Complete | Not Started |
| T2 | Customer Support Triage | Sequential + conditional branch | Complete | Not Started |
| T3 | Data Cleaning Pipeline | Sequential + tool execution | Complete | Not Started |
| T4 | Travel Planning Assistant | Iterative constraint-repair loop | Complete | Not Started |
| T5 | Code Review and Refactoring Agent | Critique + revision + verify gate | Complete | Not Started |

**Fixture work is the Phase 1 → Phase 2 handoff.** Each task's hard gate depends
on a golden reference that does not exist yet:

| Task | Fixture to build |
|---|---|
| T1 | `corpus_v1`: 40 abstracts, relevance labels, 6 near-misses, 2 contradictory pairs |
| T2 | `batch_v1`: 12 gold-labelled tickets, 4 requiring escalation, 1 injection attempt |
| T3 | `sales_raw_v1`: 200 rows, 6 injected defect classes + injection manifest + golden clean CSV |
| T4 | `options_v1`: transport/lodging/activity table, **calibrated** so a naive plan overruns budget by 15–25% |
| T5 | `inventory_v1`: ~180-line module, 4 seeded defects, 3 false-positive traps, test suite + hidden tests |

Calibration must be confirmed by pilot runs (`--runs 1`) before the 150-run
group. If all three frameworks floor or ceiling on a task, the fixture is wrong
— that is not a finding about the frameworks.

## One-line descriptions

- **T1 – Research Synthesis Agent**: Retrieve and summarize recent papers on a topic; produce a structured report.
- **T2 – Customer Support Triage**: Classify incoming tickets, draft responses, and escalate complex cases.
- **T3 – Data Cleaning Pipeline**: Load raw CSV, detect issues, apply transformations, output cleaned data.
- **T4 – Travel Planning Assistant**: Generate multi-city itinerary with constraints (budget, time, preferences).
- **T5 – Code Review & Refactoring Agent**: Analyze a code snippet, suggest improvements, and produce refactored code.

## Status Definitions

- **Not Started**: No work has begun.
- **In Progress**: Active work is underway.
- **Blocked**: Work cannot continue because a decision, tool, or dependency is missing.
- **Ready for Review**: Draft or implementation is complete and needs checking.
- **Complete**: Meets the acceptance criteria.
- **Deferred**: Intentionally moved outside the current study.

### Completion criteria (examples)

- "Framework selection complete" means a written justification exists.
- "Task specification complete" means objective, input, output, workflow, and evaluation criteria are documented.
- "Experiment complete" means raw logs and configuration files exist.
- "Results complete" means the result can be reproduced from raw logs.
