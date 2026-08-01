"""Public data models for the retry-safety experiment."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class _StringEnum(StrEnum):
    """An enum that serializes naturally while retaining a typed API."""


class ToolKind(_StringEnum):
    """The three tool semantics exercised by the simulator."""

    READ_ONLY = "read_only"
    IDEMPOTENT_MUTATION = "idempotent_mutation"
    NON_IDEMPOTENT_MUTATION = "non_idempotent_mutation"


class RetryPolicy(_StringEnum):
    """Controller policy used after an ambiguous tool result."""

    NO_RETRY = "no_retry"
    BLIND_RETRY = "blind_retry"
    STATUS_BEFORE_RETRY = "status_before_retry"
    IDEMPOTENCY_KEY_RETRY = "idempotency_key_retry"


# ``Policy`` is a short compatibility spelling useful to callers building a UI.
Policy = RetryPolicy


class FailurePhase(_StringEnum):
    """Where the simulator hides a failure from the controller."""

    NONE = "none"
    BEFORE_COMMIT = "before_commit"
    AFTER_COMMIT = "after_commit"


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """Fully explicit, reproducible experiment configuration.

    ``trials`` is the number of matched replicates per tool/policy condition.
    The returned experiment therefore contains ``trials * tools * policies``
    rows.  Failure phases are scheduled in order, so a small run still covers
    both before- and after-commit ambiguity rather than relying on luck.
    """

    seed: int = 42
    trials: int = 12
    failure_probability: float = 1.0
    failure_phases: tuple[FailurePhase, ...] = (
        FailurePhase.BEFORE_COMMIT,
        FailurePhase.AFTER_COMMIT,
    )
    include_no_failure: bool = True
    max_attempts: int = 3
    tool_kinds: tuple[ToolKind, ...] = tuple(ToolKind)
    policies: tuple[RetryPolicy, ...] = tuple(RetryPolicy)

    def __post_init__(self) -> None:
        if self.trials < 1:
            raise ValueError("trials must be at least 1")
        if not 0.0 <= self.failure_probability <= 1.0:
            raise ValueError("failure_probability must be between 0 and 1")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if not self.failure_phases:
            raise ValueError("failure_phases must not be empty")
        if not self.tool_kinds:
            raise ValueError("tool_kinds must not be empty")
        if not self.policies:
            raise ValueError("policies must not be empty")

        # Accept strings at the integration boundary without weakening the
        # typed fields exposed to Python callers.
        object.__setattr__(
            self,
            "failure_phases",
            tuple(FailurePhase(value) for value in self.failure_phases),
        )
        object.__setattr__(
            self,
            "tool_kinds",
            tuple(ToolKind(value) for value in self.tool_kinds),
        )
        object.__setattr__(
            self,
            "policies",
            tuple(RetryPolicy(value) for value in self.policies),
        )

    @property
    def trials_per_condition(self) -> int:
        """Alias that makes the matrix meaning explicit for callers."""

        return self.trials

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible configuration mapping."""

        return {
            "seed": self.seed,
            "trials": self.trials,
            "failure_probability": self.failure_probability,
            "failure_phases": [phase.value for phase in self.failure_phases],
            "include_no_failure": self.include_no_failure,
            "max_attempts": self.max_attempts,
            "tool_kinds": [kind.value for kind in self.tool_kinds],
            "policies": [policy.value for policy in self.policies],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ExperimentConfig:
        """Construct a configuration from its serialized representation."""

        return cls(
            seed=int(value["seed"]),
            trials=int(value["trials"]),
            failure_probability=float(value["failure_probability"]),
            failure_phases=tuple(value["failure_phases"]),
            include_no_failure=bool(value["include_no_failure"]),
            max_attempts=int(value["max_attempts"]),
            tool_kinds=tuple(value["tool_kinds"]),
            policies=tuple(value["policies"]),
        )


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """One observable event in a trial, retained for teaching and debugging."""

    event: str
    attempt: int
    state_after: int
    ambiguous: bool = False
    committed: bool = False
    idempotency_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TrialResult:
    """Ground-truth outcome and accounting for one tool/policy replicate."""

    trial_id: int
    seed: int
    tool_kind: ToolKind
    policy: RetryPolicy
    failure_phase: FailurePhase
    failure_injected: bool
    initial_state: int
    expected_final_state: int
    final_state: int
    side_effect_count: int
    duplicate_side_effects: int
    exact_final_state_correct: bool
    successful_completion: bool
    retries: int
    status_reads: int
    calls: int
    cost: float
    trace: tuple[TraceEvent, ...]

    @property
    def operation_attempts(self) -> int:
        """Number of mutation/read operation calls, excluding status reads."""

        return self.calls - self.status_reads

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible per-trial mapping."""

        return {
            "trial_id": self.trial_id,
            "seed": self.seed,
            "tool_kind": self.tool_kind.value,
            "policy": self.policy.value,
            "failure_phase": self.failure_phase.value,
            "failure_injected": self.failure_injected,
            "initial_state": self.initial_state,
            "expected_final_state": self.expected_final_state,
            "final_state": self.final_state,
            "side_effect_count": self.side_effect_count,
            "duplicate_side_effects": self.duplicate_side_effects,
            "exact_final_state_correct": self.exact_final_state_correct,
            "successful_completion": self.successful_completion,
            "retries": self.retries,
            "status_reads": self.status_reads,
            "calls": self.calls,
            "cost": self.cost,
            "trace": [event.to_dict() for event in self.trace],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> TrialResult:
        """Construct a trial result from serialized JSON-compatible data."""

        return cls(
            trial_id=int(value["trial_id"]),
            seed=int(value["seed"]),
            tool_kind=ToolKind(value["tool_kind"]),
            policy=RetryPolicy(value["policy"]),
            failure_phase=FailurePhase(value["failure_phase"]),
            failure_injected=bool(value["failure_injected"]),
            initial_state=int(value["initial_state"]),
            expected_final_state=int(value["expected_final_state"]),
            final_state=int(value["final_state"]),
            side_effect_count=int(value["side_effect_count"]),
            duplicate_side_effects=int(value["duplicate_side_effects"]),
            exact_final_state_correct=bool(value["exact_final_state_correct"]),
            successful_completion=bool(value["successful_completion"]),
            retries=int(value["retries"]),
            status_reads=int(value["status_reads"]),
            calls=int(value["calls"]),
            cost=float(value["cost"]),
            trace=tuple(TraceEvent(**event) for event in value.get("trace", [])),
        )


@dataclass(frozen=True, slots=True)
class AggregateResult:
    """Summary for one tool, policy, and failure-phase cell."""

    tool_kind: ToolKind
    policy: RetryPolicy
    failure_phase: FailurePhase
    trials: int
    successful_completions: int
    exact_final_states: int
    total_duplicate_side_effects: int
    total_retries: int
    total_status_reads: int
    total_calls: int
    total_cost: float

    @property
    def successful_completion_rate(self) -> float:
        return self.successful_completions / self.trials if self.trials else 0.0

    @property
    def exact_final_state_rate(self) -> float:
        return self.exact_final_states / self.trials if self.trials else 0.0

    @property
    def mean_duplicate_side_effects(self) -> float:
        return self.total_duplicate_side_effects / self.trials if self.trials else 0.0

    @property
    def mean_retries(self) -> float:
        return self.total_retries / self.trials if self.trials else 0.0

    @property
    def mean_status_reads(self) -> float:
        return self.total_status_reads / self.trials if self.trials else 0.0

    @property
    def mean_calls(self) -> float:
        return self.total_calls / self.trials if self.trials else 0.0

    @property
    def mean_cost(self) -> float:
        return self.total_cost / self.trials if self.trials else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible aggregate mapping."""

        return {
            "tool_kind": self.tool_kind.value,
            "policy": self.policy.value,
            "failure_phase": self.failure_phase.value,
            "trials": self.trials,
            "successful_completions": self.successful_completions,
            "exact_final_states": self.exact_final_states,
            "total_duplicate_side_effects": self.total_duplicate_side_effects,
            "total_retries": self.total_retries,
            "total_status_reads": self.total_status_reads,
            "total_calls": self.total_calls,
            "total_cost": self.total_cost,
            "successful_completion_rate": self.successful_completion_rate,
            "exact_final_state_rate": self.exact_final_state_rate,
            "mean_duplicate_side_effects": self.mean_duplicate_side_effects,
            "mean_retries": self.mean_retries,
            "mean_status_reads": self.mean_status_reads,
            "mean_calls": self.mean_calls,
            "mean_cost": self.mean_cost,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AggregateResult:
        """Construct an aggregate from serialized JSON-compatible data."""

        return cls(
            tool_kind=ToolKind(value["tool_kind"]),
            policy=RetryPolicy(value["policy"]),
            failure_phase=FailurePhase(value["failure_phase"]),
            trials=int(value["trials"]),
            successful_completions=int(value["successful_completions"]),
            exact_final_states=int(value["exact_final_states"]),
            total_duplicate_side_effects=int(value["total_duplicate_side_effects"]),
            total_retries=int(value["total_retries"]),
            total_status_reads=int(value["total_status_reads"]),
            total_calls=int(value["total_calls"]),
            total_cost=float(value["total_cost"]),
        )


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    """Complete serializable output from :func:`run_experiment`."""

    config: ExperimentConfig
    trials: tuple[TrialResult, ...]
    aggregates: tuple[AggregateResult, ...]

    @property
    def aggregate(self) -> tuple[AggregateResult, ...]:
        """Singular-name compatibility alias for the aggregate cells."""

        return self.aggregates

    def to_dict(self) -> dict[str, Any]:
        """Return the complete result as JSON-compatible data."""

        return {
            "config": self.config.to_dict(),
            "trials": [trial.to_dict() for trial in self.trials],
            "aggregates": [aggregate.to_dict() for aggregate in self.aggregates],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ExperimentResult:
        """Construct a complete result from serialized JSON-compatible data."""

        return cls(
            config=ExperimentConfig.from_dict(value["config"]),
            trials=tuple(TrialResult.from_dict(item) for item in value["trials"]),
            aggregates=tuple(
                AggregateResult.from_dict(item) for item in value["aggregates"]
            ),
        )
