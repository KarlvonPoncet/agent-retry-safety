import json
import sys

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
from retry_safety.agent_benchmark import SubprocessModelAdapter


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
        if "tool:" in prompt:
            return '{"action":"reconcile","use_same_key":true}'
        return '{"action":"invoke","use_same_key":true}'

    result = run_agent_benchmark(
        _config(
            controllers=(AgentControllerKind.LLM,),
            protocol_variants=(ProtocolVariant.MACHINE_READABLE,),
        ),
        model=fake_model,
    )
    row = next(row for row in result.trials if row.task_id == "payment_charge")
    assert row.model_calls >= 1
    assert all("reasoning" not in event.model_output.lower() for event in row.trace)


def test_llm_runs_protocol_ablation_and_counts_only_repeat_invocations() -> None:
    def fake_model(prompt: str) -> str:
        if "tool:" in prompt:
            return '{"action":"retry","use_same_key":false}'
        return '{"action":"invoke","use_same_key":false}'

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


def test_subprocess_adapter_reports_failures_and_accepts_text(tmp_path) -> None:
    script = tmp_path / "model.py"
    script.write_text("import sys; print('{\"action\":\"stop\"}')")
    adapter = SubprocessModelAdapter((sys.executable, str(script)))
    assert '"action":"stop"' in adapter("choose")
