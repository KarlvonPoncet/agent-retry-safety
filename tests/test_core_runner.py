import json

from retry_safety import (
    ExperimentConfig,
    ExperimentResult,
    FailurePhase,
    RetryPolicy,
    ToolKind,
    result_from_json,
    result_to_json,
    run_experiment,
)


def test_replay_is_deterministic_for_same_config() -> None:
    config = ExperimentConfig(seed=1234, trials=4)

    first = run_experiment(config)
    second = run_experiment(config)

    assert first == second
    assert len(first.trials) == 4 * len(config.tool_kinds) * len(config.policies)
    assert {row.failure_phase for row in first.trials} == {
        FailurePhase.BEFORE_COMMIT,
        FailurePhase.AFTER_COMMIT,
        FailurePhase.NONE,
    }


def test_different_seed_is_recorded_and_changes_trial_seeds() -> None:
    common = dict(
        trials=2,
        tool_kinds=(ToolKind.READ_ONLY,),
        policies=(RetryPolicy.NO_RETRY,),
    )

    first = run_experiment(ExperimentConfig(seed=1, **common))
    second = run_experiment(ExperimentConfig(seed=2, **common))

    assert [row.seed for row in first.trials] != [row.seed for row in second.trials]


def test_result_round_trips_through_json() -> None:
    result = run_experiment(ExperimentConfig(seed=77, trials=2))

    encoded = result_to_json(result)
    decoded = result_from_json(encoded)

    assert json.loads(encoded) == result.to_dict()
    assert decoded == result
    assert ExperimentResult.from_dict(result.to_dict()) == result


def test_aggregate_cells_expose_rates_and_metrics() -> None:
    result = run_experiment(
        ExperimentConfig(
            trials=1,
            failure_phases=(FailurePhase.AFTER_COMMIT,),
            include_no_failure=False,
            tool_kinds=(ToolKind.NON_IDEMPOTENT_MUTATION,),
            policies=(RetryPolicy.BLIND_RETRY,),
        )
    )

    aggregate = result.aggregates[0]
    assert aggregate.trials == 1
    assert aggregate.successful_completion_rate == 1.0
    assert aggregate.exact_final_state_rate == 0.0
    assert aggregate.mean_duplicate_side_effects == 1.0
    assert aggregate.mean_cost == 2.0
