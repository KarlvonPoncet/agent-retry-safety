"""Deterministic tool state machine used by the experiment runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import FailurePhase, ToolKind, TraceEvent


@dataclass(frozen=True, slots=True)
class ToolResponse:
    """The result visible to a controller for one operation call."""

    succeeded: bool
    ambiguous_error: bool
    committed: bool
    state_value: int | None
    event: TraceEvent


@dataclass(frozen=True, slots=True)
class StatusResponse:
    """A safe status read that is never made ambiguous in this experiment."""

    state_value: int
    satisfies_target: bool
    event: TraceEvent


class ToolSession(Protocol):
    """Interface a deterministic or future LLM controller can use."""

    expected_final_state: int
    tool_kind: ToolKind

    def invoke(self, idempotency_key: str | None = None) -> ToolResponse:
        """Attempt the requested operation."""

    def read_status(self) -> StatusResponse:
        """Read enough authoritative state to decide whether it is complete."""


class DeterministicToolSession:
    """A tiny server-like state machine with a single commit boundary.

    The first operation call can fail before commit (no effect) or after commit
    (effect is real, but the controller sees only an ambiguous error).  Later
    operation calls succeed.  Status reads are reliable and do not mutate
    state.  This is intentionally small: the simulator, rather than a model,
    is the ground truth.
    """

    def __init__(
        self,
        *,
        tool_kind: ToolKind,
        failure_phase: FailurePhase,
        initial_state: int = 0,
    ) -> None:
        self.tool_kind = tool_kind
        self.failure_phase = failure_phase
        self.initial_state = initial_state
        self.state_value = initial_state
        self.expected_final_state = (
            initial_state
            if tool_kind is ToolKind.READ_ONLY
            else initial_state + 1
        )
        self._operation_calls = 0
        self._status_reads = 0
        self._logical_side_effects = 0
        self._consumed_idempotency_keys: set[str] = set()
        self._trace: list[TraceEvent] = []

    @property
    def operation_calls(self) -> int:
        return self._operation_calls

    @property
    def status_reads(self) -> int:
        return self._status_reads

    @property
    def calls(self) -> int:
        return self._operation_calls + self._status_reads

    @property
    def logical_side_effects(self) -> int:
        """Visible effects; idempotent replays count as one effect."""

        return self._logical_side_effects

    @property
    def trace(self) -> tuple[TraceEvent, ...]:
        return tuple(self._trace)

    def invoke(self, idempotency_key: str | None = None) -> ToolResponse:
        self._operation_calls += 1
        attempt = self._operation_calls

        if (
            attempt == 1
            and self.failure_phase is FailurePhase.BEFORE_COMMIT
        ):
            event = TraceEvent(
                event="ambiguous_error_before_commit",
                attempt=attempt,
                state_after=self.state_value,
                ambiguous=True,
                committed=False,
                idempotency_key=idempotency_key,
            )
            self._trace.append(event)
            return ToolResponse(
                succeeded=False,
                ambiguous_error=True,
                committed=False,
                state_value=None,
                event=event,
            )

        already_applied = (
            idempotency_key is not None
            and idempotency_key in self._consumed_idempotency_keys
        )
        if not already_applied:
            self._commit()
            if idempotency_key is not None:
                self._consumed_idempotency_keys.add(idempotency_key)

        if attempt == 1 and self.failure_phase is FailurePhase.AFTER_COMMIT:
            event = TraceEvent(
                event="ambiguous_error_after_commit",
                attempt=attempt,
                state_after=self.state_value,
                ambiguous=True,
                committed=True,
                idempotency_key=idempotency_key,
            )
            self._trace.append(event)
            return ToolResponse(
                succeeded=False,
                ambiguous_error=True,
                committed=True,
                state_value=None,
                event=event,
            )

        event = TraceEvent(
            event="success_deduplicated" if already_applied else "success",
            attempt=attempt,
            state_after=self.state_value,
            ambiguous=False,
            committed=not already_applied,
            idempotency_key=idempotency_key,
        )
        self._trace.append(event)
        return ToolResponse(
            succeeded=True,
            ambiguous_error=False,
            committed=not already_applied,
            state_value=self.state_value,
            event=event,
        )

    def read_status(self) -> StatusResponse:
        self._status_reads += 1
        event = TraceEvent(
            event="status_read",
            attempt=self._operation_calls,
            state_after=self.state_value,
            ambiguous=False,
            committed=False,
        )
        self._trace.append(event)
        return StatusResponse(
            state_value=self.state_value,
            satisfies_target=self.state_value == self.expected_final_state,
            event=event,
        )

    def _commit(self) -> None:
        if self.tool_kind is ToolKind.READ_ONLY:
            # A read has a commit/response boundary, but no side effect.
            return
        if self.tool_kind is ToolKind.IDEMPOTENT_MUTATION:
            self.state_value = self.expected_final_state
            self._logical_side_effects = 1
            return
        if self.tool_kind is ToolKind.NON_IDEMPOTENT_MUTATION:
            self.state_value += 1
            self._logical_side_effects += 1
            return
        raise AssertionError(f"unsupported tool kind: {self.tool_kind}")
