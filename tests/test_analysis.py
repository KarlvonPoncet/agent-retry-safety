import json

from analysis.retry_analysis import analyze_file, summarize_rows, write_unsafe_retry_svg


def test_analysis_regenerates_csv_and_svg(tmp_path) -> None:
    payload = {
        "trials": [
            {
                "controller": "blind_retry",
                "protocol_variant": "none",
                "task_family": "payment",
                "semantics": "non_idempotent_mutation",
                "held_out_tool": False,
                "error_wording": "timeout",
                "failure_phase": "after_commit",
                "unsafe_retry": True,
                "successful_completion": True,
                "exact_final_state_correct": False,
                "duplicate_side_effects": 1,
                "retries": 1,
                "status_reads": 0,
                "cost": 2,
            },
            {
                "controller": "status_before_retry",
                "protocol_variant": "none",
                "task_family": "payment",
                "semantics": "non_idempotent_mutation",
                "held_out_tool": False,
                "error_wording": "timeout",
                "failure_phase": "after_commit",
                "unsafe_retry": False,
                "successful_completion": True,
                "exact_final_state_correct": True,
                "duplicate_side_effects": 0,
                "retries": 0,
                "status_reads": 1,
                "cost": 3,
            },
        ]
    }
    source = tmp_path / "agent.json"
    source.write_text(json.dumps(payload))
    summaries = analyze_file(source, tmp_path / "analysis")
    assert len(summaries) == 2
    assert (tmp_path / "analysis" / "summary.csv").exists()
    assert "duplicate-effect" in (
        tmp_path / "analysis" / "unsafe_retry_rate.svg"
    ).read_text().lower()
    assert not any("_ci_" in field for field in summaries[0])


def test_summary_stratifies_error_wording() -> None:
    rows = [
        {
            "controller": "blind_retry",
            "protocol_variant": "none",
            "task_family": "payment",
            "semantics": "non_idempotent_mutation",
            "held_out_tool": False,
            "error_wording": wording,
            "failure_phase": "after_commit",
            "unsafe_retry": True,
            "successful_completion": True,
            "exact_final_state_correct": False,
            "duplicate_side_effects": 1,
            "retries": 1,
            "status_reads": 0,
            "cost": 2,
        }
        for wording in ("timeout", "held_out")
    ]
    assert len(summarize_rows(rows)) == 2


def test_figure_preserves_opposite_protocol_variant_outcomes(tmp_path) -> None:
    rows = [
        {
            "controller": "uncertainty_protocol",
            "protocol_variant": variant,
            "failure_phase": "after_commit",
            "semantics": "non_idempotent_mutation",
            "unsafe_retry": unsafe,
        }
        for variant, unsafe in (("machine_readable", False), ("prompt_only", True))
    ]
    path = tmp_path / "figure.svg"
    write_unsafe_retry_svg(rows, path)
    svg = path.read_text()
    assert "machine readable" in svg and "prompt only" in svg
    assert "0.00</text>" in svg and "1.00</text>" in svg
    assert "0.50</text>" not in svg
