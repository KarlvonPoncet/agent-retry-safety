"""Command-line runner for small, reproducible retry-safety experiments."""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Sequence
from pathlib import Path

from .experiment import result_to_json, run_experiment
from .models import ExperimentConfig, ExperimentResult

_DEFAULT_SMALL_TRIALS = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="retry-safety",
        description="Run the deterministic retry-safety experiment matrix.",
    )
    parser.add_argument(
        "--preset",
        choices=("small",),
        default="small",
        help="preset to run (default: small)",
    )
    parser.add_argument("--seed", type=int, default=42, help="base seed (default: 42)")
    parser.add_argument(
        "--trials",
        type=_positive_int,
        default=None,
        help="matched replicates per tool/policy condition",
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=3,
        help="maximum operation attempts per controller (default: 3)",
    )
    parser.add_argument(
        "--failure-probability",
        type=_probability,
        default=1.0,
        help="probability of applying the scheduled failure (default: 1.0)",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        metavar="PATH",
        help="write complete JSON output to PATH, or '-' for stdout",
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        metavar="PATH",
        help="write one serializable row per trial to PATH",
    )
    parser.add_argument(
        "--format",
        choices=("summary", "json"),
        default="summary",
        help="stdout format when --json is not '-' (default: summary)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    trials = args.trials if args.trials is not None else _DEFAULT_SMALL_TRIALS
    config = ExperimentConfig(
        seed=args.seed,
        trials=trials,
        max_attempts=args.max_attempts,
        failure_probability=args.failure_probability,
    )
    result = run_experiment(config)

    if args.json_path == "-":
        sys.stdout.write(result_to_json(result))
    else:
        if args.json_path:
            _write_json(Path(args.json_path), result)
        if args.csv_path:
            _write_csv(Path(args.csv_path), result)
        if args.format == "json":
            sys.stdout.write(result_to_json(result))
        else:
            sys.stdout.write(_summary(result, args.json_path, args.csv_path))
    return 0


def _write_json(path: Path, result: ExperimentResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result_to_json(result), encoding="utf-8")


def _write_csv(path: Path, result: ExperimentResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "trial_id",
        "seed",
        "tool_kind",
        "policy",
        "failure_phase",
        "failure_injected",
        "initial_state",
        "expected_final_state",
        "final_state",
        "side_effect_count",
        "duplicate_side_effects",
        "exact_final_state_correct",
        "successful_completion",
        "retries",
        "status_reads",
        "calls",
        "cost",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for trial in result.trials:
            row = trial.to_dict()
            writer.writerow({field: row[field] for field in fields})


def _summary(
    result: ExperimentResult,
    json_path: str | None,
    csv_path: str | None,
) -> str:
    lines = [
        "experiment:",
        f"  seed: {result.config.seed}",
        f"  trial_rows: {len(result.trials)}",
        f"  aggregate_cells: {len(result.aggregates)}",
        f"  tools: {len(result.config.tool_kinds)}",
        f"  policies: {len(result.config.policies)}",
    ]
    if json_path:
        lines.append(f"  json: {json_path}")
    if csv_path:
        lines.append(f"  csv: {csv_path}")
    lines.append("help:")
    lines.append("  inspect JSON for per-trial traces and aggregate rates")
    return "\n".join(lines) + "\n"


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _probability(value: str) -> float:
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed


if __name__ == "__main__":  # pragma: no cover - exercised through __main__
    raise SystemExit(main())
