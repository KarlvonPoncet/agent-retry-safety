from retry_safety import FailurePhase, ToolKind
from retry_safety.simulator import DeterministicToolSession


def test_failure_before_commit_has_no_effect_and_later_call_succeeds() -> None:
    session = DeterministicToolSession(
        tool_kind=ToolKind.NON_IDEMPOTENT_MUTATION,
        failure_phase=FailurePhase.BEFORE_COMMIT,
    )

    first = session.invoke()
    second = session.invoke()

    assert first.ambiguous_error is True
    assert first.committed is False
    assert session.state_value == 1
    assert second.succeeded is True
    assert session.logical_side_effects == 1


def test_failure_after_commit_preserves_the_effect_despite_error() -> None:
    session = DeterministicToolSession(
        tool_kind=ToolKind.NON_IDEMPOTENT_MUTATION,
        failure_phase=FailurePhase.AFTER_COMMIT,
    )

    first = session.invoke()

    assert first.ambiguous_error is True
    assert first.committed is True
    assert session.state_value == 1
    assert session.logical_side_effects == 1


def test_idempotency_key_deduplicates_a_replayed_non_idempotent_call() -> None:
    session = DeterministicToolSession(
        tool_kind=ToolKind.NON_IDEMPOTENT_MUTATION,
        failure_phase=FailurePhase.AFTER_COMMIT,
    )

    session.invoke("same-key")
    replay = session.invoke("same-key")

    assert replay.succeeded is True
    assert replay.event.event == "success_deduplicated"
    assert session.state_value == 1
    assert session.logical_side_effects == 1


def test_read_only_tool_has_no_side_effect() -> None:
    session = DeterministicToolSession(
        tool_kind=ToolKind.READ_ONLY,
        failure_phase=FailurePhase.AFTER_COMMIT,
    )

    response = session.invoke()

    assert response.ambiguous_error is True
    assert session.state_value == 0
    assert session.logical_side_effects == 0
