"""The single model-client factory.

Every model call in every adapter goes through here. This is what makes the
claim "identical LLM configuration across frameworks" (Section 3.6) true by
construction rather than by inspection.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

import anthropic

# ---------------------------------------------------------------------------
# Claude Sonnet 5 removed the sampling parameters. Sending any of these returns
# HTTP 400. Frameworks that inject a default temperature must be stopped from
# doing so; `assert_no_sampling_params` is called by every adapter at build time
# so the failure surfaces as a clear assertion instead of an opaque 400 in the
# middle of a run.
# ---------------------------------------------------------------------------
FORBIDDEN_PARAMS = ("temperature", "top_p", "top_k")


def assert_no_sampling_params(params: dict[str, Any], where: str) -> None:
    offending = [p for p in FORBIDDEN_PARAMS if p in params and params[p] is not None]
    if offending:
        raise ValueError(
            f"{where}: claude-sonnet-5 rejects {offending} (HTTP 400). "
            "Remove the framework's default sampling parameters; see Section 3.6."
        )


@dataclass(frozen=True)
class LLMConfig:
    model: str
    max_tokens: int
    effort: str
    thinking: str            # "disabled" | "adaptive"
    timeout_seconds: int

    @classmethod
    def from_config(cls, cfg: dict[str, Any], key: str = "llm") -> "LLMConfig":
        node = cfg[key]
        return cls(
            model=node["model"],
            max_tokens=node["max_tokens"],
            effort=node["effort"],
            thinking=node["thinking"],
            timeout_seconds=node["request_timeout_seconds"],
        )


class InstrumentedClient:
    """Wraps the Anthropic client so that every call is logged before the
    adapter ever sees the response.

    SDK-level retries are disabled (`max_retries=0`) on purpose: retries are
    handled by the harness so that each attempt appears as its own record with
    its own tokens and latency. An SDK retry would be invisible in the cost and
    reliability figures, which is exactly the kind of hidden work this study is
    trying to measure.
    """

    def __init__(
        self,
        config: LLMConfig,
        emit_llm_call: Callable[[dict[str, Any]], None],
        run_id: str,
    ) -> None:
        self._cfg = config
        self._emit = emit_llm_call
        self._run_id = run_id
        self._client = anthropic.Anthropic(
            max_retries=0,
            timeout=config.timeout_seconds,
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        self.total_llm_seconds = 0.0

    def _request_params(self, **overrides: Any) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self._cfg.model,
            "max_tokens": self._cfg.max_tokens,
            "output_config": {"effort": self._cfg.effort},
        }
        if self._cfg.thinking == "disabled":
            params["thinking"] = {"type": "disabled"}
        else:
            params["thinking"] = {"type": "adaptive"}
        params.update(overrides)
        assert_no_sampling_params(params, "InstrumentedClient._request_params")
        return params

    def create(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str | list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        step_index: int = -1,
        agent_role: str = "unknown",
        **overrides: Any,
    ) -> Any:
        params = self._request_params(**overrides)
        if system is not None:
            params["system"] = system
        if tools:
            params["tools"] = tools
        params["messages"] = messages

        call_id = f"{self._run_id}_call_{uuid.uuid4().hex[:8]}"
        started = time.monotonic()
        error: str | None = None
        response = None
        try:
            response = self._client.messages.create(**params)
            return response
        except Exception as exc:                      # noqa: BLE001 - recorded, re-raised
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            duration = time.monotonic() - started
            self.total_llm_seconds += duration
            usage = getattr(response, "usage", None)
            self._emit(
                {
                    "call_id": call_id,
                    "run_id": self._run_id,
                    "step_index": step_index,
                    "agent_role": agent_role,
                    "model": self._cfg.model,
                    "duration_seconds": duration,
                    # Logged verbatim: the prompt-equivalence claim of Section
                    # 3.6 is only auditable if what was actually sent is on disk.
                    "request_params": {
                        k: v for k, v in params.items() if k != "messages"
                    },
                    "messages": messages,
                    "usage": _usage_dict(usage),
                    "stop_reason": getattr(response, "stop_reason", None),
                    "stop_details": _stop_details(response),
                    "response_text": _text_of(response),
                    "error": error,
                }
            )


def _usage_dict(usage: Any) -> dict[str, int]:
    """Token counts come from the provider only. No local tokenizer is used
    anywhere in this project -- the billed count is the reported count."""
    if usage is None:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }
    return {
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(
            usage, "cache_creation_input_tokens", 0
        ) or 0,
    }


def _stop_details(response: Any) -> dict[str, Any] | None:
    details = getattr(response, "stop_details", None)
    if details is None:
        return None
    return {
        "type": getattr(details, "type", None),
        "category": getattr(details, "category", None),
        "explanation": getattr(details, "explanation", None),
    }


def _text_of(response: Any) -> str:
    if response is None:
        return ""
    parts = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts)
