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
    assert json.loads(result.read_text())["schema_version"] == "retry-safety-agent-v1"
    assert json.loads(manifest.read_text())["schema_version"].endswith("manifest-v1")
    assert len(trace.read_text().splitlines()) == 192
    assert "trial_rows: 192" in capsys.readouterr().out
