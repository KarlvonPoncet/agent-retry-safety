"""UI and data adapters for the retry-safety Streamlit dashboard.

The module deliberately has no hard dependency on Streamlit.  That keeps the
normalization and deterministic demo dataset usable in small unit tests and
lets ``app.py`` provide a clear error when somebody runs the UI without the
optional Streamlit dependency installed.
"""

# Embedded HTML/CSS intentionally uses long readable lines.
# ruff: noqa: E501

from __future__ import annotations

import importlib
import inspect
import math
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from html import escape
from typing import Any

# These values intentionally mirror the public core enums. The labels remain
# plain language so the UI teaches the concept rather than the Python spelling.
POLICY_OPTIONS = (
    "blind_retry",
    "status_before_retry",
    "idempotency_key_retry",
    "no_retry",
)

POLICY_LABELS = {
    "blind_retry": "Blind retry",
    "status_before_retry": "Status-before-retry",
    "idempotency_key_retry": "Idempotency key",
    "no_retry": "No retry",
}

TOOL_OPTIONS = (
    "non_idempotent_mutation",
    "idempotent_mutation",
    "read_only",
)

FAILURE_TIMINGS = (
    "after_commit",
    "before_commit",
    "random",
)

METRIC_LABELS = {
    "duplicate_side_effect_rate": "Duplicate side effect rate",
    "final_state_correctness": "Final-state correctness",
    "retry_rate": "Retry rate",
    "response_loss_rate": "Response loss rate",
    "status_before_retry_rate": "Status-before-retry rate",
}

_RATE_METRICS = {
    "rate",
    "ratio",
    "fraction",
    "correctness",
    "accuracy",
    "probability",
    "percentage",
}


@dataclass(frozen=True)
class DashboardSettings:
    """Values collected by the sidebar before a run."""

    seed: int = 7
    trials: int = 20
    tool_type: str = TOOL_OPTIONS[0]
    failure_timing: str = "after_commit"
    failure_rate: float = 0.35
    policies: tuple[str, ...] = POLICY_OPTIONS

    @property
    def tool_types(self) -> tuple[str, ...]:
        """Return the selected tool in a collection for the core config."""

        return (self.tool_type,)

    @property
    def selected_policies(self) -> tuple[str, ...]:
        """Return the selected policies under the core API's terminology."""

        return self.policies

    def validated(self) -> DashboardSettings:
        """Return a bounded copy suitable for either the demo or core runner."""

        policies = tuple(
            canonical
            for canonical in (_canonical_policy(policy) for policy in self.policies)
            if canonical in POLICY_OPTIONS
        )
        tool_aliases = {
            "database_write": "non_idempotent_mutation",
            "email_send": "non_idempotent_mutation",
            "payment_charge": "non_idempotent_mutation",
            "file_write": "non_idempotent_mutation",
        }
        tool_type = tool_aliases.get(self.tool_type, self.tool_type)
        return DashboardSettings(
            seed=int(self.seed),
            trials=max(1, min(int(self.trials), 100_000)),
            tool_type=(tool_type if tool_type in TOOL_OPTIONS else TOOL_OPTIONS[0]),
            failure_timing=(
                self.failure_timing
                if self.failure_timing in FAILURE_TIMINGS
                else "after_commit"
            ),
            failure_rate=max(0.0, min(float(self.failure_rate), 1.0)),
            policies=policies or ("no_retry",),
        )


def _canonical_policy(policy: Any) -> str:
    value = str(policy).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "blind": "blind_retry",
        "blind_retries": "blind_retry",
        "blind_retry_policy": "blind_retry",
        "status_check": "status_before_retry",
        "status_before_retries": "status_before_retry",
        "status_before_retry_policy": "status_before_retry",
        "idempotency": "idempotency_key_retry",
        "idempotency_key": "idempotency_key_retry",
        "idempotency_keys": "idempotency_key_retry",
        "idempotent_retry": "idempotency_key_retry",
        "never_retry": "no_retry",
        "none": "no_retry",
    }
    return aliases.get(value, value)


def policy_label(policy: Any) -> str:
    """Return a concise, plain-language label for a policy identifier."""

    canonical = _canonical_policy(policy)
    if canonical in POLICY_LABELS:
        return POLICY_LABELS[canonical]
    return str(policy).replace("_", " ").replace("-", " ").title()


def metric_label(metric: Any) -> str:
    """Return a readable label while retaining unknown core metrics."""

    key = str(metric)
    if key in METRIC_LABELS:
        return METRIC_LABELS[key]
    return key.replace("_", " ").replace("-", " ").title()


def format_metric(value: Any, metric_name: str | None = None) -> str:
    """Format metric values consistently for cards and comparison tables.

    Rate-like values from the experiment are fractions in the range 0..1.  A
    value over one is treated as an already-percent value, which makes the UI
    tolerant of either common aggregate representation.
    """

    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if not math.isfinite(number):
            return "—"
        name = (metric_name or "").lower().replace("-", "_")
        looks_like_rate = any(token in name for token in _RATE_METRICS) or (
            metric_name is None and 0.0 <= number <= 1.0
        )
        if looks_like_rate:
            percentage = number * 100 if abs(number) <= 1 else number
            return f"{percentage:.1f}%"
        if number.is_integer():
            return str(int(number))
        return f"{number:.2f}"
    return str(value)


def _jsonish(value: Any) -> Any:
    """Convert common result objects to values safe for Streamlit/JSON."""

    if isinstance(value, Mapping):
        return {str(key): _jsonish(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonish(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "item"):
        try:
            return _jsonish(value.item())
        except Exception:
            pass
    return str(value)


def _records_from(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        # A single record can contain nested policy/timeline mappings. Do not
        # mistake those nested values for a mapping keyed by trial id.
        record_keys = {
            "trial_id",
            "trial",
            "tool_type",
            "failure_occurred",
            "failure_stage",
            "mutation_committed",
            "response_delivered",
            "response_lost",
            "state_transition",
            "timeline",
        }
        if any(key in value for key in record_keys):
            return [dict(_jsonish(value))]
        # A mapping keyed by trial id is also a useful serialized record set.
        if any(isinstance(item, Mapping) for item in value.values()):
            records = []
            for key, item in value.items():
                row = dict(_jsonish(item)) if isinstance(item, Mapping) else {"value": item}
                row.setdefault("trial_id", key)
                records.append(row)
            return records
        return [dict(_jsonish(value))]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        records = []
        for index, item in enumerate(value, start=1):
            if isinstance(item, Mapping):
                row = dict(_jsonish(item))
            else:
                row = {"value": _jsonish(item)}
            row.setdefault("trial_id", index)
            records.append(row)
        return records
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
        return _records_from(list(value))
    return [{"value": _jsonish(value), "trial_id": 1}]


def _adapt_trial_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Add renderer-friendly fields to a serialized core trial row."""

    row = dict(record)
    trace = [
        event for event in row.get("trace", []) if isinstance(event, Mapping)
    ]
    ambiguous = any(bool(event.get("ambiguous")) for event in trace)
    committed = any(bool(event.get("committed")) for event in trace)
    status_reads = row.get("status_reads", 0)
    retries = row.get("retries", 0)
    duplicate_count = row.get("duplicate_side_effects", 0)
    failure_injected = bool(row.get("failure_injected", False))
    response_lost = row.get("response_lost")
    if response_lost is None:
        response_lost = ambiguous
    mutation_committed = row.get("mutation_committed")
    if mutation_committed is None:
        mutation_committed = committed
    row.setdefault("failure_occurred", failure_injected)
    row.setdefault("mutation_committed", bool(mutation_committed))
    row.setdefault("response_lost", bool(response_lost))
    row.setdefault("response_delivered", not bool(response_lost))
    row.setdefault("agent_observed_response", not bool(response_lost))
    row.setdefault("status_before_retry", bool(status_reads))
    row.setdefault("retry_attempted", bool(retries))
    row.setdefault("duplicate_side_effect", bool(duplicate_count))
    if "final_state_correct" not in row:
        row["final_state_correct"] = bool(
            row.get("exact_final_state_correct", False)
        )

    if "state_transition" not in row and trace:
        status_text = "The external state changed." if mutation_committed else "No mutation committed."
        row["state_transition"] = [
            {
                "state": "Mutation committed",
                "status": "done" if mutation_committed else "not reached",
                "detail": status_text,
            },
            {
                "state": "Response delivered",
                "status": "lost" if response_lost else "done",
                "detail": "The response was ambiguous."
                if response_lost
                else "The agent received confirmation.",
            },
            {
                "state": "Status-before-retry",
                "status": "checked" if status_reads else "not used",
                "detail": "An authoritative status read resolved the ambiguity."
                if status_reads
                else "No status read was needed.",
            },
            {
                "state": "Agent's knowledge",
                "status": "unknown" if response_lost else "known",
                "detail": "Retry safety is uncertain."
                if response_lost
                else "The outcome is observable.",
            },
        ]
    return row


def _metrics_from_trials(
    trials: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, float]]:
    """Compute policy-level rates from actual per-trial rows.

    The core aggregates are intentionally detailed by tool and failure phase;
    the dashboard compares the selected tool across those cells, so the rows
    are the least ambiguous source for one policy-level headline.
    """

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for trial in trials:
        if trial.get("policy") is None:
            continue
        grouped.setdefault(_canonical_policy(trial["policy"]), []).append(trial)
    metrics: dict[str, dict[str, float]] = {}
    for policy, rows in grouped.items():
        count = len(rows)
        if not count:
            continue
        duplicate_values = [
            bool(row.get("duplicate_side_effect", row.get("duplicate_side_effects", 0)))
            for row in rows
        ]
        correct_values = [
            bool(row.get("final_state_correct", row.get("exact_final_state_correct", False)))
            for row in rows
        ]
        retry_values = [bool(row.get("retry_attempted", row.get("retries", 0))) for row in rows]
        metrics[policy] = {
            "duplicate_side_effect_rate": sum(duplicate_values) / count,
            "final_state_correctness": sum(correct_values) / count,
            "retry_rate": sum(retry_values) / count,
            "successful_completion_rate": sum(
                bool(row.get("successful_completion", False)) for row in rows
            )
            / count,
            "mean_duplicate_side_effects": sum(
                float(row.get("duplicate_side_effects", 0)) for row in rows
            )
            / count,
            "mean_retries": sum(float(row.get("retries", 0)) for row in rows) / count,
            "mean_status_reads": sum(float(row.get("status_reads", 0)) for row in rows)
            / count,
            "mean_calls": sum(float(row.get("calls", 0)) for row in rows) / count,
            "mean_cost": sum(float(row.get("cost", 0)) for row in rows) / count,
        }
    return metrics


def _metrics_from(value: Any) -> dict[str, dict[str, Any]]:
    """Normalize the few aggregate layouts used by experiment prototypes."""

    if value is None:
        return {}
    if isinstance(value, Mapping):
        for wrapper in ("by_policy", "policies", "policy_metrics"):
            if wrapper in value and isinstance(value[wrapper], (Mapping, Sequence)):
                value = value[wrapper]
                break

    result: dict[str, dict[str, Any]] = {}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            if not isinstance(item, Mapping):
                continue
            policy = item.get("policy", item.get("name", item.get("id")))
            if policy is None:
                continue
            nested = item.get("metrics", item.get("values"))
            if isinstance(nested, Mapping):
                values = dict(nested)
            else:
                values = {
                    str(key): item[key]
                    for key in item
                    if key
                    not in {
                        "policy",
                        "name",
                        "id",
                        "tool_kind",
                        "failure_phase",
                        "trials",
                    }
                }
            result.setdefault(_canonical_policy(policy), {}).update(_jsonish(values))
        return result

    if not isinstance(value, Mapping):
        return result

    # Also accept {metric: {policy: value}}, a convenient tabular shape.
    metric_aliases = {
        *METRIC_LABELS,
        "duplicate_rate",
        "duplicate_side_effects",
        "correctness",
        "final_state_correctness_rate",
        "retry_count",
        "retries",
    }
    if value and all(isinstance(item, Mapping) for item in value.values()) and any(
        str(metric) in metric_aliases for metric in value
    ):
        transposed: dict[str, dict[str, Any]] = {}
        for metric, policy_values in value.items():
            if not isinstance(policy_values, Mapping):
                continue
            for policy, metric_value in policy_values.items():
                transposed.setdefault(_canonical_policy(policy), {})[str(metric)] = _jsonish(
                    metric_value
                )
        if transposed:
            return transposed

    # The normal contract is {policy: {metric: value}}.
    for policy, metrics in value.items():
        if isinstance(metrics, Mapping):
            result[_canonical_policy(policy)] = dict(_jsonish(metrics))
        else:
            result[_canonical_policy(policy)] = {"value": _jsonish(metrics)}
    return result


def _payload_from(raw: Any) -> Any:
    if hasattr(raw, "to_dict") and callable(raw.to_dict):
        raw = raw.to_dict()
    if isinstance(raw, Mapping):
        return _jsonish(raw)
    if isinstance(raw, tuple) and len(raw) == 2:
        return {"trials": raw[0], "policy_metrics": raw[1]}
    if isinstance(raw, list):
        return {"trials": raw}
    return {"trials": raw}


def _metric_value(metrics: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        if name in metrics:
            return metrics[name]
    return None


def _derive_summary(
    trials: Sequence[Mapping[str, Any]], metrics: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    response_losses = 0
    for trial in trials:
        if trial.get("response_lost") is True or trial.get("response_delivered") is False:
            response_losses += 1
    summary: dict[str, Any] = {
        "trials": len(trials),
        "response_loss_rate": (response_losses / len(trials) if trials else 0.0),
    }
    # Prefer the first selected policy for the headline cards. The comparison
    # section still shows every aggregate independently.
    first_metrics = next(iter(metrics.values()), {})
    for key, aliases in {
        "duplicate_side_effect_rate": (
            "duplicate_side_effect_rate",
            "duplicate_rate",
            "duplicate_side_effects",
        ),
        "final_state_correctness": (
            "final_state_correctness",
            "final_state_correctness_rate",
            "correctness",
        ),
        "retry_rate": ("retry_rate", "retries"),
    }.items():
        value = _metric_value(first_metrics, aliases)
        if value is not None:
            summary[key] = value
    return summary


def normalize_results(raw: Any) -> dict[str, Any]:
    """Adapt core output into the small shape used by the entire UI.

    Supported input forms include a ``to_dict()`` result, the contract's
    ``{"trials": ..., "policy_metrics": ...}`` mapping, and prototype aliases
    such as ``records``/``aggregates``.  Keeping this reconciliation here
    prevents result-shape assumptions from leaking into rendering code.
    """

    payload = _payload_from(raw)
    if not isinstance(payload, Mapping):
        payload = {"trials": payload}
    trial_value = next(
        (
            payload[key]
            for key in (
                "trials",
                "records",
                "results",
                "per_trial",
                "per_trial_records",
                "trial_records",
            )
            if key in payload
        ),
        [],
    )
    metric_value_raw = next(
        (
            payload[key]
            for key in (
                "policy_metrics",
                "aggregate_policy_metrics",
                "aggregate_metrics",
                "aggregates",
                "policy_aggregates",
                "metrics",
                "policy_results",
            )
            if key in payload
        ),
        {},
    )
    trials = [_adapt_trial_record(record) for record in _records_from(trial_value)]
    metrics = _metrics_from(metric_value_raw)
    # The merged core emits detailed aggregate cells while the dashboard needs
    # a compact policy comparison. Per-trial rates are authoritative here.
    for policy, trial_metrics in _metrics_from_trials(trials).items():
        metrics.setdefault(policy, {}).update(trial_metrics)
    for values in metrics.values():
        if "exact_final_state_rate" in values:
            values.setdefault("final_state_correctness", values["exact_final_state_rate"])
    supplied_summary = payload.get("summary", {})
    summary = dict(_jsonish(supplied_summary)) if isinstance(supplied_summary, Mapping) else {}
    derived = _derive_summary(trials, metrics)
    for key, value in derived.items():
        summary.setdefault(key, value)
    return {
        "trials": trials,
        "policy_metrics": metrics,
        "summary": summary,
    }


def _policy_outcome(
    policy: str,
    *,
    response_lost: bool,
    mutation_committed: bool,
    status_before_retry: bool,
) -> dict[str, Any]:
    if not response_lost:
        retry = False
        duplicate = False
        correct = True
    elif policy == "blind_retry":
        retry = True
        duplicate = mutation_committed
        correct = True
    elif policy == "status_before_retry":
        retry = not status_before_retry
        duplicate = False
        correct = True
    elif policy == "idempotency_key_retry":
        retry = True
        duplicate = False
        correct = True
    else:  # no_retry, and a conservative behavior for future policy names
        retry = False
        duplicate = False
        correct = mutation_committed
    return {
        "retry_attempted": retry,
        "duplicate_side_effect": duplicate,
        "final_state_correct": correct,
    }


def build_demo_results(
    *,
    seed: int = 7,
    trials: int = 20,
    tool_type: str = TOOL_OPTIONS[0],
    failure_timing: str = "after_commit",
    failure_rate: float = 0.35,
    policies: Sequence[str] = POLICY_OPTIONS,
) -> dict[str, Any]:
    """Create a deterministic, dependency-free dataset for the first render."""

    settings = DashboardSettings(
        seed=seed,
        trials=trials,
        tool_type=tool_type,
        failure_timing=failure_timing,
        failure_rate=failure_rate,
        policies=tuple(policies),
    ).validated()
    rng = random.Random(settings.seed)
    records: list[dict[str, Any]] = []
    for index in range(1, settings.trials + 1):
        failure = rng.random() < settings.failure_rate
        if not failure:
            mutation_committed = True
            stage = "response_delivered"
        elif settings.failure_timing == "before_commit":
            mutation_committed = False
            stage = "before_mutation"
        elif settings.failure_timing == "after_commit":
            mutation_committed = True
            stage = "after_mutation_before_response"
        else:
            mutation_committed = rng.random() >= 0.35
            stage = (
                "after_mutation_before_response"
                if mutation_committed
                else "before_mutation"
            )
        response_delivered = not failure
        response_lost = not response_delivered
        status_before_retry = mutation_committed if response_lost else False
        outcomes = {
            policy: _policy_outcome(
                policy,
                response_lost=response_lost,
                mutation_committed=mutation_committed,
                status_before_retry=status_before_retry,
            )
            for policy in settings.policies
        }
        records.append(
            {
                "trial_id": index,
                "tool_type": settings.tool_type,
                "failure_timing": settings.failure_timing,
                "failure_occurred": failure,
                "failure_stage": stage,
                "mutation_committed": mutation_committed,
                "response_delivered": response_delivered,
                "response_lost": response_lost,
                "agent_observed_response": response_delivered,
                "status_before_retry": status_before_retry,
                "idempotency_key": f"demo-{settings.seed}-{index:03d}",
                "policy_outcomes": outcomes,
                "state_transition": [
                    {
                        "state": "Mutation committed",
                        "status": "done" if mutation_committed else "not reached",
                        "detail": "The tool changed the external state."
                        if mutation_committed
                        else "The tool failed before changing state.",
                    },
                    {
                        "state": "Response delivered",
                        "status": "done" if response_delivered else "lost",
                        "detail": "The agent received confirmation."
                        if response_delivered
                        else "The response disappeared after the tool call.",
                    },
                    {
                        "state": "Agent's knowledge",
                        "status": "known" if response_delivered else "unknown",
                        "detail": "The agent can distinguish success from failure."
                        if response_delivered
                        else "The agent cannot know whether retry is safe.",
                    },
                ],
            }
        )

    policy_metrics: dict[str, dict[str, float]] = {}
    for policy in settings.policies:
        outcomes = [record["policy_outcomes"][policy] for record in records]
        count = len(outcomes) or 1
        policy_metrics[policy] = {
            "duplicate_side_effect_rate": sum(
                bool(item["duplicate_side_effect"]) for item in outcomes
            )
            / count,
            "final_state_correctness": sum(
                bool(item["final_state_correct"]) for item in outcomes
            )
            / count,
            "retry_rate": sum(bool(item["retry_attempted"]) for item in outcomes) / count,
        }
    return normalize_results(
        {
            "trials": records,
            "policy_metrics": policy_metrics,
            "summary": {
                "trials": len(records),
                "response_loss_rate": sum(record["response_lost"] for record in records)
                / (len(records) or 1),
                "demo": True,
            },
        }
    )


def _make_contract_config(config_class: Any, settings: DashboardSettings) -> Any:
    """Instantiate the core config while tolerating the original UI aliases."""

    phases = {
        "before_commit": ["before_commit"],
        "after_commit": ["after_commit"],
        "random": ["before_commit", "after_commit"],
    }[settings.failure_timing]
    # The merged core names these fields explicitly. The legacy aliases are
    # retained only for a mixed worktree during integration, not used by the
    # rendered UI itself.
    values = {
        "seed": settings.seed,
        "trials": settings.trials,
        "failure_probability": settings.failure_rate,
        "failure_rate": settings.failure_rate,
        "failure_phases": phases,
        "failure_timing": settings.failure_timing,
        "include_no_failure": True,
        "max_attempts": 3,
        "tool_kinds": list(settings.tool_types),
        "tool_types": list(settings.tool_types),
        "tool_type": settings.tool_type,
        "policies": list(settings.selected_policies),
        "selected_policies": list(settings.selected_policies),
    }
    try:
        parameters = inspect.signature(config_class).parameters
    except (TypeError, ValueError):
        parameters = {}
    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    if accepts_kwargs or not parameters:
        return config_class(
            seed=settings.seed,
            trials=settings.trials,
            failure_probability=settings.failure_rate,
            failure_phases=phases,
            include_no_failure=True,
            max_attempts=3,
            tool_kinds=list(settings.tool_types),
            policies=list(settings.selected_policies),
        )
    kwargs = {
        name: values[name]
        for name, parameter in parameters.items()
        if name in values
        and parameter.kind
        not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
    }
    return config_class(**kwargs)


def run_dashboard_experiment(
    settings: DashboardSettings | None = None,
) -> tuple[dict[str, Any], bool]:
    """Run the real contract when installed, otherwise return deterministic demo data.

    The second tuple item is ``True`` only for the local demo/fallback path.
    Errors from an importable core experiment intentionally propagate so the UI
    can show an actionable error instead of silently presenting fake results.
    """

    settings = (settings or DashboardSettings()).validated()
    try:
        core = importlib.import_module("retry_safety")
    except ModuleNotFoundError as exc:
        if exc.name != "retry_safety":
            raise
        return (
            build_demo_results(
                seed=settings.seed,
                trials=settings.trials,
                tool_type=settings.tool_type,
                failure_timing=settings.failure_timing,
                failure_rate=settings.failure_rate,
                policies=settings.policies,
            ),
            True,
        )
    config_class = getattr(core, "ExperimentConfig")
    run_experiment = getattr(core, "run_experiment")
    config = _make_contract_config(config_class, settings)
    return normalize_results(run_experiment(config)), False


def _safe_number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _as_percentage(value: Any) -> float:
    number = _safe_number(value)
    return number * 100 if abs(number) <= 1 else number


def _comparison_rows(results: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for policy, metrics in results.get("policy_metrics", {}).items():
        metrics = metrics if isinstance(metrics, Mapping) else {}
        rows.append(
            {
                "Policy": policy_label(policy),
                "Final-state correctness": _as_percentage(
                    _metric_value(metrics, ("final_state_correctness", "correctness"))
                ),
                "Duplicate side effect rate": _as_percentage(
                    _metric_value(
                        metrics,
                        ("duplicate_side_effect_rate", "duplicate_rate", "duplicate_side_effects"),
                    )
                ),
                "Retry rate": _as_percentage(
                    _metric_value(metrics, ("retry_rate", "retries"))
                ),
            }
        )
    return rows


def _timeline_html(trial: Mapping[str, Any]) -> str:
    raw_steps = trial.get("state_transition") or trial.get("timeline")
    steps: list[Mapping[str, Any]] = []
    if isinstance(raw_steps, Sequence) and not isinstance(raw_steps, (str, bytes)):
        steps = [step for step in raw_steps if isinstance(step, Mapping)]
    if not steps:
        mutation = bool(trial.get("mutation_committed"))
        response = trial.get("response_delivered") is not False
        steps = [
            {
                "state": "Mutation committed",
                "status": "done" if mutation else "not reached",
                "detail": "External state changed." if mutation else "No mutation yet.",
            },
            {
                "state": "Response delivered",
                "status": "done" if response else "lost",
                "detail": "Confirmation arrived." if response else "Response was lost.",
            },
            {
                "state": "Agent's knowledge",
                "status": "known" if response else "unknown",
                "detail": "Outcome is observable." if response else "Retry safety is uncertain.",
            },
        ]
    cards = []
    for index, step in enumerate(steps, start=1):
        status = str(step.get("status", "unknown")).lower()
        status_class = "lost" if status in {"lost", "unknown", "failed"} else "done"
        cards.append(
            "<div class=\"transition-card\">"
            f"<div class=\"transition-number\" aria-hidden=\"true\">{index}</div>"
            f"<div class=\"transition-state\">{escape(str(step.get('state', 'State')))}</div>"
            f"<div class=\"transition-status {status_class}\">{escape(status.title())}</div>"
            f"<div class=\"transition-detail\">{escape(str(step.get('detail', '')))}</div>"
            "</div>"
        )
    return '<div class="transition-grid" role="list">' + "".join(cards) + "</div>"


def _trial_table_rows(results: Mapping[str, Any], policy: str | None) -> list[dict[str, Any]]:
    rows = []
    for trial in results.get("trials", []):
        outcomes = trial.get("policy_outcomes", {})
        if (
            policy
            and not outcomes
            and trial.get("policy") is not None
            and _canonical_policy(trial["policy"]) != _canonical_policy(policy)
        ):
            continue
        outcome = outcomes.get(policy, {}) if isinstance(outcomes, Mapping) and policy else {}
        rows.append(
            {
                "Trial": trial.get("trial_id", len(rows) + 1),
                "Failure": "Yes" if trial.get("failure_occurred") else "No",
                "Mutation committed": "Yes" if trial.get("mutation_committed") else "No",
                "Response": "Delivered"
                if trial.get("response_delivered") is not False
                else "Lost",
                "Retry attempted": "Yes"
                if outcome.get("retry_attempted", trial.get("retry_attempted"))
                else "No",
                "Duplicate side effect": "Yes"
                if outcome.get("duplicate_side_effect", trial.get("duplicate_side_effect"))
                else "No",
                "Final-state correct": "Yes"
                if outcome.get("final_state_correct", trial.get("final_state_correct"))
                else "No",
            }
        )
    return rows


def _render_styles(st: Any) -> None:
    st.markdown(
        """
<style>
:root { --rs-navy: #12304a; --rs-blue: #1769aa; --rs-teal: #0f766e;
        --rs-amber: #9a5b00; --rs-red: #b42318; --rs-paper: #f7fafc; }
.block-container { max-width: 1400px; padding-top: 2rem; padding-bottom: 3rem; }
.rs-hero { background: linear-gradient(135deg, #e9f3fb 0%, #f7fbfd 100%);
  border: 1px solid #b7d5ea; border-left: 6px solid var(--rs-blue); border-radius: 12px;
  padding: 1.35rem 1.5rem; color: var(--rs-navy); margin-bottom: 1rem; }
.rs-hero h1 { margin: 0 0 .35rem; font-size: clamp(1.55rem, 3vw, 2.25rem); }
.rs-hero p { margin: .35rem 0 0; line-height: 1.55; }
.story-grid, .transition-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: .8rem; margin: .75rem 0 1.2rem; }
.story-card, .transition-card { min-width: 0; overflow-wrap: anywhere; background: var(--rs-paper);
  border: 1px solid #cbd5e1; border-radius: 10px; padding: 1rem; }
.story-number, .transition-number { color: var(--rs-blue); font-size: .8rem; font-weight: 800;
  letter-spacing: .08em; text-transform: uppercase; }
.story-title, .transition-state { color: var(--rs-navy); font-weight: 750; margin-top: .25rem; }
.story-detail, .transition-detail { color: #334155; font-size: .9rem; line-height: 1.45; margin-top: .35rem; }
.transition-grid { grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); }
.transition-card { position: relative; border-top: 4px solid var(--rs-teal); }
.transition-card:has(.transition-status.lost) { border-top-color: var(--rs-red); }
.transition-status { display: inline-block; border-radius: 999px; font-size: .78rem; font-weight: 700;
  margin-top: .5rem; padding: .17rem .5rem; }
.transition-status.done { background: #d9f3ed; color: #075e54; }
.transition-status.lost { background: #fde4e2; color: #8f1d16; }
.rs-demo { background: #fff7e6; border: 1px solid #e5b95c; border-radius: 8px; color: #5e3b00;
  padding: .75rem 1rem; margin: .8rem 0; overflow-wrap: anywhere; }
.rs-real { background: #e9f7f1; border: 1px solid #8ed0b6; border-radius: 8px; color: #075e54;
  padding: .75rem 1rem; margin: .8rem 0; }
.rs-glossary { color: #334155; line-height: 1.55; }
@media (max-width: 720px) { .story-grid { grid-template-columns: 1fr; } .rs-hero { padding: 1rem; } }
</style>
        """,
        unsafe_allow_html=True,
    )


def _render_landing(st: Any) -> None:
    st.markdown(
        """
<section class="rs-hero" aria-label="Retry safety introduction">
  <h1>When a retry can repeat the world</h1>
  <p>Explore why an agent needs more than a timeout before it repeats a tool call.
  The experiment makes the invisible uncertainty after a lost response measurable.</p>
</section>
<div class="story-grid" aria-label="The retry-safety sequence">
  <div class="story-card"><div class="story-number">01 · mutation commits</div>
    <div class="story-title">The tool changes external state</div>
    <div class="story-detail">A database write, payment, email, or file operation may already have happened.</div>
  </div>
  <div class="story-card"><div class="story-number">02 · response is lost</div>
    <div class="story-title">Confirmation disappears</div>
    <div class="story-detail">A network failure hides the result, even though the mutation may be complete.</div>
  </div>
  <div class="story-card"><div class="story-number">03 · safe retry is unknown</div>
    <div class="story-title">The agent cannot know whether retry is safe</div>
    <div class="story-detail">Retrying can create a duplicate side effect; never retrying can leave work undone.</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "The dashboard compares policies under the same seeded failures. It is an educational model, not a production safety guarantee."
    )


def _render_sidebar(st: Any) -> tuple[DashboardSettings, bool]:
    sidebar = st.sidebar
    sidebar.header("Experiment controls")
    seed = sidebar.number_input(
        "Seed",
        min_value=0,
        value=7,
        step=1,
        help="The random seed makes a run reproducible: the same settings produce the same failures.",
    )
    trials = sidebar.number_input(
        "Trial count",
        min_value=1,
        max_value=100_000,
        value=20,
        step=1,
        help="Number of independent tool-call trials to simulate.",
    )
    tool_type = sidebar.selectbox(
        "Tool type",
        options=list(TOOL_OPTIONS),
        format_func=lambda value: value.replace("_", " ").title(),
        help="The kind of external side effect the agent is attempting.",
    )
    failure_timing = sidebar.selectbox(
        "Failure timing",
        options=list(FAILURE_TIMINGS),
        format_func=lambda value: {
            "after_commit": "After mutation commit (response lost)",
            "before_commit": "Before mutation commit",
            "random": "Randomly before or after commit",
        }[value],
        help="Where the failure occurs relative to the external mutation.",
    )
    failure_rate = sidebar.slider(
        "Failure rate",
        min_value=0.0,
        max_value=1.0,
        value=0.35,
        step=0.05,
        format="%.0f%%",
        help="The fraction of calls that lose their response or fail before committing.",
    )
    policies = sidebar.multiselect(
        "Policies to compare",
        options=list(POLICY_OPTIONS),
        default=list(POLICY_OPTIONS),
        format_func=policy_label,
        help="Choose how the agent reacts when it cannot tell whether a mutation committed.",
    )
    run_clicked = sidebar.button("Run experiment", type="primary", use_container_width=True)
    return (
        DashboardSettings(
            seed=int(seed),
            trials=int(trials),
            tool_type=tool_type,
            failure_timing=failure_timing,
            failure_rate=float(failure_rate),
            policies=tuple(policies),
        ),
        run_clicked,
    )


def _render_glossary(st: Any) -> None:
    with st.expander("Plain-language guide to the metrics"):
        st.markdown(
            """
<div class="rs-glossary">
<p><strong>Duplicate side effect:</strong> one real-world action happens twice because a retry repeats a mutation that already committed.</p>
<p><strong>Final-state correctness:</strong> whether the intended external state is correct when the policy finishes, regardless of how many calls it made.</p>
<p><strong>Status-before-retry:</strong> asking the tool or service whether the first request committed before sending another mutation.</p>
<p><strong>Idempotency key:</strong> a stable request ID the service uses to recognize a repeated request and apply it only once.</p>
</div>
            """,
            unsafe_allow_html=True,
        )


def _render_results(st: Any, results: Mapping[str, Any], demo: bool) -> None:
    if demo:
        st.markdown(
            '<div class="rs-demo"><strong>Demo data</strong> · The core <code>retry_safety</code> package is not installed yet. '
            "This deterministic dataset keeps the interface useful while integration is in progress.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="rs-real"><strong>Experiment data</strong> · These results came from the installed '
            "<code>retry_safety.ExperimentConfig</code> and <code>run_experiment</code> contract.</div>",
            unsafe_allow_html=True,
        )

    trials = results.get("trials", [])
    metrics = results.get("policy_metrics", {})
    summary = results.get("summary", {})
    st.subheader("Results at a glance")
    response_loss = summary.get("response_loss_rate")
    if response_loss is None:
        response_loss = 0.0
    first_metrics = next(iter(metrics.values()), {})
    cards = [
        ("Trials", format_metric(summary.get("trials", len(trials)), "count"), "Independent calls"),
        ("Response loss", format_metric(response_loss, "response_loss_rate"), "Agent loses confirmation"),
        (
            "Duplicate side effects",
            format_metric(
                _metric_value(
                    first_metrics,
                    ("duplicate_side_effect_rate", "duplicate_rate", "duplicate_side_effects"),
                ),
                "duplicate_side_effect_rate",
            ),
            "For the first listed policy",
        ),
        (
            "Final-state correctness",
            format_metric(
                _metric_value(
                    first_metrics,
                    ("final_state_correctness", "final_state_correctness_rate", "correctness"),
                ),
                "final_state_correctness",
            ),
            "For the first listed policy",
        ),
    ]
    columns = st.columns(4)
    for column, (label, value, help_text) in zip(columns, cards):
        with column:
            column.metric(label, value, help=help_text)
            column.caption(help_text)

    _render_glossary(st)
    st.subheader("Policy comparison")
    st.caption(
        "Higher final-state correctness is better. Lower duplicate side effect rate is safer. Bars show percentages."
    )
    comparison = _comparison_rows(results)
    if comparison:
        st.bar_chart(
            comparison,
            x="Policy",
            y=["Final-state correctness", "Duplicate side effect rate"],
            color=["#1769aa", "#b42318"],
            use_container_width=True,
        )
        metric_table = []
        for row in comparison:
            metric_table.append(
                {
                    "Policy": row["Policy"],
                    "Final-state correctness": format_metric(
                        row["Final-state correctness"], "percentage"
                    ),
                    "Duplicate side effect rate": format_metric(
                        row["Duplicate side effect rate"], "percentage"
                    ),
                    "Retry rate": format_metric(row["Retry rate"], "percentage"),
                }
            )
        st.dataframe(metric_table, hide_index=True, use_container_width=True)
    else:
        st.info("No policy metrics were returned. Select at least one policy and run again.")

    st.subheader("Failure timeline")
    st.caption(
        "Select a trial to inspect the state transition: a committed mutation can be real even when its response is lost."
    )
    if trials:
        trial_options = list(range(len(trials)))
        selected_index = st.selectbox(
            "Trial to inspect",
            trial_options,
            format_func=lambda index: f"Trial {trials[index].get('trial_id', index + 1)}",
        )
        selected_trial = trials[selected_index]
        st.markdown(_timeline_html(selected_trial), unsafe_allow_html=True)
    else:
        st.info("No trial records were returned. The timeline will appear after a successful run.")

    st.subheader("Per-trial inspection")
    selected_policy = next(iter(metrics), None)
    if metrics:
        selected_policy = st.selectbox(
            "Policy outcome shown in the table",
            options=list(metrics),
            format_func=policy_label,
            key="trial_table_policy",
        )
    table_rows = _trial_table_rows(results, selected_policy)
    if table_rows:
        st.dataframe(table_rows, hide_index=True, use_container_width=True)
        st.caption(
            f"The table shows whether the selected {policy_label(selected_policy) if selected_policy else 'policy'} "
            "would retry and whether the final state was correct."
        )
    else:
        st.info("There are no per-trial records to inspect yet.")
    with st.expander("Normalized result payload"):
        st.json(results)


def main(st_module: Any | None = None) -> None:
    """Render the Streamlit application."""

    if st_module is None:
        try:
            import streamlit as st_module  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depends on local install
            raise RuntimeError(
                "Streamlit is required to run the dashboard. Install it, then run `streamlit run app.py`."
            ) from exc
    st_module.set_page_config(
        page_title="Agent Retry Safety",
        page_icon="↻",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _render_styles(st_module)
    _render_landing(st_module)
    settings, run_clicked = _render_sidebar(st_module)
    settings = settings.validated()
    if run_clicked or "retry_safety_dashboard_results" not in st_module.session_state:
        try:
            results, demo = run_dashboard_experiment(settings)
            st_module.session_state["retry_safety_dashboard_results"] = results
            st_module.session_state["retry_safety_dashboard_demo"] = demo
            st_module.session_state.pop("retry_safety_dashboard_error", None)
        except Exception as exc:  # show a useful state without hiding core failures
            st_module.session_state["retry_safety_dashboard_error"] = str(exc)
            if run_clicked:
                st_module.session_state.pop("retry_safety_dashboard_results", None)
    error = st_module.session_state.get("retry_safety_dashboard_error")
    if error:
        st_module.error("The experiment could not run.")
        with st_module.expander("Technical details"):
            st_module.code(error)
        st_module.info(
            "Check the experiment configuration and rerun. Demo data is used automatically only when the core package is absent."
        )
        return
    results = st_module.session_state.get("retry_safety_dashboard_results")
    if results is None:
        st_module.info("Set the controls in the sidebar, then choose Run experiment to see results.")
        return
    _render_results(
        st_module,
        results,
        bool(st_module.session_state.get("retry_safety_dashboard_demo", False)),
    )


if __name__ == "__main__":  # pragma: no cover - Streamlit executes this file
    main()
