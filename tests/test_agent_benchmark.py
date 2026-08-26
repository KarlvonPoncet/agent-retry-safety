import json
import sys

import pytest

from retry_safety import (
    AgentBenchmarkConfig,
    AgentControllerKind,
    ErrorWording,
    FailurePhase,
    ProtocolVariant,
    TaskFamily,
    ToolKind,
    agent_result_from_json,
    agent_result_to_json,
    benchmark_manifest,
    run_agent_benchmark,
    uncertainty_protocol,
)
from retry_safety.agent_benchmark import SubprocessModelAdapter, _parse_action
from retry_safety.simulator import DeterministicToolSession


def _config(**overrides):
    values = {
        "seed": 11,
        "trials": 3,
        "failure_phases": (FailurePhase.AFTER_COMMIT,),
        "include_no_failure": False,
        "error_wordings": (ErrorWording.TIMEOUT,),
    }
    values.update(overrides)
    return AgentBenchmarkConfig(**values)


def test_agent_replay_is_deterministic_for_same_manifest() -> None:
    config = _config(controllers=(AgentControllerKind.SAME_KEY_RETRY,))
    assert run_agent_benchmark(config) == run_agent_benchmark(config)


def test_task_families_and_held_out_tools_are_in_matrix() -> None:
    result = run_agent_benchmark(_config())
    assert {row.task_family for row in result.trials} == set(TaskFamily)
    assert any(row.held_out_tool for row in result.trials)
    assert {row.semantics for row in result.trials} == set(ToolKind)
    cells = {
        (row.task_family, row.semantics, row.held_out_tool)
        for row in result.trials
    }
    assert all(
        (family, semantics, held_out) in cells
        for family, semantics in {
            (row.task_family, row.semantics) for row in result.trials
        }
        for held_out in (False, True)
    )


def test_opaque_oracle_trace_keeps_commit_truth_out_of_visible_observation() -> None:
    result = run_agent_benchmark(
        _config(controllers=(AgentControllerKind.NO_RETRY,))
    )
    row = next(row for row in result.trials if row.task_id == "payment_charge")
    assert row.true_commit_state == "committed"
    assert row.observed_result == "ambiguous_error"
    assert all("committed" not in event.observation for event in row.trace)
    assert row.oracle_trace[0].committed is True


def test_protocol_and_ablation_have_replayable_distinct_outcomes() -> None:
    result = run_agent_benchmark(
        _config(controllers=(AgentControllerKind.UNCERTAINTY_PROTOCOL,))
    )
    cells = {
        row.protocol_variant: row
        for row in result.trials
        if row.task_id == "payment_charge"
    }
    assert cells[ProtocolVariant.MACHINE_READABLE].duplicate_side_effects == 0
    assert cells[ProtocolVariant.NATURAL_LANGUAGE].duplicate_side_effects == 0
    assert cells[ProtocolVariant.PROMPT_ONLY].duplicate_side_effects == 1
    assert cells[ProtocolVariant.MACHINE_READABLE].status_reads == 1


def test_benchmark_json_round_trip_and_manifest_are_machine_readable() -> None:
    config = _config(controllers=(AgentControllerKind.SAME_KEY_RETRY,))
    result = run_agent_benchmark(config)
    encoded = agent_result_to_json(result)
    assert agent_result_from_json(encoded) == result
    assert json.loads(encoded)["schema_version"] == "retry-safety-agent-v1"
    manifest = benchmark_manifest(config)
    assert manifest["schema_version"].endswith("manifest-v1")
    assert manifest["protocol"]["on_ambiguous_result"] == "unknown"
    assert len(manifest["schedule"]) == config.trials
    assert uncertainty_protocol()["reconcile"]["authoritative"] is True


def test_scripted_llm_adapter_uses_visible_actions_without_private_reasoning() -> None:
    def fake_model(prompt: str) -> str:
        return '{"action":"reconcile","use_same_key":true}'

    result = run_agent_benchmark(
        _config(
            controllers=(AgentControllerKind.LLM,),
            protocol_variants=(ProtocolVariant.MACHINE_READABLE,),
        ),
        model=fake_model,
    )
    row = next(row for row in result.trials if row.task_id == "payment_charge")
    assert row.model_calls >= 1
    assert row.trace[0].action == "invoke"
    assert row.trace[0].model_output == ""
    assert "Prior visible observations: tool:" in row.trace[1].input_text
    assert all("reasoning" not in event.model_output.lower() for event in row.trace)


def test_llm_runs_protocol_ablation_and_counts_only_repeat_invocations() -> None:
    def fake_model(prompt: str) -> str:
        return '{"action":"retry","use_same_key":false}'

    result = run_agent_benchmark(
        _config(
            trials=1,
            controllers=(AgentControllerKind.LLM,),
            protocol_variants=(
                ProtocolVariant.MACHINE_READABLE,
                ProtocolVariant.PROMPT_ONLY,
            ),
        ),
        model=fake_model,
    )
    rows = [row for row in result.trials if row.task_id == "payment_charge"]
    assert {row.protocol_variant for row in rows} == {
        ProtocolVariant.MACHINE_READABLE,
        ProtocolVariant.PROMPT_ONLY,
    }
    assert all(row.retries == 1 for row in rows)


@pytest.mark.parametrize("action", ["retry", "invoke"])
@pytest.mark.parametrize(
    "variant",
    [
        ProtocolVariant.MACHINE_READABLE,
        ProtocolVariant.NATURAL_LANGUAGE,
        ProtocolVariant.PROMPT_ONLY,
    ],
)
def test_llm_same_key_intent_reuses_the_trial_key_for_all_protocol_aliases(
    action: str, variant: ProtocolVariant
) -> None:
    def fake_model(prompt: str) -> str:
        return json.dumps({"action": action, "use_same_key": True})

    result = run_agent_benchmark(
        _config(
            trials=1,
            controllers=(AgentControllerKind.LLM,),
            failure_phases=(FailurePhase.AFTER_COMMIT,),
            protocol_variants=(variant,),
            max_attempts=2,
        ),
        model=fake_model,
    )

    for row in result.trials:
        initial_key = row.trace[0].idempotency_key
        assert initial_key == f"agent-{row.seed}-{row.task_id}"
        assert row.trace[1].action == action
        assert row.trace[1].idempotency_key == initial_key
        operation_events = [
            event for event in row.oracle_trace if event.event != "status_read"
        ]
        assert all(event.idempotency_key == initial_key for event in operation_events)
    non_idempotent = [
        row
        for row in result.trials
        if row.semantics is ToolKind.NON_IDEMPOTENT_MUTATION
    ]
    assert all(row.duplicate_side_effects == 0 for row in non_idempotent)


@pytest.mark.parametrize("action", ["retry", "invoke"])
def test_llm_false_same_key_intent_does_not_reuse_key(action: str) -> None:
    def fake_model(prompt: str) -> str:
        return json.dumps({"action": action, "use_same_key": False})

    result = run_agent_benchmark(
        _config(
            trials=1,
            controllers=(AgentControllerKind.LLM,),
            failure_phases=(FailurePhase.AFTER_COMMIT,),
            protocol_variants=(ProtocolVariant.MACHINE_READABLE,),
            max_attempts=2,
        ),
        model=fake_model,
    )

    for row in result.trials:
        assert row.trace[1].idempotency_key is None
    non_idempotent = [
        row
        for row in result.trials
        if row.semantics is ToolKind.NON_IDEMPOTENT_MUTATION
    ]
    assert all(row.unsafe_retry for row in non_idempotent)


def test_after_commit_wrong_key_replay_is_detected_as_unsafe() -> None:
    session = DeterministicToolSession(
        tool_kind=ToolKind.NON_IDEMPOTENT_MUTATION,
        failure_phase=FailurePhase.AFTER_COMMIT,
    )
    original_key = "agent-regression-payment_charge"
    first = session.invoke(original_key)
    replay = session.invoke("different-logical-operation-key")

    assert first.event.idempotency_key == original_key
    assert replay.event.idempotency_key != original_key
    assert session.logical_side_effects == 2
    assert session.state_value != session.expected_final_state


def test_llm_action_parser_preserves_boolean_intent_and_enforces_schema() -> None:
    assert _parse_action('{"action":"retry","use_same_key":true}') == (
        "retry",
        True,
    )
    assert _parse_action('{"action":"invoke","use_same_key":false}') == (
        "invoke",
        False,
    )
    for raw in (
        '{"action":"retry"}',
        '{"action":"retry","use_same_key":1}',
        '{"action":"retry","use_same_key":true,"extra":false}',
        '{"action":"unknown","use_same_key":true}',
        '[]',
    ):
        assert _parse_action(raw) == ("stop", False)


def test_subprocess_adapter_reports_failures_and_accepts_text(tmp_path) -> None:
    script = tmp_path / "model.py"
    script.write_text("import sys; print('{\"action\":\"stop\"}')")
    adapter = SubprocessModelAdapter((sys.executable, str(script)))
    assert '"action":"stop"' in adapter("choose")
