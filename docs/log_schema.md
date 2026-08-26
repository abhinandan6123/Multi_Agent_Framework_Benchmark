# Log and Results Schema

This is a **frozen contract**. The adapters write it, the metric layer reads it,
and the analysis layer reads only the derived CSVs. Adding a field is allowed;
renaming or repurposing one is not, because published raw logs must remain
readable by the published analysis code.

Everything is written under `experiments/raw_logs/<run_group>/`, where
`run_group` is `YYYYMMDD_HHMMSS` of the batch start.

---

## Files per run group

| File | Content |
|---|---|
| `manifest.json` | The run schedule: seed, cell list, interleaved order, config snapshot |
| `environment.json` | Resolved dependency versions, interpreter, platform (copy of `experiments/configs/environment.json`) |
| `runs.jsonl` | One record per attempt (see below) |
| `steps.jsonl` | One record per agent step |
| `llm_calls.jsonl` | One record per model API call |
| `tools.jsonl` | One record per tool invocation |
| `judge.jsonl` | One record per judge verdict |
| `outputs/<run_id>.json` | The final output payload of each attempt, verbatim |
| `prompts/<run_id>/` | Every prompt transmitted, verbatim, in call order |

Raw logs are append-only. The metric layer never mutates them.

---

## 1. `runs.jsonl` — one record per attempt

An *attempt* is one execution. A *run* is the sequence of attempts for one
replication; `attempt_index` distinguishes them. Retries are separate records,
never overwrites.

```jsonc
{
  "run_id":            "str",   // "lg_T2_r03_a0" — framework_task_repl_attempt
  "run_group":         "str",
  "framework":         "langgraph|crewai|autogen",
  "framework_version": "str",
  "task_id":           "T1|T2|T3|T4|T5",
  "fixture_id":        "str",   // which input instance was used
  "replication":       0,       // 0..9
  "attempt_index":     0,       // 0 = first try; >0 = harness retry
  "is_final_attempt":  true,    // exactly one true per replication

  "schedule_position": 0,       // position in the interleaved order

  "started_at":        "ISO-8601 UTC",
  "ended_at":          "ISO-8601 UTC",
  "latency_seconds":   0.0,     // monotonic clock, adapter entry -> return
  "llm_seconds":       0.0,     // summed duration of all llm_calls
  "tool_seconds":      0.0,
  "overhead_seconds":  0.0,     // latency - llm_seconds - tool_seconds

  "step_count":        0,
  "llm_call_count":    0,
  "tool_call_count":   0,

  "input_tokens":       0,      // from provider usage, summed
  "output_tokens":      0,
  "cache_read_tokens":  0,
  "cache_write_tokens": 0,

  "peak_rss_mb":       0.0,     // 100ms sampling, max

  "status":            "success|failure",
  "failure_category":  null,    // taxonomy below; null iff status==success
  "failure_detail":    null,    // exception type + message, truncated 2000 ch
  "traceback":         null,

  "schema_valid":      true,
  "hard_gate_passed":  true,    // task-specific success predicate
  "terminated_cleanly": true,   // no timeout, no step-limit hit

  "output_path":       "outputs/lg_T2_r03_a0.json",
  "config_hash":       "str",   // sha256 of the resolved config used
  "notes":             null
}
```

`status == "success"` **iff** `terminated_cleanly && schema_valid &&
hard_gate_passed`. The metric layer asserts this rather than trusting it.

### `failure_category` taxonomy (closed set)

`exception` · `timeout` · `step_limit` · `schema_invalid` ·
`constraint_violation` · `tool_error` · `transport_error`

Only these seven values are valid. A new failure mode requires a schema
revision, not an ad-hoc string — otherwise the reliability table silently
develops a long tail of one-off categories.

---

## 2. `steps.jsonl` — one record per agent step

```jsonc
{
  "run_id":       "str",
  "step_index":   0,
  "agent_role":   "str",       // canonical role name, shared across frameworks
  "native_node":  "str",       // framework-native identifier (node/agent/task)
  "started_at":   "ISO-8601 UTC",
  "duration_seconds": 0.0,
  "llm_call_ids": ["str"],
  "tool_call_ids": ["str"],
  "error":        null
}
```

`agent_role` is drawn from a fixed per-task vocabulary shared by all three
adapters, so that per-role token attribution is comparable across frameworks.
`native_node` preserves what the framework actually called it.

---

## 3. `llm_calls.jsonl` — one record per model API call

```jsonc
{
  "call_id":      "str",
  "run_id":       "str",
  "step_index":   0,
  "agent_role":   "str",
  "model":        "claude-sonnet-5",
  "started_at":   "ISO-8601 UTC",
  "duration_seconds": 0.0,
  "request_params": { },       // effort, max_tokens, thinking, tools declared
  "prompt_path":  "prompts/lg_T2_r03_a0/call_004.json",
  "usage": {
    "input_tokens": 0, "output_tokens": 0,
    "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0
  },
  "stop_reason":  "end_turn|tool_use|max_tokens|refusal|...",
  "stop_details": null,
  "response_text": "str",      // verbatim
  "error":        null
}
```

Token counts come from the provider `usage` field only. No local tokenizer is
used anywhere in this project — the billed count is the one that matters, and a
local estimate would be a different number reported under the same name.

---

## 4. `tools.jsonl`

```jsonc
{
  "tool_call_id": "str",
  "run_id":       "str",
  "step_index":   0,
  "tool_name":    "str",
  "arguments":    { },
  "started_at":   "ISO-8601 UTC",
  "duration_seconds": 0.0,
  "ok":           true,
  "result":       { },         // truncated to 8000 chars, with a flag if cut
  "result_truncated": false,
  "error":        null
}
```

---

## 5. `judge.jsonl`

```jsonc
{
  "judgement_id": "str",
  "run_id":       "str",
  "rubric":       "reasoning_quality|maintainability",
  "judge_model":  "claude-opus-5",
  "judge_index":  0,           // 0..2
  "blinded":      true,        // framework identity withheld from the judge
  "prompt_path":  "prompts/judge/....json",
  "scores":       { "faithfulness": 4, "grounding": 3,
                    "consistency": 5, "completeness": 4 },
  "rationale":    "str",
  "usage":        { "input_tokens": 0, "output_tokens": 0 }
}
```

Judge tokens are logged but excluded from framework cost figures: the judge is
measurement apparatus, not part of the system under test.

---

## Derived CSVs

Written by `benchmark/common/metrics.py` into `results/csv/`. One row per unit
of analysis, tidy format, no merged cells, no summary rows.

### `runs.csv` — one row per **replication** (final attempt), 150 rows

```
run_id, framework, framework_version, task_id, fixture_id, replication,
attempts_used, schedule_position,
latency_seconds, llm_seconds, tool_seconds, overhead_seconds,
step_count, llm_call_count, tool_call_count,
input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
total_tokens, cost_usd,
peak_rss_mb,
success, failure_category,
schema_valid, hard_gate_passed, terminated_cleanly,
accuracy_primary, accuracy_metric_name,
reasoning_quality_median, reasoning_quality_alpha,
recovered_after_failure, transport_retry_count, framework_retry_count
```

`accuracy_primary` is the task's headline deterministic score with
`accuracy_metric_name` naming it (`macro_f1`, `cell_agreement`,
`defect_recall`, `retrieval_f1`, `constraint_satisfaction`) — so a single
column can be aggregated without losing the fact that it means different things
per task.

`cost_usd` is derived, not logged: recomputing it from tokens and the pricing
snapshot means a pricing correction never requires re-running an experiment.

### `attempts.csv` — one row per attempt, including retries

Same key columns plus `attempt_index`, `is_final_attempt`. Feeds the recovery
and reliability analysis, where the retried attempts are the data.

### `steps.csv` — one row per step

`run_id, framework, task_id, step_index, agent_role, native_node,
duration_seconds, input_tokens, output_tokens, cost_usd, error`

Per-role token attribution.

### `concurrency.csv`

`framework, task_id, concurrency_level, run_index, latency_seconds, success,
wall_clock_batch_seconds, throughput_tasks_per_min`

### `engineering.csv` — one row per (framework, task) plus a framework total

```
framework, task_id, loc_orchestration, loc_shared, loc_total,
dev_hours_implementation, dev_hours_debugging,
defect_count, defect_categories,
maintainability_judge_median, maintainability_self, implementation_order
```

`implementation_order` is carried into the data so the learning-order confound
(Section 3.8.5) is analysable rather than merely disclosed in prose.

### `consistency.csv` — one row per (framework, task) cell

`framework, task_id, n_runs, structured_exact_agreement,
text_mean_pairwise_cosine, latency_cv, tokens_cv, accuracy_cv`

---

## Invariants the metric layer asserts

These are checked and raise on violation, rather than being assumed:

1. Exactly 150 rows in `runs.csv`; exactly 10 per (framework, task) cell.
2. Exactly one `is_final_attempt` per replication.
3. `success` is consistent with the three component flags.
4. `failure_category` is null iff `success`, and otherwise in the closed set.
5. Token totals in `runs.csv` equal the sum over that run's `llm_calls.jsonl`.
6. `latency_seconds >= llm_seconds + tool_seconds` (overhead is non-negative).
7. `config_hash` is identical across all runs in a group.
8. No run's `framework_version` is `PENDING_INSTALL`.

Any exclusion from an analysis must be applied by a named, logged rule, and the
count of exclusions is reported in Section 5. Silent dropping is prohibited.
