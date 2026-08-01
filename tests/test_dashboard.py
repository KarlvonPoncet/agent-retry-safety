"""Fast, browser-free checks for the retry-safety dashboard adapter and UI data."""

from __future__ import annotations

import sys
from pathlib import Path
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from retry_safety_dashboard.dashboard import (  # noqa: E402
    DashboardSettings,
    build_demo_results,
    format_metric,
    normalize_results,
    policy_label,
    run_dashboard_experiment,
)


class ResultNormalizationTests(unittest.TestCase):
    def test_to_dict_and_alias_keys_are_normalized(self) -> None:
        class CoreResult:
            def to_dict(self):
                return {
                    "records": [{"trial": 1, "response_delivered": False}],
                    "aggregates": {
                        "blind": {
                            "duplicate_rate": 0.25,
                            "final_state_correctness": 0.75,
                        }
                    },
                }

        normalized = normalize_results(CoreResult())
        self.assertEqual(normalized["trials"][0]["trial"], 1)
        self.assertEqual(normalized["policy_metrics"]["blind_retry"]["duplicate_rate"], 0.25)
        self.assertEqual(normalized["summary"]["response_loss_rate"], 1.0)

    def test_tuple_and_mapping_records_are_supported(self) -> None:
        normalized = normalize_results(
            (
                {"trial-a": {"response_lost": True}},
                {"no_retry": {"final_state_correctness": 0.5}},
            )
        )
        self.assertEqual(len(normalized["trials"]), 1)
        self.assertEqual(normalized["trials"][0]["trial_id"], "trial-a")
        self.assertEqual(normalized["policy_metrics"]["no_retry"]["final_state_correctness"], 0.5)

    def test_transposed_metric_table_is_supported(self) -> None:
        normalized = normalize_results(
            {
                "trials": [],
                "metrics": {
                    "final_state_correctness": {"blind_retry": 0.9},
                    "duplicate_side_effect_rate": {"blind_retry": 0.2},
                },
            }
        )
        self.assertEqual(
            normalized["policy_metrics"]["blind_retry"]["final_state_correctness"],
            0.9,
        )


class DemoDataTests(unittest.TestCase):
    def test_demo_data_is_deterministic(self) -> None:
        first = build_demo_results(seed=11, trials=8, failure_rate=0.5)
        second = build_demo_results(seed=11, trials=8, failure_rate=0.5)
        self.assertEqual(first, second)
        self.assertEqual(len(first["trials"]), 8)
        self.assertIn("blind_retry", first["policy_metrics"])

    def test_demo_data_changes_with_seed(self) -> None:
        first = build_demo_results(seed=11, trials=8, failure_rate=0.5)
        second = build_demo_results(seed=12, trials=8, failure_rate=0.5)
        self.assertNotEqual(first["trials"], second["trials"])


class LabelsAndFormattingTests(unittest.TestCase):
    def test_policy_labels_are_plain_language(self) -> None:
        self.assertEqual(policy_label("blind_retry"), "Blind retry")
        self.assertEqual(policy_label("status-before-retry"), "Status-before-retry")
        self.assertEqual(policy_label("idempotency_key"), "Idempotency key")

    def test_metric_formatting_handles_fractions_counts_and_missing_values(self) -> None:
        self.assertEqual(format_metric(0.875, "final_state_correctness"), "87.5%")
        self.assertEqual(format_metric(3, "retry_count"), "3")
        self.assertEqual(format_metric(None), "—")


class ImportBehaviorTests(unittest.TestCase):
    def test_missing_core_package_uses_demo_without_a_browser(self) -> None:
        with patch.dict(sys.modules, {"retry_safety": None}):
            results, is_demo = run_dashboard_experiment(
                DashboardSettings(seed=3, trials=2, policies=("no_retry",))
            )
        self.assertTrue(is_demo)
        self.assertEqual(len(results["trials"]), 2)

    def test_importable_core_contract_is_used(self) -> None:
        calls = []

        class ExperimentConfig:
            def __init__(
                self,
                *,
                seed,
                trials,
                tool_types,
                failure_timing,
                failure_rate,
                selected_policies,
            ):
                self.values = {
                    "seed": seed,
                    "trials": trials,
                    "tool_types": tool_types,
                    "failure_timing": failure_timing,
                    "failure_rate": failure_rate,
                    "selected_policies": selected_policies,
                }

        def run_experiment(config):
            calls.append(config.values)
            return {
                "trials": [{"trial_id": 1, "response_delivered": True}],
                "policy_metrics": {
                    "no_retry": {"final_state_correctness": 1.0}
                },
            }

        fake_core = types.ModuleType("retry_safety")
        fake_core.ExperimentConfig = ExperimentConfig
        fake_core.run_experiment = run_experiment
        with patch.dict(sys.modules, {"retry_safety": fake_core}):
            results, is_demo = run_dashboard_experiment(
                DashboardSettings(
                    seed=9,
                    trials=1,
                    tool_type="email_send",
                    failure_timing="before_commit",
                    failure_rate=0.2,
                    policies=("no_retry",),
                )
            )
        self.assertFalse(is_demo)
        self.assertEqual(calls[0]["tool_types"], ["email_send"])
        self.assertEqual(calls[0]["selected_policies"], ["no_retry"])
        self.assertEqual(results["policy_metrics"]["no_retry"]["final_state_correctness"], 1.0)


if __name__ == "__main__":
    unittest.main()
