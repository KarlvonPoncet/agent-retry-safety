import json

from analysis.retry_analysis import analyze_file, summarize_rows, wilson_interval


def test_wilson_interval_is_bounded_and_reproducible() -> None:
    assert wilson_interval(0, 4)[0] == 0.0
    assert wilson_interval(4, 4)[1] == 1.0
    assert wilson_interval(2, 4) == wilson_interval(2, 4)


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
    assert "unsafe" in (
        tmp_path / "analysis" / "unsafe_retry_rate.svg"
    ).read_text().lower()


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
