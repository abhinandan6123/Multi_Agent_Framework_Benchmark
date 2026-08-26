"""Shared data contracts.

These types are the interface between the four pipeline stages described in
Section 3.2. They are deliberately framework-agnostic: nothing here may import
langgraph, crewai, or autogen. If a field is needed by only one adapter, it does
not belong in this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class FailureCategory(str, Enum):
    """Closed taxonomy. See docs/log_schema.md.

    A new failure mode requires a schema revision, not a new string literal --
    otherwise the reliability table grows a long tail of one-off categories and
    stops being comparable across frameworks.
    """

    EXCEPTION = "exception"
    TIMEOUT = "timeout"
    STEP_LIMIT = "step_limit"
    SCHEMA_INVALID = "schema_invalid"
    CONSTRAINT_VIOLATION = "constraint_violation"
    TOOL_ERROR = "tool_error"
    TRANSPORT_ERROR = "transport_error"


@dataclass(frozen=True)
class TaskInstance:
    """One task, one input fixture. Identical object for all three adapters."""

    task_id: str                    # "T1".."T5"
    fixture_id: str
    payload: dict[str, Any]         # the task input, verbatim from the fixture
    output_schema: dict[str, Any]   # JSON Schema the output must validate against
    agent_roles: tuple[str, ...]    # canonical role vocabulary for this task
    prompts: "TaskPrompts"
    rubric_id: str | None
    max_steps: int
    timeout_seconds: int
    workdir: str                    # per-run isolated temp directory


@dataclass(frozen=True)
class TaskPrompts:
    """The three-part prompt template of Section 3.6.

    `preamble` and `task_block` are byte-identical across frameworks and are
    asserted so by `benchmark/common/prompts.py`. `role_blocks` carry identical
    semantic content expressed in each framework's idiom, which is the one place
    equivalence cannot be enforced mechanically -- hence every prompt actually
    transmitted is logged verbatim so the claim stays auditable.
    """

    preamble: str
    task_block: str
    role_blocks: dict[str, str]     # canonical role name -> role instruction


@dataclass
class StepRecord:
    step_index: int
    agent_role: str
    native_node: str
    started_at: str
    duration_seconds: float
    llm_call_ids: list[str] = field(default_factory=list)
    tool_call_ids: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class RunResult:
    """What an adapter returns. Timing, tokens, and cost are NOT set here --
    the harness and logger own those, so an adapter cannot influence its own
    measured numbers."""

    output: dict[str, Any] | None
    steps: list[StepRecord]
    terminated_cleanly: bool
    failure_category: FailureCategory | None = None
    failure_detail: str | None = None
    traceback: str | None = None
    native_trace: dict[str, Any] | None = None   # framework-specific extras


class FrameworkAdapter(Protocol):
    """The single interface every framework must implement.

    An adapter is responsible for orchestration only: building the framework's
    native agent topology, running it, and reporting a per-step trace. Prompts,
    tools, the output schema, and the model client are injected, so they cannot
    drift between adapters (Section 3.1, controlled factors).
    """

    name: str          # "langgraph" | "crewai" | "autogen"
    version: str       # resolved at construction from the installed distribution

    def build(self, task: TaskInstance) -> None:
        """Construct the native topology. Called once per run, before timing
        starts, so topology construction is not charged to latency."""

    def run(self, task: TaskInstance) -> RunResult:
        """Execute. Must raise nothing: convert every error into a RunResult
        with a failure_category, so a crash in one adapter cannot abort a run
        group."""
