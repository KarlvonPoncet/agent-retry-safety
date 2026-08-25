"""Experimental core for studying retry safety under commit ambiguity.

Stable integration contract::

    from retry_safety import ExperimentConfig, run_experiment

The returned :class:`ExperimentResult` contains typed per-trial rows and
aggregate cells.  Call ``result.to_dict()`` for JSON-compatible data or use the
CLI for JSON/CSV files.
"""

from .agent_benchmark import (
    AgentBenchmarkConfig,
    AgentBenchmarkResult,
    AgentControllerKind,
    AgentTrialResult,
    ErrorWording,
    ProtocolVariant,
    TaskFamily,
    TaskSpec,
    benchmark_manifest,
    default_task_specs,
    run_agent_benchmark,
    uncertainty_protocol,
)
from .agent_benchmark import (
    result_from_json as agent_result_from_json,
)
from .agent_benchmark import (
    result_to_json as agent_result_to_json,
)
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
    "AgentBenchmarkConfig",
    "AgentBenchmarkResult",
    "AgentControllerKind",
    "AgentTrialResult",
    "ExperimentConfig",
    "ExperimentResult",
    "ErrorWording",
    "FailurePhase",
    "Policy",
    "RetryPolicy",
    "ProtocolVariant",
    "ToolKind",
    "TaskFamily",
    "TaskSpec",
    "TraceEvent",
    "TrialResult",
    "result_from_json",
    "result_to_json",
    "run_agent_benchmark",
    "agent_result_from_json",
    "agent_result_to_json",
    "benchmark_manifest",
    "default_task_specs",
    "run_experiment",
    "uncertainty_protocol",
]

__version__ = "0.1.0"
