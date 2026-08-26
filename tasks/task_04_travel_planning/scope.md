# T4 – Travel Planning Assistant

**Coordination pattern exercised:** iterative constraint-repair loop.

## Objective

Given a multi-city trip request with hard constraints and soft preferences,
produce a feasible day-by-day itinerary drawn from a static option table,
revising the plan until every hard constraint is satisfied.

## Input

Fixture directory: `tasks/task_04_travel_planning/fixtures/`

```jsonc
{
  "request_id": "trip_v1",
  "hard_constraints": {
    "budget_usd": 3200,
    "start_date": "2026-10-05",
    "end_date": "2026-10-16",       // 11 nights
    "mandatory_cities": ["Lisbon", "Seville", "Barcelona"],
    "max_flights": 3,
    "min_nights_per_city": 2
  },
  "soft_preferences": [
    "prefer trains over flights where journey time is under 6 hours",
    "at least one museum or gallery per city",
    "avoid arriving in a new city after 21:00",
    "one rest day with no scheduled activity"
  ],
  "options_table": "fixtures/options_v1.json"
}
```

`options_v1.json` is a static table of transport legs (mode, duration, departure
and arrival times, price), accommodation options per city (price per night,
area), and activities per city (type, price, duration). No live services.

**The table is calibrated so that a naive greedy plan overruns the budget by
roughly 15–25%.** This is the design decision that makes the task work: a
single-pass planner will produce an infeasible itinerary, so the framework must
actually iterate. A task solvable in one pass would not test loop behaviour.

## Expected Output

Validated against `tasks/task_04_travel_planning/schema.json`.

```jsonc
{
  "request_id": "str",
  "itinerary": [
    { "date": "YYYY-MM-DD", "city": "str",
      "transport": { "mode": "str", "from": "str", "to": "str",
                     "depart": "HH:MM", "arrive": "HH:MM",
                     "price_usd": 0 } | null,
      "accommodation": { "name": "str", "price_usd": 0 } | null,
      "activities": [ { "name": "str", "type": "str", "price_usd": 0 } ] }
  ],                                // one entry per date in the window
  "cost_breakdown": { "transport": 0, "accommodation": 0,
                      "activities": 0, "total": 0 },
  "constraints_check": [
    { "constraint": "str", "satisfied": true, "note": "str|null" }
  ],
  "revisions": [
    { "iteration": 0, "violation": "str", "change_made": "str",
      "cost_before": 0, "cost_after": 0 }
  ],
  "preferences_addressed": ["str"]
}
```

The `revisions` array is required output, not bookkeeping: it makes the repair
loop externally visible and checkable against `steps.csv`.

## Required Agents

| Role | Responsibility |
|---|---|
| `planner` | Produce a candidate itinerary from the options table |
| `cost_checker` | Compute the total and check every hard constraint |
| `repair_agent` | Revise the plan to remove a specific violation |
| `finaliser` | Confirm all hard constraints satisfied; report preference coverage |

## Required Tools

- `get_options(city: str, kind: str) -> list[Option]`
- `get_transport(from_city: str, to_city: str, date: str) -> list[Leg]`
- `sum_cost(itinerary) -> CostBreakdown` — deterministic arithmetic, so
  arithmetic slips do not confound the planning measurement

## Workflow Pattern

Plan → check → **loop** (repair → re-check) until feasible or the iteration
ceiling is reached → finalise.

Iteration ceiling: 5 repair cycles, enforced identically in all three adapters.
This is the suite's probe of cyclic control flow — a framework with explicit
loop constructs, one that must simulate loops through task re-declaration, and
one where looping is emergent from conversation will differ here structurally,
and that structural difference is the finding.

## Success Criteria

Hard gate — all must hold:

1. Output validates against the schema.
2. `cost_breakdown.total <= 3200`. **An over-budget itinerary is a failure
   regardless of its quality** — a plan the traveller cannot afford is not a
   partially good plan.
3. One itinerary entry per date in the window, no gaps, no duplicates.
4. All three mandatory cities present, each with ≥ 2 nights.
5. At most 3 flights.
6. Every transport leg, accommodation, and activity exists in `options_v1.json`
   at the stated price (**no invented options or prices**).
7. Transport arrival times are consistent with the next day's city.

Graded: hard-constraint satisfaction count
(`accuracy_primary`, `accuracy_metric_name = constraint_satisfaction`), soft
preference coverage (of 4), repair-loop iteration count, internal schedule
consistency, reasoning-quality rubric.

## Failure Conditions

| Condition | Category |
|---|---|
| Over budget | `constraint_violation` |
| Missing date, missing mandatory city, > 3 flights | `constraint_violation` |
| Invented option or price not in the table | `constraint_violation` |
| Loop does not terminate within 5 repair cycles | `step_limit` |
| Not schema-valid | `schema_invalid` |
| Exceeds 25 steps or 600 s | `step_limit` / `timeout` |

## Metrics Collected

All standard per-run metrics, plus hard-constraint satisfaction, cost margin
against the ceiling, repair iterations used, soft-preference coverage,
price-fabrication count, and per-role token attribution across loop iterations
(which is where the cost of a repair cycle becomes visible per framework).

## Known Risks

- **Calibration is critical and must be verified before the real runs.** If the
  naive plan comes in under budget, no repair is needed and the task measures
  nothing; if it overruns by too much, no framework will recover and the
  completion rate floors at zero for all three. Pilot runs must confirm that at
  least one framework succeeds and at least one repair iteration occurs.
- Arithmetic errors would confound planning ability with a model weakness, which
  is why `sum_cost` is a deterministic tool rather than something the agent
  computes.
- No golden itinerary exists — many feasible plans are valid. Hence constraint
  satisfaction rather than reference comparison, with the rubric confined to the
  residual quality judgement.
