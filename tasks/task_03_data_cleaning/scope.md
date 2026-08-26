# T3 – Data Cleaning Pipeline

**Coordination pattern exercised:** sequential pipeline with real tool execution and result handling.

## Objective

Given a raw CSV containing a documented set of injected defects, diagnose the
defects, apply corrective transformations through tools, and emit a cleaned
dataset together with an auditable change log.

## Input

Fixture directory: `tasks/task_03_data_cleaning/fixtures/`

```jsonc
{
  "dataset_id": "sales_raw_v1",
  "csv_path": "fixtures/sales_raw_v1.csv",
  "schema_doc": "fixtures/sales_schema.md",
  "row_count": 200
}
```

`sales_raw_v1` — 200 rows, 8 columns, with **exactly 6 defect classes injected
at known locations** (the injection manifest is the golden reference and is
never shown to the agent):

| # | Defect class | Instances |
|---|---|---|
| 1 | Mixed date formats in `order_date` | 24 rows |
| 2 | Exact duplicate rows | 8 rows |
| 3 | Missing values in `quantity` and `region` | 15 cells |
| 4 | Out-of-range values (`quantity` negative, `unit_price` zero) | 9 rows |
| 5 | Inconsistent categorical encoding in `region` (`"US"`/`"usa"`/`"U.S.A."`) | 31 rows |
| 6 | Numeric column stored as text with thousands separators (`revenue`) | 40 rows |

`sales_schema.md` documents the intended types, allowed ranges, and the
canonical `region` vocabulary — so the correct behaviour is fully determined by
the inputs and requires no guessing.

## Expected Output

Validated against `tasks/task_03_data_cleaning/schema.json`.

```jsonc
{
  "dataset_id": "str",
  "output_csv_path": "str",       // written via the tool layer
  "defects_found": [
    { "defect_class": "str", "column": "str",
      "affected_row_count": 0, "action_taken": "str" }
  ],
  "change_log": [
    { "row_index": 0, "column": "str",
      "before": "str", "after": "str", "reason": "str" }
  ],
  "final_row_count": 0,
  "unresolved_issues": ["str"]
}
```

## Required Agents

| Role | Responsibility |
|---|---|
| `profiler` | Load the CSV and profile it against the schema doc |
| `diagnostician` | Enumerate defects with affected columns and row counts |
| `transformer` | Apply transformations through the tool layer |
| `validator` | Re-profile the cleaned output; confirm defects resolved and nothing else changed |

## Required Tools

From `benchmark/common/tools.py`, identical across adapters:

- `read_csv(path) -> TableSummary` — shape, dtypes, null counts, value samples
- `profile_column(path, column) -> ColumnProfile`
- `apply_transform(path, op, params) -> TransformResult` — a **closed set** of
  operations: `parse_dates`, `drop_duplicates`, `fill_missing`, `clip_range`,
  `normalise_categorical`, `parse_numeric`, `drop_rows`
- `write_csv(df_handle, path) -> str`

The operation set is closed on purpose. An open-ended code-execution tool would
turn T3 into a measurement of the model's Python skill rather than of the
framework's tool orchestration.

## Workflow Pattern

Profile → diagnose → transform (one tool call per defect class) → validate.

Genuinely sequential with real data dependencies: the transformer cannot act
before the diagnostician has produced a defect list, and the validator's input
is the transformer's written artefact. This makes T3 the suite's probe of how
each framework threads tool results through state.

## Success Criteria

Hard gate — all must hold:

1. Output validates against the schema.
2. A cleaned CSV was actually written and is readable.
3. `final_row_count == 192` (200 minus the 8 duplicates) — no other rows dropped.
4. No column present in the input is absent from the output.
5. **No unrequested destructive edits**: every cell that differs from the input
   appears in `change_log` with a reason.

Condition 5 is the sharpest check in the suite. It measures whether a
framework's agents stay inside their instructions, which is exactly what
determines whether such a pipeline can be trusted in production.

Graded: cell-level agreement with the golden cleaned dataset
(`accuracy_primary`, `accuracy_metric_name = cell_agreement`), defect-class
detection recall (of 6), change-log completeness, unrequested-edit count.

## Failure Conditions

| Condition | Category |
|---|---|
| No output CSV written, or unreadable | `constraint_violation` |
| Row count ≠ 192, or a column dropped | `constraint_violation` |
| A cell changed without a change-log entry | `constraint_violation` |
| Tool call raises and is not recovered | `tool_error` |
| Not schema-valid | `schema_invalid` |
| Exceeds 25 steps or 600 s | `step_limit` / `timeout` |

## Metrics Collected

All standard per-run metrics, plus cell-level agreement, per-defect-class
detection recall, change-log completeness ratio, unrequested-edit count, tool
call count and tool error rate, and retry behaviour after tool errors (T3 is
the main source of `tool_error` data for the recovery metric).

## Known Risks

- **Filesystem side effects.** Each run writes to an isolated per-run temporary
  directory; fixtures are read-only and checksummed before and after every run.
  A checksum mismatch invalidates the run group, not just the run.
- Tool errors are expected here and are the point — this task supplies most of
  the recovery-success data. The retry taxonomy must distinguish an agent
  calling a tool wrongly (framework-side) from the tool itself failing.
- 200 rows × 8 columns exceeds what fits comfortably in a prompt, so agents must
  work through profiling tools rather than reading the whole table. This is
  intentional and mirrors real conditions, but a framework that tries to inline
  the full table will hit `max_tokens`; that outcome is a genuine finding and
  is recorded as `constraint_violation`, not excluded.
