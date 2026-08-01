"""Deterministic retry controllers and their future-controller interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import RetryPolicy, TraceEvent
from .simulator import ToolSession


@dataclass(frozen=True, slots=True)
class ControllerOutcome:
    """Accounting emitted by a controller after it decides the operation is done."""

    successful_completion: bool
    retries: int
    status_reads: int
    calls: int
    trace: tuple[TraceEvent, ...]


class Controller(Protocol):
    """Protocol for replacing these policies with a future LLM controller."""

    policy: RetryPolicy

    def execute(self, session: ToolSession, *, operation_key: str) -> ControllerOutcome:
        """Drive one tool operation through a controller/tool interface."""


def controller_for(policy: RetryPolicy, *, max_attempts: int) -> Controller:
    """Build a deterministic controller for ``policy``."""

    return _DeterministicController(policy=policy, max_attempts=max_attempts)


@dataclass(frozen=True, slots=True)
class _DeterministicController:
    policy: RetryPolicy
    max_attempts: int

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

    def execute(self, session: ToolSession, *, operation_key: str) -> ControllerOutcome:
        if self.policy is RetryPolicy.NO_RETRY:
            return self._single_attempt(session)

        if self.policy is RetryPolicy.BLIND_RETRY:
            return self._retry_until_success(
                session,
                operation_key=None,
                check_status=False,
            )

        if self.policy is RetryPolicy.IDEMPOTENCY_KEY_RETRY:
            return self._retry_until_success(
                session,
                operation_key=operation_key,
                check_status=False,
            )

        if self.policy is RetryPolicy.STATUS_BEFORE_RETRY:
            return self._status_before_retry(session)

        raise AssertionError(f"unsupported retry policy: {self.policy}")

    def _single_attempt(self, session: ToolSession) -> ControllerOutcome:
        response = session.invoke()
        return ControllerOutcome(
            successful_completion=response.succeeded,
            retries=0,
            status_reads=0,
            calls=1,
            trace=(response.event,),
        )

    def _retry_until_success(
        self,
        session: ToolSession,
        *,
        operation_key: str | None,
        check_status: bool,
    ) -> ControllerOutcome:
        del check_status  # Kept as a named extension point for future controllers.
        trace: list[TraceEvent] = []
        attempts = 0
        while attempts < self.max_attempts:
            attempts += 1
            response = session.invoke(operation_key)
            trace.append(response.event)
            if response.succeeded:
                return ControllerOutcome(
                    successful_completion=True,
                    retries=attempts - 1,
                    status_reads=0,
                    calls=attempts,
                    trace=tuple(trace),
                )
        return ControllerOutcome(
            successful_completion=False,
            retries=max(0, attempts - 1),
            status_reads=0,
            calls=attempts,
            trace=tuple(trace),
        )

    def _status_before_retry(self, session: ToolSession) -> ControllerOutcome:
        trace: list[TraceEvent] = []
        attempts = 0
        status_reads = 0

        response = session.invoke()
        attempts += 1
        trace.append(response.event)
        if response.succeeded:
            return ControllerOutcome(True, 0, 0, attempts, tuple(trace))

        # The status endpoint is the controller's way to turn an ambiguous
        # outcome into a known outcome. It avoids a second mutation when the
        # first call committed, but permits a retry when it did not.
        status = session.read_status()
        status_reads += 1
        trace.append(status.event)
        if status.satisfies_target:
            return ControllerOutcome(
                True,
                0,
                status_reads,
                attempts + status_reads,
                tuple(trace),
            )

        while attempts < self.max_attempts:
            attempts += 1
            response = session.invoke()
            trace.append(response.event)
            if response.succeeded:
                return ControllerOutcome(
                    True,
                    attempts - 1,
                    status_reads,
                    attempts + status_reads,
                    tuple(trace),
                )
            status = session.read_status()
            status_reads += 1
            trace.append(status.event)
            if status.satisfies_target:
                return ControllerOutcome(
                    True,
                    attempts - 1,
                    status_reads,
                    attempts + status_reads,
                    tuple(trace),
                )

        return ControllerOutcome(
            False,
            max(0, attempts - 1),
            status_reads,
            attempts + status_reads,
            tuple(trace),
        )
