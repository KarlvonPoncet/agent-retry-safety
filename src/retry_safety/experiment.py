"""Experiment orchestration and reproducible failure scheduling."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from typing import Any

from .models import (
    AggregateResult,
    ExperimentConfig,
    ExperimentResult,
    FailurePhase,
    RetryPolicy,
    ToolKind,
    TrialResult,
)
from .policies import controller_for
from .simulator import DeterministicToolSession


def run_experiment(config: ExperimentConfig) -> ExperimentResult:
    """Run a matched experiment and return serializable ground-truth results.

    Each replicate gets one seed and one scheduled failure phase.  Every
    policy/tool condition for that replicate receives the same phase and seed,
    making policy comparisons paired rather than accidentally comparing
    different random draws.  The simulator itself is deterministic; the seed
    controls the explicit schedule and is recorded in every row.
    """

    rng = random.Random(config.seed)
    trial_rows: list[TrialResult] = []
    trial_id = 0

    for replicate in range(config.trials):
        trial_seed = rng.getrandbits(63)
        scheduled_phase = _scheduled_failure_phase(config, replicate)
        if scheduled_phase is FailurePhase.NONE:
            failure_phase = FailurePhase.NONE
        elif rng.random() <= config.failure_probability:
            failure_phase = scheduled_phase
        else:
            failure_phase = FailurePhase.NONE

        for tool_kind in config.tool_kinds:
            for policy in config.policies:
                session = DeterministicToolSession(
                    tool_kind=tool_kind,
                    failure_phase=failure_phase,
                )
                controller = controller_for(
                    policy,
                    max_attempts=config.max_attempts,
                )
                outcome = controller.execute(
                    session,
                    operation_key=f"experiment-{trial_seed}",
                )
                exact = session.state_value == session.expected_final_state
                trial_rows.append(
                    TrialResult(
                        trial_id=trial_id,
                        seed=trial_seed,
                        tool_kind=tool_kind,
                        policy=policy,
                        failure_phase=failure_phase,
                        failure_injected=failure_phase is not FailurePhase.NONE,
                        initial_state=session.initial_state,
                        expected_final_state=session.expected_final_state,
                        final_state=session.state_value,
                        side_effect_count=session.logical_side_effects,
                        duplicate_side_effects=(
                            max(0, session.logical_side_effects - 1)
                            if tool_kind is ToolKind.NON_IDEMPOTENT_MUTATION
                            else 0
                        ),
                        exact_final_state_correct=exact,
                        successful_completion=outcome.successful_completion,
                        retries=outcome.retries,
                        status_reads=outcome.status_reads,
                        calls=outcome.calls,
                        cost=(outcome.calls - outcome.status_reads)
                        + (2 * outcome.status_reads),
                        trace=outcome.trace,
                    )
                )
                trial_id += 1

    return ExperimentResult(
        config=config,
        trials=tuple(trial_rows),
        aggregates=_aggregate(trial_rows),
    )


def _scheduled_failure_phase(
    config: ExperimentConfig,
    replicate: int,
) -> FailurePhase:
    phases = list(config.failure_phases)
    if config.include_no_failure:
        phases.append(FailurePhase.NONE)
    return phases[replicate % len(phases)]


def _aggregate(rows: list[TrialResult]) -> tuple[AggregateResult, ...]:
    grouped: dict[
        tuple[ToolKind, RetryPolicy, FailurePhase], list[TrialResult]
    ] = defaultdict(list)
    for row in rows:
        grouped[(row.tool_kind, row.policy, row.failure_phase)].append(row)

    aggregates: list[AggregateResult] = []
    for (tool_kind, policy, failure_phase), group in grouped.items():
        aggregates.append(
            AggregateResult(
                tool_kind=tool_kind,
                policy=policy,
                failure_phase=failure_phase,
                trials=len(group),
                successful_completions=sum(
                    row.successful_completion for row in group
                ),
                exact_final_states=sum(
                    row.exact_final_state_correct for row in group
                ),
                total_duplicate_side_effects=sum(
                    row.duplicate_side_effects for row in group
                ),
                total_retries=sum(row.retries for row in group),
                total_status_reads=sum(row.status_reads for row in group),
                total_calls=sum(row.calls for row in group),
                total_cost=sum(row.cost for row in group),
            )
        )
    return tuple(aggregates)


def result_to_json(result: ExperimentResult, *, indent: int = 2) -> str:
    """Encode an experiment result as deterministic, human-readable JSON."""

    return json.dumps(result.to_dict(), indent=indent, sort_keys=True) + "\n"


def result_from_json(text: str) -> ExperimentResult:
    """Decode JSON produced by :func:`result_to_json`."""

    value: Any = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("experiment JSON must contain an object")
    return ExperimentResult.from_dict(value)
