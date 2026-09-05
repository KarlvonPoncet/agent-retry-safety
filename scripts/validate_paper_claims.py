#!/usr/bin/env python3
"""Validate headline paper claims against archived benchmark artifacts.

This checks generated outputs, not source-code wording.  It is intentionally
offline: no credentials or model calls are required.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    rows = value.get("trials")
    if not isinstance(rows, list):
        raise ValueError(f"{path}: missing trials list")
    return rows


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deterministic", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()

    deterministic = load(args.deterministic)
    model = load(args.model)
    require(
        len(deterministic) == 11_520,
        "deterministic matrix must contain 11,520 rows",
    )
    require(len(model) == 432, "model matrix must contain 432 configured rows")
    require(sum(row["model_calls"] > 0 for row in model) == 288,
            "only the 288 failure rows should invoke the model")
    require(sum(row["model_calls"] for row in model) == 400,
            "model decision count changed; update the paper from artifacts")

    primary = [
        row for row in deterministic
        if row["semantics"] == "non_idempotent_mutation"
        and row["failure_phase"] == "after_commit"
    ]
    by_controller = Counter(row["controller"] for row in primary)
    require(
        by_controller["blind_retry"] == 240,
        "blind-retry primary denominator changed",
    )
    unsafe = sum(
        row["unsafe_retry"]
        for row in primary
        if row["controller"] == "blind_retry"
    )
    require(
        unsafe == 240,
        "blind retry is no longer 240/240 unsafe in the archived run",
    )
    for controller in (
        "same_key_retry",
        "status_before_retry",
        "rule_safety_wrapper",
    ):
        rows = [row for row in primary if row["controller"] == controller]
        require(len(rows) == 240, f"{controller}: unexpected primary denominator")
        require(
            sum(row["unsafe_retry"] for row in rows) == 0,
            f"{controller}: archived unsafe count changed",
        )
    for variant in ("machine_readable", "natural_language", "prompt_only"):
        rows = [
            row
            for row in primary
            if row["controller"] == "uncertainty_protocol"
            and row["protocol_variant"] == variant
        ]
        require(len(rows) == 240, f"{variant}: unexpected primary denominator")
        expected = 240 if variant == "prompt_only" else 0
        require(
            sum(row["unsafe_retry"] for row in rows) == expected,
            f"{variant}: archived unsafe count changed",
        )

    model_failures = [row for row in model if row["failure_phase"] != "none"]
    require(all(row["successful_completion"] for row in model_failures),
            "archived model failure rows are not all complete")
    require(all(not row["unsafe_retry"] for row in model_failures),
            "archived model failure rows contain an unsafe retry")
    print(
        f"validated deterministic={len(deterministic)} model_rows={len(model)} "
        f"model_decisions={sum(row['model_calls'] for row in model)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
