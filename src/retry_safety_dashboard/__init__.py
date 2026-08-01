"""Streamlit dashboard for the retry-safety educational experiment."""

from .dashboard import (
    DashboardSettings,
    METRIC_LABELS,
    POLICY_LABELS,
    POLICY_OPTIONS,
    TOOL_OPTIONS,
    build_demo_results,
    format_metric,
    main,
    normalize_results,
    policy_label,
    run_dashboard_experiment,
)

__all__ = [
    "DashboardSettings",
    "METRIC_LABELS",
    "POLICY_LABELS",
    "POLICY_OPTIONS",
    "TOOL_OPTIONS",
    "build_demo_results",
    "format_metric",
    "main",
    "normalize_results",
    "policy_label",
    "run_dashboard_experiment",
]
