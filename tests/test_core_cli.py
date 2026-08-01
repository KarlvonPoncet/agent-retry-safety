import csv
import json

from retry_safety.cli import main


def test_cli_writes_json_and_csv_results(tmp_path, capsys) -> None:
    json_path = tmp_path / "nested" / "results.json"
    csv_path = tmp_path / "nested" / "results.csv"

    exit_code = main(
        [
            "--seed",
            "5",
            "--trials",
            "1",
            "--json",
            str(json_path),
            "--csv",
            str(csv_path),
        ]
    )

    assert exit_code == 0
    assert json_path.exists()
    assert csv_path.exists()
    payload = json.loads(json_path.read_text())
    assert payload["config"]["seed"] == 5
    assert len(payload["trials"]) == 12
    with csv_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 12
    assert "duplicate_side_effects" in rows[0]
    assert "trial_rows: 12" in capsys.readouterr().out


def test_cli_can_emit_json_to_stdout(capsys) -> None:
    assert main(["--trials", "1", "--json", "-"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert "config" in payload
    assert "aggregates" in payload
