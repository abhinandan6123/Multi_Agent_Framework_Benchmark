# Metric Definitions

Normative definitions for every metric reported in this study. No quantity may
appear in the results section unless it is defined here first. Column names
refer to `docs/log_schema.md`.

**Reporting conventions.** Skewed distributions (latency, tokens, cost) are
reported as median with IQR and a bootstrap percentile CI (10,000 resamples).
Proportions are reported with Wilson score intervals. Rubric scores are
reported as medians with inter-judge agreement. Means are used only where the
distribution is approximately symmetric, and never for latency.

---

## Performance

| Metric | Definition | How Measured |
|---|---|---|
| Task Completion Rate | Fraction of replications where the run terminated cleanly, produced schema-valid output, and passed the task's hard gate. All three necessary; binary per run. | `runs.csv.success` aggregated per cell. Wilson interval. Between-framework comparison by Fisher's exact test, Holm-corrected. |
| Accuracy / F1 | Task-specific deterministic correctness against the golden reference. No LLM involved. | `accuracy_primary`, computed by `benchmark/common/scoring.py`. T1: retrieval F1 vs. labelled relevance set. T2: macro-F1 over category/severity/escalation labels. T3: cell-level agreement vs. golden cleaned CSV. T4: fraction of hard constraints satisfied. T5: seeded-defect recall (with false positives reported separately). |
| Reasoning Quality | Rubric score 1–5 on faithfulness, grounding, internal consistency, completeness. | Three independent `claude-opus-5` judges (`effort: high`), blinded to framework identity, per dimension; per-run score is the median across judges. Rubric and prompts in Appendix A; every verdict in `judge.jsonl`. Krippendorff's α (ordinal) reported alongside — a rubric score with low judge agreement is discounted, not presented as fact. |

## Efficiency

| Metric | Definition | How Measured |
|---|---|---|
| End-to-End Latency | Wall-clock seconds from adapter entry to final output return, including all model calls, tool execution, framework overhead, network round trip, and any harness retries within the run. | `time.monotonic()` bracket in `benchmark/common/harness.py`. `runs.csv.latency_seconds`. Median + IQR + bootstrap CI; Kruskal–Wallis then Mann–Whitney U with Holm correction and Cliff's delta. |
| Framework Overhead | Latency minus summed model-call duration minus summed tool duration. The network-insensitive component of the latency comparison. | `overhead_seconds`, derived. Asserted non-negative. |
| Throughput | Successful completions per minute at concurrency 1/2/4/8. | `concurrency.csv`. T2 and T3 only, 8 runs per level — a cost-bounded sweep, reported as such. Batch wall clock ÷ successful completions. |
| Token Usage | Input, output, cache-read, cache-write tokens per run and per agent role. | Provider `usage` field on every response, summed. **No local tokenizer is used** — the billed count is the reported count. `runs.csv`, `steps.csv`. |
| API Cost | Tokens × fixed pricing snapshot (2026-08-23: \$3.00/MTok input, \$15.00/MTok output; cache read 0.1×, cache write 1.25×). Standard list price, not the promotional intro rate. | Derived in `metrics.py`, never logged — so a pricing correction never requires re-running an experiment. Reported per run **and per 100 successful completions**; the latter is the decision-relevant figure, since a cheap framework that fails often is not cheap. Judge tokens excluded (measurement apparatus, not system under test). |

## Reliability

| Metric | Definition | How Measured |
|---|---|---|
| Failure Rate | Fraction of replications not meeting the success predicate, broken out by a closed seven-category taxonomy. | `runs.csv.failure_category`. Reported **by category**, not only in aggregate — the categories imply different engineering remedies. Categories: `exception`, `timeout`, `step_limit`, `schema_invalid`, `constraint_violation`, `tool_error`, `transport_error`. |
| Recovery Success | Of replications where attempt 0 failed and a retry was issued, the fraction ultimately succeeding. Max 2 retries, exponential backoff (base 4 s). | `attempts.csv`. Every attempt is a separate logged record with its own tokens and latency, so retries are never invisible in cost or timing. `transport_error` retries reported **separately** from framework-side retries: the former measures the provider, the latter the framework, and conflating them would credit a framework for network recovery it did not perform. |
| Output Consistency | Run-to-run variability within a cell, three ways. | `consistency.csv`. Structured fields: exact agreement rate over 10 runs. Free text: mean pairwise cosine of sentence embeddings over 45 pairs. Scalars: coefficient of variation. Measured as an outcome because determinism is unavailable on this model (no temperature control — see Section 3.6). |

## Resource Usage

| Metric | Definition | How Measured |
|---|---|---|
| Memory Footprint | Peak RSS of the worker process during a run. Orchestration footprint only — model weights are remote, so absolute values are modest and only the relative comparison is meaningful. | `psutil` sampled at 100 ms by a monitor thread; maximum retained. `runs.csv.peak_rss_mb`. |
| Concurrency Behaviour | Degradation in median latency and completion rate as concurrency rises 1→8; reported as a scaling curve with the level at which completion rate first degrades. | `concurrency.csv`. Sweep tops out at 8; no claim is made about production-scale behaviour. |

## Engineering

The most construct-fragile metrics in the study. Reported as components, never
aggregated into a single "productivity" score — such a score would imply a
precision these constructs do not have.

| Metric | Definition | How Measured |
|---|---|---|
| Lines of Code | Non-blank, non-comment lines of **orchestration** code per adapter. | `cloc` over a fixed per-adapter file list. Shared code (prompts, tools, harness) counted separately and excluded from comparison — it is identical by construction and including it would dilute the signal. Counted only after all three adapters are functionally equivalent, so no framework is credited for an unfinished adapter. Reported alongside maintainability and never read as a quality measure alone: a declarative framework produces fewer lines almost by construction. |
| Development Time | Hours to a working adapter, split into implementation and debugging, per (framework, task). | Recorded **contemporaneously** in `docs/experiment_log.md`, not reconstructed afterwards. `engineering.csv`. Confounded by learning order; `implementation_order` is carried into the data so the confound is analysable. A shared design pass fixing agent topology and prompts precedes all framework-specific code, so shared design cost is not charged to the first framework; a uniform hardening pass after all three work equalises maturity. Reported as indicative, not as a measurement supporting a general claim. |
| Debugging Effort | Count of distinct non-trivial defects (more than a typographical fix) per framework, with root-cause category. | Logged at time of occurrence with description and category (framework API misuse / framework defect / prompt-format issue / integration issue). An auditable incident count rather than a subjective difficulty score; the incident log is published so a reader can re-categorise. |
| Maintainability | Rubric 1–5 on modularity, control-flow clarity, state-management explicitness, testability, extension cost. | Three-judge `claude-opus-5` ensemble on framework-anonymised adapter code (median), **plus** an independent implementer self-assessment. Both reported. Disagreement between them is reported rather than resolved — the disagreement is itself a finding. |
| Learning Curve | Qualitative, from the contemporaneous log: time to first working single-agent run, and the number of documentation lookups required. | Reported narratively in Section 4, not as a number. Insufficiently operationalised to quantify from n = 1 developer, and we do not pretend otherwise. |

---

## Metrics deliberately not reported

Listed so their absence is a decision rather than an omission:

- **Mean latency** — the distributions are right-skewed; a mean would misstate them.
- **Locally-estimated token counts** — the provider's billed count is authoritative.
- **A composite framework score** — the metrics trade off against each other; collapsing them would hide exactly the trade-off the paper is about.
- **Statistical significance without effect size** — every pairwise test reports Cliff's delta, because at n = 10 a significant negligible difference has no engineering meaning.
