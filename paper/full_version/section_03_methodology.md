# 3. Experimental Methodology

> **Status:** Phase 1 draft. Every value in this section is mirrored in
> `benchmark/config.yaml`, which is the machine-readable source of truth. If the
> two disagree, `config.yaml` wins and this section is stale.

This section specifies the study in enough detail to be replicated
independently. We state the design, the controlled and manipulated factors, the
exact software and model configuration, the task suite, the metric definitions
and their measurement procedures, and the threats to validity that follow from
the choices we made.

---

## 3.1 Research Design

**Study type.** A controlled experimental benchmark. The object of study is the
*orchestration framework*, not the underlying language model; the model is held
fixed so that observed differences are attributable to how each framework
structures agent coordination, state, tool invocation, and error handling.

**Design.** A within-subjects (repeated-measures) factorial design with two
crossed factors:

| Factor | Type | Levels |
|---|---|---|
| Framework | Manipulated (independent variable) | LangGraph, CrewAI, AutoGen |
| Task | Manipulated (blocking factor) | T1–T5 |

Every framework executes every task, giving a fully crossed 3 × 5 design with
10 replications per cell — 150 measured runs. Because each task is attempted by
all three frameworks, task difficulty is a within-subjects blocking factor
rather than a between-subjects confound, and framework comparisons are made
within task before being aggregated.

**Controlled factors.** Held identical across all three frameworks:

- The language model, its version, and every model parameter (§3.6).
- The task inputs, byte-for-byte, drawn from a versioned fixture set.
- The agent-role decomposition and the semantic content of every system and
  role prompt (§3.6, Appendix A). Only framework-specific orchestration
  scaffolding differs.
- The tool implementations. All three adapters import the *same* Python tool
  functions from `benchmark/common/tools.py`; only the framework-native
  registration wrapper differs.
- The per-run step ceiling (25 agent steps), wall-clock timeout (600 s), and
  retry policy (§3.8.3).
- The host machine, operating system, and Python interpreter (§3.4, §3.5).

**Manipulated factor.** The framework, and strictly nothing else that we can
control.

**Replication strategy.** Ten runs per (framework, task) cell. Ten is chosen
so that non-parametric interval estimation is usable at the cell level: with
n = 10 the bootstrap percentile interval on a cell median is informative, and
the framework-level comparisons pool 50 runs per framework. Runs are executed
in **interleaved round-robin order** over all 15 cells rather than
cell-by-cell, so that any drift in provider-side latency, load, or model
serving during the measurement window is spread evenly across frameworks
instead of being absorbed by whichever framework happened to run last. The
harness-side pseudo-random choices (run ordering, selection of input instance
per replication, judge sampling) are seeded from a fixed seed (`20260823`) and
the resulting order is written to the run manifest, so the *schedule* of the
experiment is exactly reproducible even though the model's outputs are not.

**On determinism.** We do not claim run-level determinism, and we could not
obtain it even if we wanted to: Claude Sonnet 5 does not expose sampling
parameters (§3.6), so `temperature = 0` is unavailable as a variance-reduction
device. This is a deliberate methodological trade-off. We treat stochasticity
as a property of the system under test and characterise it, reporting
distributions with dispersion and confidence intervals rather than point
estimates, and measuring run-to-run variability directly as a reliability
metric (§3.8.3, *output consistency*). Because the stochasticity is identical
in kind across frameworks, it inflates within-cell variance symmetrically and
does not bias between-framework comparison.

---

## 3.2 Experimental Workflow

**Figure 1** shows the end-to-end pipeline. Control flows left to right; every
stage writes to disk before the next stage reads, so any stage can be re-run
from persisted artefacts without re-invoking the model.

```
 ┌────────────┐   ┌────────────┐   ┌──────────────┐   ┌────────────┐
 │ Task spec  │   │ Framework  │   │   Unified    │   │  Metric    │   ┌──────────┐
 │  + fixture │──▶│  adapter   │──▶│    logger    │──▶│ computation│──▶│ Analysis │
 │  loader    │   │   layer    │   │ (JSONL runs) │   │  + judge   │   │ + figures│
 └────────────┘   └────────────┘   └──────────────┘   └────────────┘   └──────────┘
   tasks/          benchmark/{lg,   experiments/       results/csv/      results/
   fixtures/        crewai,autogen} raw_logs/                           statistics/
```

**Stage 1 — Task loader.** Reads the task specification and a versioned input
fixture from `tasks/<task>/fixtures/`, and emits a `TaskInstance`: the input
payload, the output JSON schema, the golden reference (where one exists), and
the rubric identifier. The loader is framework-agnostic; all three adapters
receive an identical `TaskInstance`.

**Stage 2 — Framework adapter layer.** Each framework implements one interface,
`FrameworkAdapter.run(task_instance) -> RunResult`. The adapter is responsible
only for orchestration: constructing the framework's native agent topology,
executing it, and returning the final output plus a per-step trace. Everything
that is *not* orchestration — prompts, tools, the schema, and the model client
configuration — is injected from shared code so that it cannot drift between
adapters.

**Stage 3 — Unified logger.** A single instrumentation layer, shared by all
adapters, records one JSONL record per run and one per agent step. It captures
wall-clock timings, per-call token counts read from the provider's `usage`
field, every model request and response, tool invocations and their results,
exceptions with tracebacks, retry attempts, and peak resident memory. Token
counts are never estimated by a local tokenizer; they are taken from the API
response, which is the billed quantity. The log schema is specified in
`docs/log_schema.md` and is treated as a frozen contract.

**Stage 4 — Metric computation.** Consumes raw logs and produces one tidy CSV
row per run. Deterministic metrics (latency, tokens, cost, failure, schema
validity, rule-based accuracy) are computed directly from the logs. Rubric
metrics (reasoning quality, maintainability) are produced by an LLM-judge
ensemble (§3.8.1) whose prompts, model, and raw verdicts are themselves logged.

**Stage 5 — Analysis.** Reads the tidy CSVs and emits the statistical summary
tables, hypothesis tests, and figures. It performs no data cleaning: any run
excluded from an analysis must be excluded by an explicit, logged rule, and the
count of exclusions is reported.

**Reproducibility contract.** The pipeline is re-entrant at every stage
boundary. Given the published raw logs, every number, table, and figure in
Section 5 can be regenerated with no API access at all. Given API access and
the pinned dependency set, the raw logs can be regenerated, though not
byte-identically (§3.1, *On determinism*).

---

## 3.3 Framework Selection Criteria

We selected three frameworks by applying explicit inclusion and exclusion
criteria to the population of general-purpose multi-agent orchestration
libraries.

**Inclusion criteria.** A framework was eligible if it satisfied all of:

1. **Active maintenance** — a release within the six months preceding the
   measurement window.
2. **Substantive adoption** — evidence of production use beyond demonstration
   code, indicated by package download volume and repository activity.
3. **Documented public API** — an orchestration API stable enough to target
   without reading library internals.
4. **Model-provider neutrality** — the ability to substitute the language model
   without rewriting the orchestration layer. This is a prerequisite for the
   study design, since the model must be held constant while the framework
   varies.
5. **General-purpose scope** — not restricted to a single vertical domain.

**Exclusion criteria.** A framework was excluded if any of:

1. It is explicitly experimental or pre-release, so that measurements would not
   describe anything a practitioner could adopt.
2. It is coupled to one provider or one model family, breaking criterion 4.
3. It is a thin wrapper over another framework in the study, which would
   produce a redundant rather than an independent data point.
4. It is a hosted service without a self-hostable execution path, which would
   make hardware and network conditions uncontrollable.

**Why these three.** The surviving candidates cluster into a small number of
architectural paradigms, and we sampled one representative from each so that
the comparison spans the design space rather than three points within one
region of it:

| Framework | Paradigm | Coordination primitive | Control flow |
|---|---|---|---|
| LangGraph | Explicit state graph | Node over a shared typed state object | Programmer-specified edges, conditional branching, explicit cycles |
| CrewAI | Role-based crew | Agent with a role, goal, and assigned task | Declared task sequence and dependency order |
| AutoGen | Conversational multi-agent | Message exchange between conversable agents | Emergent from conversation, bounded by termination conditions |

These three differ on the axis that matters most for the research questions:
**where control flow is decided.** LangGraph places it in code the developer
writes; CrewAI places it in a declarative task/role configuration; AutoGen
delegates it to the model via conversation. Contrasting the three therefore
contrasts explicit orchestration against declarative orchestration against
emergent orchestration, which is precisely the trade-off a practitioner faces.

**Scope limitation.** Three frameworks is a sample, not a census, and the
paradigm-representative sampling means results describe the paradigms at least
as much as the specific libraries. We revisit this in §3.9 and in the
limitations section.

---

## 3.4 Hardware Configuration

All runs were executed from a single host, recorded verbatim:

| Component | Specification |
|---|---|
| Machine | Apple Mac, arm64 |
| CPU | Apple M4 Pro, 14 cores |
| RAM | 24 GB |
| GPU | Integrated Apple GPU — **unused**; no local inference was performed |
| Operating system | macOS 15.3.1 (build 24D70) |
| Network | Consumer broadband, wired, single geographic location |

**The host is not the compute bottleneck.** Every language-model call is a
remote HTTPS request to the provider's API. The host performs orchestration,
tool execution, and logging only, so hardware specifications matter for
reproducibility disclosure and for the resource-usage metrics (§3.8.4), not for
inference throughput.

**Network variability is a first-order threat, and we mitigate it by design
rather than by assertion.** Because latency includes the network round trip and
provider-side queueing, absolute latency figures are properties of this
measurement environment. Two mitigations apply: runs are interleaved across
frameworks (§3.1), so provider-side drift affects all three frameworks
equally; and we report a network-independent efficiency measure — token counts,
which are unaffected by transport — alongside wall-clock latency. Where a
latency claim is made, it is a *relative* claim between frameworks measured in
the same interleaved window.

---

## 3.5 Software Stack

| Component | Version |
|---|---|
| Python | 3.11.7 (CPython) |
| LangGraph | recorded at install time |
| CrewAI | recorded at install time |
| AutoGen | recorded at install time |
| `anthropic` SDK | recorded at install time |
| `pandas` | 3.0.3 |
| `numpy` | 2.4.6 |
| `scipy` | 1.17.1 |
| Containerisation | Not used |

**Version recording policy.** Framework versions are deliberately *not*
hand-written into this section. `benchmark/scripts/record_environment.py`
interrogates the installed distributions and writes the full resolved
dependency graph, interpreter build, and platform triple to
`experiments/configs/environment.json`; the paper's version table is generated
from that file. This exists because a version number typed by hand into a
methods section is a claim that has not been verified, and this study's standing
rule is that a factor is not controlled until it has actually been controlled.

**Dependency pinning.** `benchmark/requirements.txt` pins every direct and
transitive dependency to an exact version. Each framework is installed into its
own virtual environment. This is not cosmetic: the three frameworks have
overlapping and mutually incompatible constraints on shared libraries, and
resolving them into one environment would silently downgrade one framework's
dependencies and change what is being measured.

**Custom wrappers and patches.** The only shared code injected into the
frameworks is (i) the model-client factory in `benchmark/common/llm.py`, which
guarantees an identical model configuration in all three adapters, (ii) the tool
functions in `benchmark/common/tools.py`, and (iii) the instrumentation hooks in
`benchmark/common/logging.py`. No framework source was patched. Any
framework-specific workaround required to make an adapter function is recorded
in the run log and reported in Section 4 as an implementation finding rather
than being silently absorbed.

---

## 3.6 LLM Configuration

**Model.** `claude-sonnet-5` (Anthropic first-party Claude API), 1M-token
context window. The same model identifier is used by all three frameworks and
by every agent role within a run.

**Parameters.**

| Parameter | Value | Note |
|---|---|---|
| `max_tokens` | 4096 | Per response, identical for every agent role |
| `thinking` | `disabled` | Extended reasoning off, for cost and latency comparability |
| `output_config.effort` | `medium` | Reasoning-depth control |
| `temperature` | *not configurable* | See below |
| `top_p` / `top_k` | *not configurable* | See below |
| `stop_sequences` | none | |
| SDK-level retries | 0 | Retries are handled by the harness so each is logged |
| Request timeout | 300 s | Per API call; the run-level timeout is 600 s |

**Sampling parameters are unavailable on this model, and this has methodological
consequences we state rather than hide.** Claude Sonnet 5 removed
`temperature`, `top_p`, and `top_k`; supplying any of them returns an HTTP 400
error. Three consequences follow:

1. `temperature = 0` is not available as a variance-reduction technique. Output
   variability is therefore intrinsic to the measurement and is reported, not
   suppressed (§3.1, §3.8.3).
2. A confounder is *removed*: it is impossible for one framework's default
   sampling settings to silently differ from another's, which is a common and
   rarely-checked flaw in framework comparisons. Frameworks that inject a
   default `temperature` must be configured not to, and our adapters assert this
   at construction time.
3. The controllable analogue of sampling temperature on this model is reasoning
   effort. We fix it at `medium` for every call in every framework, and treat it
   as a controlled constant.

**System prompt template.** A single shared prompt template governs all
frameworks. It is composed of three parts:

- **Common preamble** — identical bytes across all frameworks and tasks: the
  operating contract, the output-format requirement, and the instruction to
  emit output conforming to the task's JSON schema.
- **Task block** — identical bytes across frameworks for a given task: the
  objective, the input contract, and the evaluation-relevant constraints.
- **Role block** — identical *semantic content* across frameworks, expressed in
  each framework's native idiom (a LangGraph node's prompt, a CrewAI agent's
  `role`/`goal`/`backstory`, an AutoGen agent's `system_message`).

Only the third part can differ, and only in form. It cannot be eliminated: a
role-based framework and a graph-based framework do not accept the same object
as an agent definition, and forcing byte-identity would mean crippling at least
two of the three frameworks and measuring a strawman instead of the tool a
practitioner would actually use. We manage this residual with two controls: the
role blocks are diffed and reviewed for semantic equivalence, and every prompt
actually sent is logged verbatim, so the claim of equivalence is auditable
rather than asserted. This is the study's single largest internal-validity
threat and is treated as such in §3.9.

**Justification of model choice.** Sonnet 5 sits at a capability tier where all
five tasks are solvable but not trivially so — a model too weak would floor the
completion-rate metric and a model too strong would ceiling it, and in both
cases framework differences would be masked by the model. Its 1M-token context
also ensures that no framework is penalised for a more verbose orchestration
style by hitting a context limit, which would confound the comparison. Cost per
token is low enough to make 150 runs plus a judge ensemble affordable, which is
what makes n = 10 per cell possible at all.

**Judge model.** Rubric-scored dimensions use `claude-opus-5` — a *different and
more capable* model than the system under test — with `effort: high`. Three
independent judges score each output and the median is taken. Using a stronger
separate model prevents a system from grading its own output and reduces
same-model stylistic self-preference, which would otherwise bias rubric scores
uniformly and undetectably. Judge prompts, per-judge raw scores, and
inter-judge agreement are all published (Appendix A, Appendix C).

**Cost model.** Costs are computed from logged token counts and a fixed pricing
snapshot dated 2026-08-23: \$3.00 per million input tokens and \$15.00 per
million output tokens for `claude-sonnet-5`. Cached-read and cache-write tokens
are priced at 0.1× and 1.25× the input rate respectively and are accounted
separately, because prompt caching is a framework-visible optimisation and
folding it into a single input figure would hide a real efficiency difference.
We deliberately use standard list pricing rather than the promotional
introductory rate in effect during the measurement window, so that reported
cost figures remain valid after that window closes. Judge-model tokens are
tracked but excluded from the reported cost of a framework, since the judge is
part of the measurement apparatus and not part of the system under test.

---

## 3.7 Task Design

### 3.7.1 Task Design Principles

The suite is small and tightly specified by intention. A benchmark of five
well-controlled tasks with unambiguous success criteria supports stronger
claims than a larger suite whose scoring is contestable, and every additional
task multiplies out across three frameworks and ten replications.

Four principles govern the design:

**Real-world relevance.** Each task corresponds to an automation workload that
is actually delegated to multi-agent systems in practice — literature
synthesis, support triage, data preparation, constrained planning, and code
review. No task is a synthetic puzzle chosen because it is easy to score.

**Coordination diversity.** The tasks were chosen to *differ in the
coordination pattern they demand*, not merely in subject matter. This is the
central design decision of the suite: if all five tasks required the same
control flow, the benchmark would measure one framework capability five times
and could not distinguish frameworks whose strengths lie in different
coordination regimes.

| Task | Coordination pattern demanded |
|---|---|
| T1 | Parallel fan-out to independent workers, then merge |
| T2 | Sequential stages with a data-dependent conditional branch |
| T3 | Sequential pipeline with real tool execution and result handling |
| T4 | Iterative loop with constraint checking and revision until valid |
| T5 | Multi-role critique and revision with a verification gate |

**Measurability.** Every task has a machine-checkable output schema and an
explicit success predicate. Where a golden reference exists (T2, T3, T5) it is
versioned alongside the task. Where the output is legitimately open-ended (T1,
T4) the objective components are still checked by rule, and only the residual
quality judgement is delegated to a rubric — a task is never scored *purely* by
opinion.

**Bounded cost and hermetic execution.** No task depends on live external
services. Retrieval in T1 runs against a frozen local corpus; T4 plans over a
static option table. This removes network flakiness and third-party drift from
the measurement, and means the benchmark can be re-run identically years later.

### 3.7.2 Task Definitions

Each task is specified with the same template — Objective, Input, Expected
Output, Required Workflow, Evaluation Criteria — in `tasks/<task>/scope.md`,
which is the authoritative specification. Summaries follow; results in Section 5
refer to tasks by identifier.

**T1 — Research Synthesis Agent.** Given a research question and a frozen
corpus of 40 paper abstracts, retrieve the relevant subset and produce a
structured synthesis: per-theme findings, each attributed to specific source
identifiers, plus explicitly identified disagreements between sources. Exercises
parallel fan-out and merge. Scored on retrieval precision/recall against a
labelled relevance set, citation validity (every cited identifier must exist in
the corpus and support the claim), and a reasoning-quality rubric.

**T2 — Customer Support Triage.** Given a batch of 12 support tickets,
classify each by category, severity, and escalation requirement, and draft a
response for the non-escalated ones. Exercises sequential staging with a
data-dependent conditional branch. Scored by macro-F1 against gold labels,
escalation-decision accuracy, and schema validity — the most deterministically
scorable task in the suite.

**T3 — Data Cleaning Pipeline.** Given a raw CSV with a documented set of
injected defects (type inconsistencies, duplicates, missing values, out-of-range
values, inconsistent categorical encodings), diagnose the defects and emit a
cleaned dataset plus a change log. Exercises real tool execution and handling of
tool results. Scored by cell-level agreement with the golden cleaned dataset,
defect-detection recall, and absence of unrequested destructive edits — which
makes it the suite's sharpest probe of whether a framework's agents stay inside
their instructions.

**T4 — Travel Planning Assistant.** Given a multi-city trip request with hard
constraints (budget ceiling, date window, mandatory cities) and soft
preferences, produce a day-by-day itinerary from a static option table.
Exercises an iterative constraint-repair loop, since a first draft will
typically violate the budget. Scored by hard-constraint satisfaction (a binary
gate — an over-budget itinerary is a failure regardless of quality),
soft-preference coverage, and internal consistency of the schedule.

**T5 — Code Review and Refactoring Agent.** Given a Python module containing
seeded defects of known type (a correctness bug, a performance defect, and two
maintainability issues) with an accompanying test suite, produce a review
identifying the defects and a refactored module. Exercises multi-role critique
with a verification gate. Scored by seeded-defect detection recall,
false-positive count, and — decisively — whether the refactored module still
passes the original test suite when executed. This last check is objective and
unforgiving, and is the reason T5 is in the suite.

---

## 3.8 Evaluation Metrics

Every metric below is defined together with the procedure that produces it.
`docs/metric_definitions.md` is the normative version of this subsection; no
quantity appears in Section 5 that is not defined here first.

### 3.8.1 Performance Metrics

**Task Completion Rate.** The fraction of runs that satisfy the task's success
predicate. Binary per run. A run is a success only if it terminates without an
unhandled exception, within the step and time ceilings, emits output that
validates against the task's JSON schema, and satisfies the task's hard
correctness gate. All four conditions are necessary; a plausible-looking output
that fails schema validation is a failure, because a downstream system could
not consume it. Reported as a proportion with a Wilson score interval.

**Accuracy / F1.** Task-specific and computed by deterministic comparison
against the golden reference: macro-F1 over classification labels for T2,
cell-level agreement with the golden cleaned dataset for T3, seeded-defect
detection precision and recall for T5, and retrieval precision/recall against
the labelled relevance set for T1. T4 has no single golden itinerary and
reports constraint satisfaction instead. No LLM is involved in any of these
numbers.

**Reasoning Quality.** A rubric score in 1–5 on four dimensions — task
faithfulness, evidential grounding, internal consistency, and completeness —
assigned by the three-judge `claude-opus-5` ensemble described in §3.6. The
per-run score is the median across judges per dimension. The rubric text, the
judge prompt, and every individual verdict are published. We report inter-judge
agreement (Krippendorff's α on ordinal data) alongside the scores, because a
rubric score whose judges disagree is not evidence, and reporting the
agreement statistic lets a reader discount the metric appropriately. Judges see
the output and the task specification but never the framework identity, so the
scoring is blind to the condition.

### 3.8.2 Efficiency Metrics

**End-to-End Latency.** Wall-clock seconds from the moment the adapter receives
the `TaskInstance` to the moment it returns a final output, measured with a
monotonic clock. It includes all model calls, tool execution, and framework
overhead, and it includes network round-trip time (§3.4). Harness-level retries
are included in the latency of the run that contained them, since a user
experiences the total. Reported as median with interquartile range and a
bootstrap CI on the median; the distributions are right-skewed and a mean would
misrepresent them.

**Framework Overhead.** Latency minus the summed duration of all model API
calls in the run. This isolates the time the framework itself spends on
orchestration from time spent waiting on the provider, and it is the
network-insensitive component of the latency comparison.

**Throughput.** Successful task completions per minute at concurrency levels
1, 2, 4, and 8, measured on T2 and T3 only — the two cheapest and most
deterministically scored tasks — with 8 runs per level. Restricting the sweep to
two tasks is a cost decision and is reported as such rather than presented as
full coverage.

**Token Usage.** Input, output, cache-read, and cache-write tokens, taken from
the provider's `usage` field on every response and summed per run; also
attributed per agent role. Counts are never estimated locally, because the
billed quantity is the one the provider reports.

**API Cost.** Token counts multiplied by the fixed pricing snapshot of §3.6.
Reported per run and per 100 successful completions — the second figure is the
one that matters for framework selection, since a cheap framework that fails
often is not cheap.

### 3.8.3 Reliability Metrics

**Failure Rate.** The fraction of runs that terminate without producing a
schema-valid output satisfying the success predicate. Failures are classified
into a fixed taxonomy, recorded per run, and reported by category rather than
only in aggregate, since the categories imply different engineering remedies:

| Category | Meaning |
|---|---|
| `exception` | Unhandled exception in framework or adapter code |
| `timeout` | Exceeded the 600 s wall-clock ceiling |
| `step_limit` | Exceeded 25 agent steps without terminating |
| `schema_invalid` | Terminated but output failed schema validation |
| `constraint_violation` | Schema-valid output failing the task's hard gate |
| `tool_error` | Unrecovered tool-invocation failure |
| `transport_error` | Provider transport or rate-limit error after retries |

**Recovery Success Rate.** Of runs where at least one attempt failed and a
harness retry was issued, the fraction that ultimately succeeded. Retries are
capped at 2 with exponential backoff, and every attempt is logged as a separate
record with its own tokens and latency, so a retry is never invisible in the
cost or timing figures. `transport_error` retries are reported separately from
retries triggered by framework-side failures: the former measures the
provider's reliability, the latter measures the framework's, and conflating them
would credit a framework for network recovery it did not perform.

**Output Consistency.** Run-to-run variability within a cell, quantified three
ways because a single number would be misleading. For structured fields, exact
agreement rate across the 10 runs. For free-text outputs, mean pairwise cosine
similarity of sentence embeddings over the 45 run pairs. For scalar metrics, the
coefficient of variation. Directly relevant given that determinism is
unavailable (§3.1): consistency is measured as an outcome rather than assumed
as a precondition.

### 3.8.4 Resource Usage

**Memory Footprint.** Peak resident set size of the worker process during a run,
sampled at 100 ms intervals by a monitoring thread and reported as the maximum.
This measures the framework's own orchestration footprint — model weights are
remote — so absolute values are modest and the meaningful comparison is
relative.

**Concurrency Behaviour.** Degradation in median latency and completion rate as
concurrency rises from 1 to 8, on the sweep tasks. Reported as a scaling curve
with the concurrency level at which completion rate first degrades. We do not
claim this characterises production-scale behaviour; the sweep tops out at 8.

### 3.8.5 Engineering Metrics

These quantify developer-facing cost. They are the most construct-fragile
metrics in the study and are reported with that qualification attached rather
than as hard measurements.

**Lines of Code (LOC).** Non-blank, non-comment lines in each framework's
adapter, counted by `cloc` over a fixed file list, and reported split into
orchestration code and shared code. Only orchestration code is compared;
shared code is identical by construction and including it would dilute the
signal. Counted after implementation is complete and functionally equivalent
across frameworks, so a framework is not rewarded for an unfinished adapter.

**Development Time.** Wall-clock hours to reach a working adapter, recorded
contemporaneously per task per framework in `docs/experiment_log.md` — not
reconstructed afterwards. Split into initial implementation and debugging.

**Learning-order confound, and how it is handled.** Implementing three
frameworks in sequence means the third benefits from experience gained on the
first two, which biases development time and debugging effort against whichever
framework was implemented first. We cannot eliminate this with a single
developer. We mitigate and disclose it: the implementation order is recorded and
reported; a common design pass fixing the agent topology and prompts for all
five tasks is completed *before* any framework-specific code is written, so the
shared design cost is not charged to the first framework; and after all three
adapters work, each is revisited in a uniform hardening pass so that all end at
comparable maturity. Residual order effects are reported as a limitation, and
we deliberately state development-time results as indicative rather than as
measurements from which a general claim follows.

**Debugging Effort.** The count of distinct non-trivial defects — each requiring
more than a typographical fix — encountered per framework, logged at the time of
occurrence with a short description and a root-cause category
(framework API misuse, framework defect, prompt/format issue, integration
issue). A count of logged incidents is a more auditable quantity than a
subjective difficulty score, and the incident log is published so a reader can
re-categorise.

**Maintainability.** A rubric score in 1–5 on modularity, control-flow clarity,
state-management explicitness, testability, and extension cost, applied to each
adapter. Scored independently by the three-judge ensemble on
framework-anonymised code, and separately self-assessed by the implementer;
both scores are reported. Where they disagree, the disagreement is reported
rather than resolved, since the disagreement is itself the finding.

---

## 3.9 Threats to Validity

### Internal Validity

**Prompt non-equivalence across frameworks.** The largest threat. Role
definitions must be expressed in each framework's native idiom (§3.6), so
byte-identity is unattainable for that component and a subtle wording advantage
could masquerade as a framework effect. *Mitigation:* the common preamble and
task block are byte-identical; role blocks are diffed for semantic equivalence;
every prompt actually transmitted is logged verbatim and published, making the
equivalence claim auditable. *Residual risk:* real and not fully eliminable.
We do not claim it is eliminated.

**Adapter implementation quality.** A framework may appear worse because our
adapter for it is weaker, not because the framework is. *Mitigation:* shared
tools, prompts, and model client, so adapters differ only in orchestration; a
uniform hardening pass after all three work; adapter code published in full for
inspection.

**Learning-order effects on engineering metrics.** Addressed in §3.8.5.
Disclosed rather than corrected.

**Provider-side drift during the measurement window.** Model serving, load, or
latency may change mid-experiment. *Mitigation:* interleaved round-robin run
order, so drift is distributed evenly across frameworks; timestamps logged per
call so drift is detectable post hoc.

**Absence of temperature control.** Determinism is unavailable (§3.6).
*Mitigation:* 10 replications per cell, distributional reporting, variability
measured as an outcome. Because the effect is symmetric across frameworks it
inflates variance without biasing comparison.

**Judge bias in rubric metrics.** *Mitigation:* a different and stronger model
than the system under test; three judges with median aggregation; blinding to
framework identity; inter-judge agreement reported so the reader can discount
low-agreement dimensions.

### External Validity

**Three frameworks, one model, one task suite, one host.** Results describe
these conditions. Paradigm-representative framework sampling (§3.3) is intended
to make the findings speak to *classes* of orchestration design rather than
three specific libraries, but that is an argument, not a demonstration.

**Single model tier.** Framework differences may interact with model
capability — an emergent-orchestration framework plausibly benefits more from a
stronger model than an explicitly-orchestrated one does. This study cannot
detect such an interaction, and we do not extrapolate across model tiers.
A model sweep is identified as future work.

**Task scale.** Five tasks, hermetic, with inputs of bounded size. Behaviour on
long-horizon workloads, very large contexts, or live external tool ecosystems is
not measured.

**Framework versions are a moving target.** These libraries change quickly.
Results are pinned to the recorded versions and should be read as a snapshot;
the published harness exists so the snapshot can be refreshed.

### Construct Validity

**"Developer productivity" is only partially captured** by LOC, hours, defect
counts, and a maintainability rubric. These proxies omit onboarding cost,
ecosystem quality, debugging-tool maturity, and team-scale factors. We report
components separately and never aggregate them into a single productivity
score, because such a score would imply a precision the constructs do not have.

**"Reasoning quality" is operationalised as an LLM-judge rubric score,** which
measures what the judge rewards. Mitigations in §3.8.1; the residual gap
between the construct and the measure is real, which is why every task also
carries a deterministic correctness component and no task is scored by rubric
alone.

**Task completion is binary,** collapsing partial success. Deliberate: a
partially-correct output is not usable by a downstream automated consumer, so
the binary predicate matches the deployment reality the benchmark is about.
Graded accuracy metrics are reported alongside to recover the lost resolution.

**LOC as a complexity proxy** rewards terseness, and a declarative framework
will produce fewer lines than an explicit one almost by construction. Reported
alongside the maintainability rubric and never interpreted as a quality measure
on its own.

### Conclusion Validity

**Statistical power.** n = 10 per cell, 50 per framework per aggregate. This
supports detection of large effects and is adequate for interval estimation; it
is underpowered for small effects. We report confidence intervals throughout and
state explicitly where an observed difference is not statistically
distinguishable, rather than reporting a direction as though it were a finding.

**Distributional assumptions.** Latency and token distributions are
right-skewed, so we use non-parametric methods: Kruskal–Wallis for the omnibus
framework effect, Mann–Whitney U for pairwise comparisons, Fisher's exact test
for proportions. Medians and bootstrap percentile intervals (10,000 resamples)
replace means and normal-theory intervals.

**Multiple comparisons.** Three frameworks × five tasks × several metrics
generates many tests. All p-values are Holm-corrected within a metric family,
and both corrected and uncorrected values are reported.

**Effect sizes over significance.** Cliff's delta accompanies every pairwise
comparison. With 10 runs per cell a statistically significant but negligible
difference has no engineering meaning, and reporting significance alone would
invite exactly that misreading.

**Non-independence within a cell.** Runs in a cell share a task instance and a
time window, so they are not fully independent. Aggregation is performed within
task before pooling across tasks, and per-task results are reported in full
(Appendix C) so that pooled figures can be checked against their components.
