import pytest

from retry_safety import (
    ExperimentConfig,
    FailurePhase,
    RetryPolicy,
    ToolKind,
    run_experiment,
)


@pytest.mark.parametrize(
    ("policy", "successful", "exact", "duplicates", "status_reads", "retries"),
    [
        (RetryPolicy.NO_RETRY, False, True, 0, 0, 0),
        (RetryPolicy.BLIND_RETRY, True, False, 1, 0, 1),
        (RetryPolicy.STATUS_BEFORE_RETRY, True, True, 0, 1, 0),
        (RetryPolicy.IDEMPOTENCY_KEY_RETRY, True, True, 0, 0, 1),
    ],
)
def test_policies_have_distinct_after_commit_outcomes(
    policy: RetryPolicy,
    successful: bool,
    exact: bool,
    duplicates: int,
    status_reads: int,
    retries: int,
) -> None:
    result = run_experiment(
        ExperimentConfig(
            seed=9,
            trials=1,
            failure_phases=(FailurePhase.AFTER_COMMIT,),
            include_no_failure=False,
            tool_kinds=(ToolKind.NON_IDEMPOTENT_MUTATION,),
            policies=(policy,),
        )
    )
    row = result.trials[0]

    assert row.successful_completion is successful
    assert row.exact_final_state_correct is exact
    assert row.duplicate_side_effects == duplicates
    assert row.status_reads == status_reads
    assert row.retries == retries


def test_all_policies_recover_a_before_commit_failure_without_duplicates() -> None:
    result = run_experiment(
        ExperimentConfig(
            seed=10,
            trials=1,
            failure_phases=(FailurePhase.BEFORE_COMMIT,),
            include_no_failure=False,
            tool_kinds=(ToolKind.NON_IDEMPOTENT_MUTATION,),
        )
    )

    for row in result.trials:
        assert row.duplicate_side_effects == 0
        if row.policy is RetryPolicy.NO_RETRY:
            assert row.successful_completion is False
        else:
            assert row.successful_completion is True
        assert row.exact_final_state_correct == (
            row.policy is not RetryPolicy.NO_RETRY
        )


def test_cost_counts_operation_calls_and_charges_status_reads_twice() -> None:
    result = run_experiment(
        ExperimentConfig(
            trials=1,
            failure_phases=(FailurePhase.AFTER_COMMIT,),
            include_no_failure=False,
            tool_kinds=(ToolKind.NON_IDEMPOTENT_MUTATION,),
            policies=(RetryPolicy.STATUS_BEFORE_RETRY,),
        )
    )

    row = result.trials[0]
    assert row.calls == 2  # one operation + one status read
    assert row.cost == 3  # one + two status-read cost units
