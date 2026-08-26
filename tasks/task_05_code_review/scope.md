# T5 – Code Review and Refactoring Agent

**Coordination pattern exercised:** multi-role critique and revision with a verification gate.

## Objective

Given a Python module containing seeded defects of known type, together with its
test suite, produce a structured review identifying the defects and a refactored
module that preserves behaviour.

## Input

Fixture directory: `tasks/task_05_code_review/fixtures/`

```jsonc
{
  "module_id": "inventory_v1",
  "module_path": "fixtures/inventory_v1.py",   // ~180 lines
  "test_path":   "fixtures/test_inventory_v1.py",
  "language": "python"
}
```

`inventory_v1.py` contains **exactly 4 seeded defects** of known type and
location (the seed manifest is the golden reference and is never shown to the
agent):

| # | Class | Description |
|---|---|---|
| D1 | Correctness | Off-by-one in a date-range filter, excluding the final day |
| D2 | Correctness | Mutable default argument shared across calls |
| D3 | Performance | O(n²) membership scan inside a loop where a set would be O(n) |
| D4 | Maintainability | A 45-line function with four responsibilities and duplicated validation |

The accompanying test suite passes on the original module **and covers the
behaviour that D1 and D2 corrupt only indirectly** — so the tests do not simply
hand the agent the answer, but they do constrain any refactor. There are also
**3 pieces of idiomatic-but-unusual code that are correct** and should not be
reported; these are the false-positive traps.

## Expected Output

Validated against `tasks/task_05_code_review/schema.json`.

```jsonc
{
  "module_id": "str",
  "findings": [
    { "finding_id": "str",
      "category": "correctness|performance|maintainability|style",
      "severity": "high|medium|low",
      "line_start": 0, "line_end": 0,
      "description": "str",
      "failure_scenario": "str|null",     // required for correctness findings
      "recommendation": "str" }
  ],
  "refactored_module_path": "str",
  "refactor_summary": "str",
  "behaviour_preserved_claim": true,
  "tests_run": { "passed": 0, "failed": 0, "errors": 0 }
}
```

## Required Agents

| Role | Responsibility |
|---|---|
| `reader` | Build a structural understanding of the module |
| `reviewer` | Produce candidate findings with line references |
| `critic` | Challenge each finding; reject unsupported ones (false-positive control) |
| `refactorer` | Apply surviving findings, producing the new module |
| `verifier` | Run the original test suite against the refactored module |

The `critic` role exists because an unfiltered reviewer will over-report, and an
over-reporting review is not a useful review. Whether a framework's topology can
express a genuine adversarial critique step — rather than a second reviewer that
agrees — is part of what T5 measures.

## Required Tools

- `read_file(path) -> str`
- `write_file(path, content) -> str`
- `run_tests(module_path, test_path) -> TestResult` — subprocess `pytest`,
  isolated per-run temp directory, 60 s timeout

## Workflow Pattern

Read → review → critique → refactor → **verify (gate)**.

If `run_tests` fails on the refactored module, the refactorer gets one repair
attempt, then verification runs again. The gate is objective and unforgiving:
`tests_run.failed > 0` on the final verification is a failed run no matter how
good the review text was. This is the reason T5 is in the suite — it is the one
task where correctness is decided by executing code rather than by comparing
text.

## Success Criteria

Hard gate — all must hold:

1. Output validates against the schema.
2. A refactored module was written and is syntactically valid Python.
3. **The original, unmodified test suite passes against the refactored module**
   (`failed == 0 and errors == 0`).
4. The public API of the module is unchanged (all originally exported names still
   present with compatible signatures).
5. At least one seeded defect is correctly identified with a line reference
   within ±3 lines of the seeded location.

Graded: seeded-defect detection recall out of 4
(`accuracy_primary`, `accuracy_metric_name = defect_recall`), false-positive
count against the 3 traps, line-reference precision, whether the correctness
defects D1/D2 were actually fixed in the refactored code (checked by
supplementary hidden tests run *after* scoring, never given to the agent), and
a maintainability rubric on the refactored module.

## Failure Conditions

| Condition | Category |
|---|---|
| Refactored module not written, or not valid Python | `constraint_violation` |
| Original test suite fails on the refactored module | `constraint_violation` |
| Public API broken | `constraint_violation` |
| No seeded defect identified | `constraint_violation` |
| `run_tests` times out or errors unrecovered | `tool_error` |
| Not schema-valid | `schema_invalid` |
| Exceeds 25 steps or 600 s | `step_limit` / `timeout` |

## Metrics Collected

All standard per-run metrics, plus seeded-defect recall, false-positive count,
line-reference precision, hidden-test pass rate (the real measure of whether the
correctness defects were fixed rather than merely described), refactor churn
(lines added/removed), verification-gate retry count, and the maintainability
rubric.

## Known Risks

- **Subprocess execution.** `run_tests` executes agent-produced code. It runs in
  a per-run temporary directory with a 60 s timeout and no network. This is the
  only place in the benchmark where generated code is executed, and it is
  contained deliberately.
- The hidden supplementary tests must never leak into the agent's context; they
  are applied by the scoring layer after the run completes, from a path the
  tools cannot read.
- **Ceiling/floor risk.** Four defects with one execution gate could floor the
  completion rate if the module is too intricate. The module is deliberately
  small (~180 lines) so that a competent refactor is achievable; pilot runs must
  confirm at least one framework clears the gate.
- Frameworks differ in how naturally they express a genuine critic role. Where
  an adapter cannot make the critique adversarial, that limitation is reported as
  a Section 4 finding rather than compensated for in the prompt.
