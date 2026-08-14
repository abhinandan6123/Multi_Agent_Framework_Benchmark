# Metric Definitions

Precise definitions for every metric used in the study. Fill in the "How Measured" column before running any experiments — do not leave a metric in the results section that isn't defined here first.

## Performance

| Metric | Definition | How Measured |
|---|---|---|
| Task Completion Rate | Binary success/failure per run | PENDING |
| Accuracy / F1 | For tasks with structured outputs | PENDING |
| Reasoning Quality | Rubric-based score (e.g., 1–5) | PENDING |

## Efficiency

| Metric | Definition | How Measured |
|---|---|---|
| End-to-End Latency | Wall-clock time from task start to final output | PENDING |
| Throughput | Tasks completed per unit time under concurrent load | PENDING |
| Token Usage | Input + output tokens per task and per agent | PENDING |
| API Cost | Derived from token counts and provider pricing | PENDING |

## Reliability

| Metric | Definition | How Measured |
|---|---|---|
| Failure Rate | Fraction of runs with unhandled exceptions or invalid outputs | PENDING |
| Recovery Success | Fraction of failures where retry/self-correction succeeds | PENDING |
| Consistency | Variance in outputs across runs (e.g., semantic similarity) | PENDING |

## Resource Usage

| Metric | Definition | How Measured |
|---|---|---|
| Memory Footprint | Peak RAM usage | PENDING |
| Concurrency Behavior | Performance degradation under parallel tasks | PENDING |

## Engineering

| Metric | Definition | How Measured |
|---|---|---|
| Lines of Code (LOC) | Framework-specific implementation size for the task suite | PENDING |
| Development Time | Hours to implement and debug each framework's version | PENDING |
| Debugging Effort | Subjective score or issue count | PENDING |
| Maintainability | Code modularity, clarity, ease of extension (rubric-based) | PENDING |
