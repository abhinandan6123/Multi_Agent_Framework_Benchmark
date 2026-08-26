# T1 – Research Synthesis Agent

**Coordination pattern exercised:** parallel fan-out to independent workers, then merge.

## Objective

Given a research question and a frozen local corpus of paper abstracts, identify
the relevant subset and produce a structured synthesis organised by theme, with
every claim attributed to specific source identifiers and with disagreements
between sources stated explicitly.

## Input

Fixture directory: `tasks/task_01_research/fixtures/`

```jsonc
{
  "question": "str",              // e.g. "What are the reported failure modes
                                  //       of retrieval-augmented generation?"
  "corpus_id": "corpus_v1",
  "max_sources": 12
}
```

`corpus_v1` is a frozen set of **40 abstracts**, each `{id, title, year, venue,
abstract}`. Of these, a labelled relevance set marks which are relevant to the
question; 6 abstracts are deliberate near-misses (topically adjacent, not
relevant) and 2 pairs contain directly contradictory findings.

The corpus is local. Retrieval is performed through the shared
`search_corpus(query, k)` tool — no network access, so the task is hermetic and
re-runnable indefinitely.

## Expected Output

Validated against `tasks/task_01_research/schema.json`.

```jsonc
{
  "question": "str",
  "themes": [
    { "name": "str",
      "finding": "str",
      "source_ids": ["str"],      // >= 1, must exist in the corpus
      "confidence": "high|medium|low" }
  ],                              // 3..6 themes
  "disagreements": [
    { "description": "str", "source_ids": ["str"] }   // >= 2 ids each
  ],
  "sources_used": ["str"],
  "summary": "str"                // <= 200 words
}
```

## Required Agents

Canonical roles (shared vocabulary across all three adapters):

| Role | Responsibility |
|---|---|
| `planner` | Decompose the question into 3–4 independent sub-queries |
| `retriever` | Execute `search_corpus` per sub-query (parallel fan-out) |
| `analyst` | Extract findings from retrieved abstracts, per sub-query |
| `synthesiser` | Merge analyst outputs into themes; detect contradictions |

## Required Tools

- `search_corpus(query: str, k: int) -> list[Abstract]` — BM25 over `corpus_v1`
- `get_abstract(source_id: str) -> Abstract`

Both from `benchmark/common/tools.py`, identical across adapters.

## Workflow Pattern

Plan → **parallel** retrieve+analyse per sub-query → merge → synthesise.

The parallel stage is the point of the task: it distinguishes frameworks that
express concurrent fan-out natively from those that serialise it. Adapters must
use each framework's native concurrency mechanism where one exists, and the
absence of one is a finding to report in Section 4, not something to paper over
with a manual thread pool.

## Success Criteria

Hard gate — all must hold:

1. Output validates against the schema.
2. Every `source_id` mentioned anywhere exists in `corpus_v1` (**no fabricated
   citations** — a single invented identifier fails the run).
3. At least 3 themes present.
4. At least one disagreement correctly identified, with both sides cited from
   the labelled contradictory pairs.

Graded metrics: retrieval F1 against the labelled relevance set
(`accuracy_primary`, `accuracy_metric_name = retrieval_f1`), citation support
rate, near-miss inclusion count, reasoning-quality rubric.

## Failure Conditions

| Condition | Category |
|---|---|
| Fabricated `source_id` | `constraint_violation` |
| Fewer than 3 themes, or no disagreement found | `constraint_violation` |
| Output not schema-valid | `schema_invalid` |
| `search_corpus` raises and is not recovered | `tool_error` |
| Exceeds 25 steps or 600 s | `step_limit` / `timeout` |

## Metrics Collected

All standard per-run metrics (`docs/log_schema.md`) plus retrieval F1, citation
support rate, near-miss inclusion count, theme count, per-role token
attribution (which is where the parallel stage shows up in the data).

## Known Risks

- **Ceiling risk.** If retrieval is too easy all frameworks score identically
  and the task carries no signal. The 6 near-misses exist to prevent this;
  if the pilot run shows F1 above 0.95 for all three frameworks, the corpus
  needs harder distractors before the real runs.
- **Open-ended output.** Theme naming is legitimately variable, which is why
  the deterministic score is retrieval and citation validity, and only the
  residual quality judgement is delegated to the rubric.
- Frameworks that serialise the fan-out will show higher latency for reasons
  that are genuinely about the framework — this is signal, not noise, but it
  must be reported as an orchestration difference rather than an inefficiency
  of our adapter.
