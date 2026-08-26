# Research Decisions

## Working Title

Comparative Evaluation of Multi-Agent AI Frameworks for Real-World Task Automation

## Optional Subtitle

A Reproducible Benchmarking Study of LangGraph, CrewAI, and AutoGen

## Target Venue

IEEE International Conference on Agentic AI

## Full Paper Format

Internal master manuscript: approximately 18–22 pages before compression.

## IEEE Submission Format

IEEE ICA 2026 regular paper: maximum 6 pages, using the official IEEE Conference Proceedings format.

## Frameworks

- LangGraph
- CrewAI
- AutoGen

## Task Suite

- T1: Research Synthesis Agent
- T2: Customer Support Triage
- T3: Data Cleaning Pipeline
- T4: Travel Planning Assistant
- T5: Code Review and Refactoring Agent

## Evaluation Dimensions

### Performance
- Task completion rate
- Accuracy or F1 where applicable
- Reasoning quality

### Efficiency
- End-to-end latency
- Throughput
- Token usage
- API cost

### Reliability
- Failure rate
- Recovery success
- Output consistency

### Resource Usage
- Memory footprint
- Concurrency behavior

### Engineering
- Lines of code
- Development time
- Debugging effort
- Maintainability
- Learning curve

## Planned Replication

Multiple runs per task and framework. Final run count to be fixed before experiments.

## Open-Source Artifacts

- Benchmark code
- Framework adapters
- Task definitions
- Prompts
- Evaluation scripts
- Statistical analysis
- Figures and tables
- Reproduction instructions

---

## Decisions Locked (Phase 1, 2026-08-23)

The master rule still holds: **do not claim that a factor is controlled until you
have actually controlled it.** Everything below is either verified against the
machine/API or recorded as explicitly not-yet-verified. The machine-readable
source of truth is `benchmark/config.yaml`.

| Item | Status | Value |
|---|---|---|
| LLM | **Locked** | `claude-sonnet-5`, Anthropic first-party Claude API, 1M context |
| Provider | **Locked** | Anthropic first-party Claude API (no Bedrock/Vertex) |
| Temperature | **Not controllable** | Claude Sonnet 5 removed `temperature`/`top_p`/`top_k`; sending them returns HTTP 400. Reasoning effort is fixed at `medium` as the controllable analogue. See below. |
| Maximum tokens | **Locked** | 4096 per response, every agent role |
| Thinking / effort | **Locked** | `thinking: disabled`, `output_config.effort: medium` |
| Hardware | **Locked (verified)** | Apple M4 Pro, 14 cores, 24 GB RAM, macOS 15.3.1 (24D70). GPU unused — all inference remote. |
| Python | **Locked (verified)** | CPython 3.11.7 |
| Framework versions | **Pending install** | Recorded automatically by `benchmark/scripts/record_environment.py`; deliberately not hand-written. None of the three is installed yet. |
| Number of runs | **Locked** | 10 per (framework, task) cell → 150 measured runs |
| Run order | **Locked** | Interleaved round-robin over all 15 cells, seeded (`20260823`) |
| Tool access | **Locked** | Per-task closed tool sets, all hermetic (local corpus, static tables, local CSV, subprocess pytest). No network access from any tool. |
| Evaluation method | **Locked** | Hybrid. Deterministic rules + golden references for all hard gates and accuracy; 3-judge `claude-opus-5` ensemble (median, blinded) for rubric dimensions only. No task is scored by rubric alone. |
| Judge model | **Locked** | `claude-opus-5`, `effort: high`, 3 judges, median aggregation, blinded to framework |
| Cost calculation | **Locked** | Pricing snapshot 2026-08-23: `claude-sonnet-5` \$3.00/\$15.00 per MTok (standard list, **not** the intro rate). Cache read 0.1×, cache write 1.25×. Derived from logged tokens; judge tokens excluded. |
| Scalability test | **Locked** | Concurrency 1/2/4/8 on T2 and T3 only, 8 runs per level. A cost-bounded sweep, reported as such. |
| Developer study | **Locked** | Single developer (`akash.shastri@query.ai`). Time recorded contemporaneously in `docs/experiment_log.md`, split implementation/debugging. Implementation order carried into `engineering.csv` so the learning-order confound is analysable, not merely disclosed. |
| Statistics | **Locked** | Kruskal–Wallis omnibus, Mann–Whitney U pairwise, Holm correction, Cliff's delta, Fisher's exact for proportions, bootstrap percentile CIs (10,000 resamples), α = 0.05 |

### Note on the absence of temperature control

This is the most consequential Phase 1 finding and it is a genuine constraint,
not an oversight. Claude Sonnet 5 does not accept sampling parameters, so
`temperature = 0` is unavailable. Consequences, all handled explicitly in
Section 3.1/3.6/3.9:

- Run-level determinism is impossible; we do not claim it.
- Variability is measured as an outcome (output-consistency metric) rather than
  suppressed as a nuisance.
- One confounder is *removed*: no framework can silently differ from another via
  its default sampling settings. Adapters assert this at build time
  (`benchmark/common/llm.py: assert_no_sampling_params`).

If a future version of the study needs temperature control, it requires a
different model, and that changes the LLM constant — so it would be a new run
group, not a patch to this one.
