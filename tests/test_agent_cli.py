import json

from retry_safety.agent_cli import main


def test_agent_cli_writes_manifest_result_and_trace(tmp_path, capsys) -> None:
    result = tmp_path / "result.json"
    manifest = tmp_path / "manifest.json"
    trace = tmp_path / "trace.jsonl"
    assert (
        main(
            [
                "--trials",
                "1",
                "--json",
                str(result),
                "--manifest",
                str(manifest),
                "--trace-jsonl",
                str(trace),
            ]
        )
        == 0
    )
    result_data = json.loads(result.read_text())
    assert result_data["schema_version"] == "retry-safety-agent-v1"
    assert json.loads(manifest.read_text())["schema_version"].endswith("manifest-v1")
    assert len(trace.read_text().splitlines()) == len(result_data["trials"])
    assert f"trial_rows: {len(result_data['trials'])}" in capsys.readouterr().out
