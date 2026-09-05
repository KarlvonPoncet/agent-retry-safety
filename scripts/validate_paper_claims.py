#!/usr/bin/env python3
"""Validate headline paper claims against archived benchmark artifacts.

This checks generated outputs, not source-code wording.  It is intentionally
offline: no credentials or model calls are required.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from itertools import product
from math import fsum, isclose
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


TASK_TOOLS = (
    ("payment_charge", "charge_card"),
    ("payment_debit", "debit_payment_method"),
    ("email_send", "send_email"),
    ("message_dispatch", "dispatch_notification"),
    ("shipment_create", "create_shipment"),
    ("parcel_book", "book_parcel"),
    ("ticket_status", "set_ticket_status"),
    ("case_state", "update_case_state"),
    ("calendar_upsert", "upsert_event"),
    ("meeting_upsert", "ensure_meeting"),
    ("order_lookup", "lookup_order"),
    ("purchase_read", "read_purchase_state"),
)
WORDINGS = ("timeout", "connection_lost", "service_unavailable", "held_out")
PROTOCOL_VARIANTS = ("machine_readable", "natural_language", "prompt_only")
DETERMINISTIC_CONTROLLERS = (
    ("no_retry", "none"),
    ("blind_retry", "none"),
    ("status_before_retry", "none"),
    ("same_key_retry", "none"),
    ("rule_safety_wrapper", "none"),
    *(("uncertainty_protocol", variant) for variant in PROTOCOL_VARIANTS),
)


def require_coverage(
    rows: list[dict[str, Any]],
    controller_variants: tuple[tuple[str, str], ...],
    schedule: tuple[tuple[int, str], ...],
    label: str,
) -> None:
    fields = (
        "task_id",
        "tool_name",
        "error_wording",
        "controller",
        "protocol_variant",
        "replicate",
        "failure_phase",
    )
    actual = Counter(tuple(row[field] for field in fields) for row in rows)
    expected = Counter(
        (*task_tool, wording, *controller_variant, *schedule_entry)
        for task_tool, wording, controller_variant, schedule_entry in product(
            TASK_TOOLS, WORDINGS, controller_variants, schedule
        )
    )
    require(actual == expected, f"{label} matrix has missing or duplicate coverage cells")


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
    require_coverage(
        deterministic,
        DETERMINISTIC_CONTROLLERS,
        tuple((replicate, ("before_commit", "after_commit", "none")[replicate % 3])
              for replicate in range(30)),
        "deterministic",
    )
    require_coverage(
        model,
        tuple(("llm", variant) for variant in PROTOCOL_VARIANTS),
        ((0, "before_commit"), (1, "after_commit"), (2, "none")),
        "model",
    )
    phase_counts = Counter(row["failure_phase"] for row in model)
    require(
        phase_counts == Counter({
            "none": 144,
            "before_commit": 144,
            "after_commit": 144,
        }),
        "model matrix must contain 144 rows for each failure phase",
    )
    no_failure_rows = [row for row in model if row["failure_phase"] == "none"]
    failure_rows = [row for row in model if row["failure_phase"] != "none"]
    require(
        all(row["model_calls"] == 0 for row in no_failure_rows),
        "no-failure rows must not invoke the model",
    )
    require(
        all(row["model_calls"] > 0 for row in failure_rows),
        "every failure row must invoke the model",
    )
    require(sum(row["model_calls"] for row in model) == 400,
            "model decision count changed; update the paper from artifacts")

    primary = [
        row for row in deterministic
        if row["semantics"] == "non_idempotent_mutation"
        and row["failure_phase"] == "after_commit"
    ]
    primary_outcomes = {
        ("no_retry", "none"): (False, True, False, 1.0),
        ("blind_retry", "none"): (True, False, True, 2.0),
        ("status_before_retry", "none"): (True, True, False, 3.0),
        ("same_key_retry", "none"): (True, True, False, 2.0),
        ("rule_safety_wrapper", "none"): (True, True, False, 3.0),
        ("uncertainty_protocol", "machine_readable"): (True, True, False, 3.0),
        ("uncertainty_protocol", "natural_language"): (True, True, False, 3.0),
        ("uncertainty_protocol", "prompt_only"): (True, False, True, 2.0),
    }
    for (controller, variant), expected in primary_outcomes.items():
        rows = [
            row
            for row in primary
            if row["controller"] == controller
            and row["protocol_variant"] == variant
        ]
        label = f"{controller}/{variant}"
        require(len(rows) == 240, f"{label}: unexpected primary denominator")
        completion, exact_state, unsafe_retry, cost = expected
        require(
            all(row["successful_completion"] is completion for row in rows),
            f"{label}: archived completion outcome changed",
        )
        require(
            all(row["exact_final_state_correct"] is exact_state for row in rows),
            f"{label}: archived exact-state outcome changed",
        )
        require(
            all(row["unsafe_retry"] is unsafe_retry for row in rows),
            f"{label}: archived unsafe outcome changed",
        )
        require(
            all(row["cost"] == cost for row in rows),
            f"{label}: archived mean cost changed",
        )

    require(all(row["successful_completion"] for row in model),
            "archived model rows are not all complete")
    require(all(row["exact_final_state_correct"] for row in model),
            "archived model rows do not all have exact final state")
    require(all(not row["unsafe_retry"] for row in model),
            "archived model rows contain an unsafe retry")
    non_idempotent_failures = [
        row for row in failure_rows
        if row["semantics"] == "non_idempotent_mutation"
    ]
    require(
        isclose(
            fsum(row["cost"] for row in non_idempotent_failures)
            / len(non_idempotent_failures),
            19 / 2,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "model non-idempotent failure-row mean cost is no longer 9.5",
    )
    variant_costs = {
        "machine_readable": (109 / 12, "9.08"),
        "natural_language": (205 / 24, "8.54"),
        "prompt_only": (421 / 48, "8.77"),
    }
    for variant, (expected, reported) in variant_costs.items():
        rows = [
            row for row in failure_rows
            if row["protocol_variant"] == variant
        ]
        require(
            isclose(
                fsum(row["cost"] for row in rows) / len(rows),
                expected,
                rel_tol=0.0,
                abs_tol=1e-12,
            ),
            f"{variant} failure-row mean cost is no longer {reported}",
        )

    replay_phases: Counter[str] = Counter()
    non_idempotent_replay_phases: Counter[str] = Counter()
    for row in model:
        trial_id = row.get("trial_id", "unknown")
        trace = row.get("trace")
        oracle_trace = row.get("oracle_trace")
        require(isinstance(trace, list) and trace,
                f"model trial {trial_id}: missing trace events")
        require(isinstance(oracle_trace, list) and oracle_trace,
                f"model trial {trial_id}: missing oracle trace events")
        require(all(isinstance(event, dict) for event in trace),
                f"model trial {trial_id}: malformed trace event")
        require(all(isinstance(event, dict) for event in oracle_trace),
                f"model trial {trial_id}: malformed oracle trace event")
        require(
            all(event.get("idempotency_key") != "same-logical-operation-key"
                for event in (*trace, *oracle_trace)),
            f"model trial {trial_id}: placeholder operation key remains",
        )
        require(trace[0].get("action") == "invoke",
                f"model trial {trial_id}: trace must begin with invoke")
        initial_key = trace[0].get("idempotency_key")
        require(isinstance(initial_key, str) and initial_key,
                f"model trial {trial_id}: missing original operation key")
        require(oracle_trace[0].get("idempotency_key") == initial_key,
                f"model trial {trial_id}: trace and oracle keys differ")

        replays = [
            event for event in trace[1:]
            if event.get("action") in ("invoke", "retry")
        ]
        require(row.get("retries") == len(replays),
                f"model trial {trial_id}: retry count disagrees with trace")
        require(all(event.get("idempotency_key") == initial_key
                    for event in replays),
                f"model trial {trial_id}: replay did not use original key")
        oracle_replays = [
            event for event in oracle_trace
            if event.get("attempt", 0) > 1
        ]
        require(len(oracle_replays) == len(replays),
                f"model trial {trial_id}: replay trace disagrees with oracle")
        require(all(event.get("idempotency_key") == initial_key
                    for event in oracle_replays),
                f"model trial {trial_id}: oracle replay used a different key")
        if replays:
            replay_phases[row["failure_phase"]] += len(replays)
            if row["semantics"] == "non_idempotent_mutation":
                non_idempotent_replay_phases[row["failure_phase"]] += len(replays)

        if (row["semantics"] == "non_idempotent_mutation"
                and row["failure_phase"] != "none"):
            require(
                sum(event.get("action") == "reconcile" for event in trace) == 1,
                f"model trial {trial_id}: expected one reconciliation",
            )
            require(
                sum(event.get("event") == "status_read"
                    for event in oracle_trace) == 1,
                f"model trial {trial_id}: reconciliation missing from oracle",
            )

    require(replay_phases == Counter({"before_commit": 132, "after_commit": 22}),
            "model replay phase counts are no longer 132/22")
    require(sum(replay_phases.values()) == 154,
            "model same-key replay count is no longer 154")
    require(
        non_idempotent_replay_phases == Counter({"before_commit": 72}),
        "non-idempotent replay phase counts are no longer 72/0",
    )
    print(
        f"validated deterministic={len(deterministic)} model_rows={len(model)} "
        f"model_decisions={sum(row['model_calls'] for row in model)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
