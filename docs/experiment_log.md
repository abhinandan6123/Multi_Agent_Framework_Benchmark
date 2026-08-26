# Experiment Log

Update this file every day. It is especially useful for the methodology and threats-to-validity sections later.

---

## 2026-08-14

### Phase

Phase 0 – Setup

### Completed

- Created project folders
- Created paper workspace
- Created benchmark configuration
- Defined initial frameworks
- Defined initial five-task suite
- Defined metric categories

### Decisions Made

- Full paper will be written before IEEE compression.
- LangGraph, CrewAI, and AutoGen will be compared.
- The study will evaluate system and engineering metrics.

### Pending Decisions

- Exact LLM and version
- Framework versions
- Hardware details
- Number of runs
- Evaluation protocol
- Scalability configuration
- API cost assumptions

### Problems or Risks

- Framework APIs may change before final experiments.
- Cloud API latency may introduce network variability.
- Subjective engineering metrics require a clearly documented rubric.

---

## 2026-08-23

### Phase

Phase 1 – Methods & Reproducibility Core

### Completed

- Locked every controllable constant (see `docs/research_decisions.md`): model,
  parameters, run count, run order, seed, tool access, evaluation protocol,
  pricing snapshot, statistical plan.
- Verified hardware and Python version against the actual machine rather than
  recording assumed values.
- Wrote Section 3 in full (3.1–3.9): `paper/full_version/section_03_methodology.md`.
- Wrote the frozen log/CSV contract: `docs/log_schema.md`, including the closed
  failure taxonomy and the eight invariants the metric layer asserts.
- Filled `docs/metric_definitions.md` — every metric now has a measurement
  procedure, and a "deliberately not reported" section so absences are decisions.
- Wrote all five task specifications (T1–T5) to the common template, each with a
  hard gate, a failure-category mapping, and known risks.
- Implemented the shared harness: `types.py` (adapter contract), `llm.py`
  (single model-client factory), `logging.py` (unified logger + memory sampler),
  `harness.py` (interleaved schedule, retry policy, PENDING guard),
  `metrics.py` (offline CSV derivation + invariant assertions),
  `scripts/record_environment.py`.
- Verified: schedule builder produces 150 attempts across 15 cells, exactly 10
  per cell, interleaved; PENDING guard fires; all modules parse.

### Decisions Made

- **LLM: `claude-sonnet-5`.** Capability tier where all five tasks are solvable
  but not trivially so, so framework differences are not masked by a floor or
  ceiling effect. 1M context ensures no framework is penalised for a verbose
  orchestration style.
- **Temperature cannot be controlled** on this model (sampling params removed;
  HTTP 400). Determinism is therefore not claimed. Variability is measured as an
  outcome. This is documented as the study's central methodological constraint
  rather than glossed over.
- **Hybrid evaluation.** Deterministic rules and golden references decide every
  hard gate; the LLM-judge ensemble scores rubric dimensions only. No task is
  scored by rubric alone.
- **Judge is `claude-opus-5`, not the system under test** — a stronger, different
  model, 3 judges, median, blinded to framework identity, with inter-judge
  agreement reported.
- **10 runs per cell, interleaved round-robin.** Interleaving is the mitigation
  for provider-side drift during the measurement window.
- **Standard list pricing, not the promotional intro rate**, so cost figures stay
  valid after the intro window closes on 2026-08-31.
- **Retries are harness-level, not SDK-level** (`max_retries=0` on the client),
  so every retry is a separate logged record and cannot hide in the cost or
  reliability figures.
- **`tool_error` is deliberately non-retryable**: an agent misusing a tool is
  framework behaviour to measure, not noise to retry away.
- **Framework versions are not hand-written.** Recorded from the installed
  distributions; `config.yaml` says `PENDING_INSTALL` until then, and the metric
  layer refuses a run group containing that value.
- **Separate virtual environment per framework.** The three have incompatible
  shared-dependency constraints; one environment would silently downgrade a
  framework and change what is measured.
- **Tasks differ by coordination pattern, not just topic** (parallel fan-out /
  conditional branch / tool pipeline / repair loop / critique+verify gate). Five
  tasks that all needed the same control flow would measure one capability five
  times.

### Pending / Not Done

- **Adapters are not implemented.** LangGraph, CrewAI, and AutoGen are not
  installed and no framework-specific code exists yet. `harness.py --dry-run`
  works; a real run exits with a clear message.
- **No experiments have been run.** Blocked on two things: no `ANTHROPIC_API_KEY`
  is configured in this environment, and the three frameworks are not installed.
- **Fixtures are specified but not built.** T1 corpus (40 abstracts + relevance
  labels), T2 ticket batch (12, gold-labelled), T3 CSV (200 rows, 6 defect
  classes + injection manifest), T4 options table + calibration, T5 module
  (~180 lines, 4 seeded defects + tests + hidden tests).
- Prompt templates (Appendix A) not yet written.
- Section 4 waits on implementation, by design (PDF writing order).

### Problems or Risks

- **Prompt non-equivalence across frameworks** is the largest internal-validity
  threat and cannot be fully eliminated — role definitions must use each
  framework's native idiom. Mitigated by byte-identical preamble/task blocks,
  semantic diffing of role blocks, and verbatim logging of every transmitted
  prompt. Disclosed as residual in §3.9 rather than claimed solved.
- **Learning-order confound** on development-time metrics with a single
  developer. Mitigated by a shared design pass before any framework code, a
  uniform hardening pass after all three work, and recording implementation
  order in the data. Results stated as indicative.
- **Task calibration is unverified.** T4's budget overrun (15–25% on a naive
  plan) and T1's near-miss difficulty determine whether those tasks carry signal
  at all. Pilot runs (`--runs 1`) must confirm calibration before the 150-run
  group; if all frameworks floor or ceiling on a task, the fixture is wrong, not
  the finding.
- **T5 executes agent-generated code** in a subprocess. Contained to a per-run
  temp directory, 60 s timeout, no network — the only place in the benchmark
  where this happens.
- n = 10 per cell is adequate for large effects and interval estimation,
  underpowered for small ones. Committed to reporting CIs and effect sizes and
  to saying explicitly where a difference is not distinguishable.
