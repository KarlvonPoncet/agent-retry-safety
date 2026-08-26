"""Dependency-free analysis and figure generation for benchmark artifacts."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

DEFAULT_GROUP_FIELDS = (
    "controller",
    "protocol_variant",
    "task_family",
    "semantics",
    "held_out_tool",
    "error_wording",
    "failure_phase",
)


def wilson_interval(
    successes: int, trials: int, z: float = 1.96
) -> tuple[float, float]:
    """Return a two-sided Wilson interval for a binomial proportion."""

    if trials <= 0:
        return 0.0, 0.0
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    margin = (
        z
        * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials)
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def summarize_rows(
    rows: Iterable[Mapping[str, Any]],
    group_fields: tuple[str, ...] = DEFAULT_GROUP_FIELDS,
) -> list[dict[str, Any]]:
    """Summarize raw trial rows with Wilson intervals and means."""

    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(field) for field in group_fields)].append(row)
    summaries: list[dict[str, Any]] = []
    for key, group in sorted(groups.items(), key=lambda item: str(item[0])):
        n = len(group)
        unsafe = sum(bool(row["unsafe_retry"]) for row in group)
        completion = sum(bool(row["successful_completion"]) for row in group)
        exact = sum(bool(row["exact_final_state_correct"]) for row in group)
        unsafe_low, unsafe_high = wilson_interval(unsafe, n)
        completion_low, completion_high = wilson_interval(completion, n)
        summaries.append(
            {
                **dict(zip(group_fields, key)),
                "trials": n,
                "unsafe_retries": unsafe,
                "unsafe_retry_rate": unsafe / n,
                "unsafe_retry_ci_low": unsafe_low,
                "unsafe_retry_ci_high": unsafe_high,
                "successful_completions": completion,
                "successful_completion_rate": completion / n,
                "completion_ci_low": completion_low,
                "completion_ci_high": completion_high,
                "exact_final_states": exact,
                "exact_final_state_rate": exact / n,
                "mean_duplicate_side_effects": sum(
                    float(row["duplicate_side_effects"]) for row in group
                )
                / n,
                "mean_retries": sum(float(row["retries"]) for row in group) / n,
                "mean_status_reads": sum(float(row["status_reads"]) for row in group)
                / n,
                "mean_cost": sum(float(row["cost"]) for row in group) / n,
            }
        )
    return summaries


def load_trials(path: str | Path) -> list[dict[str, Any]]:
    """Load the raw rows from a JSON benchmark artifact."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return list(payload["trials"])


def write_csv(rows: Iterable[Mapping[str, Any]], path: str | Path) -> None:
    rows = list(rows)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        destination.write_text("\n", encoding="utf-8")
        return
    fields = list(rows[0])
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_unsafe_retry_svg(
    rows: Iterable[Mapping[str, Any]], path: str | Path
) -> None:
    """Create a small self-contained SVG figure without a plotting dependency."""

    selected = [
        row
        for row in rows
        if row.get("failure_phase") == "after_commit"
        and row.get("semantics") == "non_idempotent_mutation"
    ]
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in selected:
        grouped[str(row["controller"])].append(row)
    values = {
        key: sum(bool(row["unsafe_retry"]) for row in value) / len(value)
        for key, value in grouped.items()
        if value
    }
    width, height = 760, 390
    chart_left, chart_top, chart_width, chart_height = 70, 35, 650, 270
    bar_width = chart_width / max(1, len(values)) * 0.7
    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" ',
        'viewBox="0 0 760 390">',
        "<style>text{font:12px sans-serif;fill:#222}"
        ".title{font-size:16px;font-weight:bold}"
        ".bar{fill:#34699a}.axis{stroke:#333;stroke-width:1}</style>",
        '<text x="70" y="22" class="title">Unsafe retry rate after commit '
        "(non-idempotent tasks)</text>",
    ]
    for tick in range(0, 6):
        y = chart_top + chart_height - (tick / 5) * chart_height
        value = tick / 5
        svg.append(
            f'<line x1="{chart_left}" y1="{y:.1f}" x2="720" '
            f'y2="{y:.1f}" stroke="#ddd"/>'
        )
        svg.append(f'<text x="38" y="{y + 4:.1f}">{value:.1f}</text>')
    svg.append(
        f'<line class="axis" x1="{chart_left}" y1="{chart_top + chart_height}" '
        f'x2="720" y2="{chart_top + chart_height}"/>'
    )
    for index, (label, value) in enumerate(sorted(values.items())):
        x = chart_left + index * (chart_width / max(1, len(values))) + 10
        bar_height = value * chart_height
        y = chart_top + chart_height - bar_height
        svg.append(
            f'<rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
            f'height="{bar_height:.1f}"/><text x="{x:.1f}" '
            f'y="{chart_top + chart_height + 18}" '
            f'transform="rotate(25 {x:.1f} {chart_top + chart_height + 18})">'
            f"{label}</text>"
        )
        svg.append(
            f'<text x="{x + bar_width / 3:.1f}" y="{y - 5:.1f}">'
            f"{value:.2f}</text>"
        )
    svg.append(
        '<text x="10" y="175" transform="rotate(-90 10 175)">rate</text>'
        '<text x="300" y="375">controller (95% intervals are in '
        'summary.csv)</text></svg>'
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(svg), encoding="utf-8")


def analyze_file(
    input_path: str | Path, output_dir: str | Path
) -> list[dict[str, Any]]:
    """Regenerate the canonical table and figure from raw JSON."""

    rows = load_trials(input_path)
    summaries = summarize_rows(rows)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    write_csv(summaries, destination / "summary.csv")
    write_unsafe_retry_svg(rows, destination / "unsafe_retry_rate.svg")
    return summaries
