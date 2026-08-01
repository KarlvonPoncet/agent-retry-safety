"""Experimental core for studying retry safety under commit ambiguity.

Stable integration contract::

    from retry_safety import ExperimentConfig, run_experiment

The returned :class:`ExperimentResult` contains typed per-trial rows and
aggregate cells.  Call ``result.to_dict()`` for JSON-compatible data or use the
CLI for JSON/CSV files.
"""

from .experiment import result_from_json, result_to_json, run_experiment
from .models import (
    AggregateResult,
    ExperimentConfig,
    ExperimentResult,
    FailurePhase,
    Policy,
    RetryPolicy,
    ToolKind,
    TraceEvent,
    TrialResult,
)

__all__ = [
    "AggregateResult",
    "ExperimentConfig",
    "ExperimentResult",
    "FailurePhase",
    "Policy",
    "RetryPolicy",
    "ToolKind",
    "TraceEvent",
    "TrialResult",
    "result_from_json",
    "result_to_json",
    "run_experiment",
]

__version__ = "0.1.0"
