"""CLI for the opaque-agent benchmark and its reproducible artifacts."""

from __future__ import annotations

import argparse
import shlex
import sys
from collections.abc import Sequence
from pathlib import Path

from .agent_benchmark import (
    AgentBenchmarkConfig,
    AgentBenchmarkResult,
    AgentControllerKind,
    SubprocessModelAdapter,
    benchmark_manifest,
    result_to_json,
    run_agent_benchmark,
    write_jsonl_trace,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="retry-safety-agent",
        description=(
            "Run the agent retry-safety benchmark against the deterministic oracle."
        ),
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--trials", type=_positive_int, default=4)
    parser.add_argument("--max-attempts", type=_positive_int, default=3)
    parser.add_argument("--failure-probability", type=_probability, default=1.0)
    parser.add_argument("--json", dest="json_path", metavar="PATH")
    parser.add_argument("--manifest", metavar="PATH")
    parser.add_argument("--trace-jsonl", metavar="PATH")
    parser.add_argument(
        "--model-command",
        metavar="COMMAND",
        help=(
            "optional already-authenticated command receiving a prompt on stdin "
            "and returning one JSON action"
        ),
    )
    parser.add_argument("--model-name", default="external-command")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    controllers = list(AgentBenchmarkConfig().controllers)
    model = None
    if args.model_command:
        controllers.append(AgentControllerKind.LLM)
        model = SubprocessModelAdapter(
            tuple(shlex.split(args.model_command)), model_name=args.model_name
        )
    config = AgentBenchmarkConfig(
        seed=args.seed,
        trials=args.trials,
        max_attempts=args.max_attempts,
        failure_probability=args.failure_probability,
        controllers=tuple(controllers),
    )
    if args.manifest:
        destination = Path(args.manifest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        import json

        destination.write_text(
            json.dumps(benchmark_manifest(config), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    result = run_agent_benchmark(config, model=model)
    if args.json_path and args.json_path != "-":
        destination = Path(args.json_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(result_to_json(result), encoding="utf-8")
    if args.trace_jsonl:
        write_jsonl_trace(args.trace_jsonl, result)
    if args.format == "json" or args.json_path == "-":
        sys.stdout.write(result_to_json(result))
    else:
        sys.stdout.write(
            _summary(result, args.json_path, args.manifest, args.trace_jsonl)
        )
    return 0


def _summary(
    result: AgentBenchmarkResult,
    json_path: str | None,
    manifest_path: str | None,
    trace_path: str | None,
) -> str:
    # Avoid importing the concrete result type solely for a human-readable summary.
    lines = [
        "agent_experiment:",
        f"  trial_rows: {len(result.trials)}",
        f"  aggregate_cells: {len(result.aggregates)}",
        f"  skipped: {len(result.skipped_controllers)}",
    ]
    if json_path:
        lines.append(f"  json: {json_path}")
    if manifest_path:
        lines.append(f"  manifest: {manifest_path}")
    if trace_path:
        lines.append(f"  trace_jsonl: {trace_path}")
    lines.append("help:")
    lines.append(
        "  use scripts/analyze_results.py to regenerate tables and SVG figures"
    )
    return "\n".join(lines) + "\n"


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _probability(value: str) -> float:
    parsed = float(value)
    if not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
