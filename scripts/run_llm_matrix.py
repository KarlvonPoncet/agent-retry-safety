#!/usr/bin/env python3
"""Run the authenticated single-facility LLM matrix used by the paper."""

from __future__ import annotations

import json
import os
from pathlib import Path

from retry_safety.agent_benchmark import (
    AgentBenchmarkConfig,
    AgentControllerKind,
    SubprocessModelAdapter,
    result_to_json,
    run_agent_benchmark,
    write_jsonl_trace,
)


def main() -> int:
    model_id = os.environ.get("RETRY_SAFETY_CODEX_MODEL", os.environ.get("PI_MODEL"))
    if not model_id:
        raise SystemExit(
            "set RETRY_SAFETY_CODEX_MODEL or PI_MODEL; no model comparison is inferred"
        )
    config = AgentBenchmarkConfig(
        seed=20260825,
        trials=3,
        controllers=(AgentControllerKind.LLM,),
    )
    model = SubprocessModelAdapter(
        ("./scripts/codex_action.sh",), model_name=f"codex:{model_id}"
    )
    result = run_agent_benchmark(config, model=model)
    artifacts = Path("paper/artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "llm_matrix.json").write_text(
        result_to_json(result), encoding="utf-8"
    )
    (artifacts / "llm_matrix_manifest.json").write_text(
        json.dumps(
            {
                "model_name": model.model_name,
                "model_source": (
                    "authenticated codex exec; final schema-constrained JSON only"
                ),
                "config": config.to_dict(),
                "skipped_controllers": list(result.skipped_controllers),
                "private_reasoning_recorded": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    write_jsonl_trace(artifacts / "llm_matrix_traces.jsonl", result)
    print(f"wrote {len(result.trials)} LLM rows for {model.model_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
