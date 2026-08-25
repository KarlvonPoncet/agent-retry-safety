A payment provider can return `timeout` after it has accepted a charge. An AI agent sees an error, assumes nothing happened, and calls `charge` again. The customer is charged twice even though the agent followed a familiar retry recipe. The dangerous fact is that the client cannot tell whether the request committed.

# Retry Safety Lab

Retry Safety Lab is a small educational research simulator for that failure mode. It studies how deterministic agent/controller policies behave when a tool reports an ambiguous timeout or error around its commit point. Its deterministic state machine remains the ground truth, so the original core is reproducible and easy to inspect. The repository also contains an opaque agent benchmark that evaluates controllers against that same oracle without exposing commit truth.

## The idea in plain language

A **commit** is the point at which a tool's requested change becomes real. A request can fail **before commit** (nothing changed) or **after commit** (the change happened, but the response was lost). In both cases the controller receives the same ambiguous error:

```text
controller                  tool/server
    |       "timeout"          |
    |<--------------------------|  Did the request commit?
    |                           |
    | retry?                    |
```

An **idempotent** operation is safe to repeat: applying `set_status("paid")` twice leaves one paid status. A non-idempotent operation accumulates effects: `charge($10)` twice charges $20. An **idempotency key** is a request identifier that tells the server to apply one logical request once and return the same result for replays.

The simulator compares four controller policies:

| Policy | What it does after the ambiguous error | Main trade-off |
| --- | --- | --- |
| `no_retry` | Stops immediately | No duplicate, but may not finish |
| `blind_retry` | Calls the operation again | Often finishes, but can duplicate a non-idempotent effect |
| `status_before_retry` | Reads authoritative status first; retries only if needed | Extra read, usually avoids the duplicate |
| `idempotency_key_retry` | Retries with the same key | Lets the server deduplicate the replay |

## Experiment matrix

The default run crosses every tool kind with every policy. Each replicate is matched: all policies see the same scheduled failure phase and recorded seed.

| Tool kind | Commit behavior | Expected final state | What it teaches |
| --- | --- | ---: | --- |
| `read_only` | Returns state; changes nothing | `0` | A retry is harmless, but still costs a call |
| `idempotent_mutation` | Sets state to `1`; repeats are equivalent | `1` | Repetition is safe when the operation itself is idempotent |
| `non_idempotent_mutation` | Increments state on every non-deduplicated commit | `1` | Blind retries can create duplicate side effects |

Failure phases are scheduled as `before_commit`, `after_commit`, and (by default) a no-failure baseline. A small run therefore covers both ambiguity locations without depending on random luck. The `failure_probability` setting can turn scheduled failures off while retaining the schedule and seed in the output.

## Architecture

```text
ExperimentConfig (seed, trials, phases, policies)
                 |
                 v
       deterministic phase scheduler
                 |
       +---------+----------+
       |                    |
       v                    v
 controller policy     tool state machine
       |              (commit + failure injection)
       +---------+----------+
                 v
   TrialResult rows + AggregateResult cells
                 |
          JSON / CSV / UI adapter
```

The controller uses a small typed `ToolSession` protocol. An optional agent adapter can implement the same `invoke()` and `read_status()` boundary without changing the simulator or ground-truth metrics. The credential-free core makes no model calls; the completed optional single-facility run is documented below and is not a model comparison.

## Stable Python integration contract

The exact stable imports for the parallel UI lane are:

```python
from retry_safety import ExperimentConfig, run_experiment

config = ExperimentConfig(seed=42, trials=12)
result = run_experiment(config)

# Typed tuples of TrialResult and AggregateResult:
trial_rows = result.trials
aggregate_cells = result.aggregates
json_ready = result.to_dict()
```

Useful additional public types are exported from the same package:

```python
from retry_safety import (
    AggregateResult,
    ExperimentResult,
    FailurePhase,
    Policy,              # alias for RetryPolicy
    RetryPolicy,
    ToolKind,
    TrialResult,
)
```

`ExperimentConfig` accepts enum values or their serialized strings. `trials` means matched replicates per tool/policy condition, so the number of per-trial rows is `trials × number_of_tools × number_of_policies`. `result.to_dict()` is JSON-compatible; `ExperimentResult.from_dict()` and `result_from_json()` restore typed results.

## Setup

Python 3.11 or newer is required. From a clean clone:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

The package has no runtime dependency. The `dev` extra installs pytest, coverage support, and Ruff. The optional `ui` extra installs the visualization stack expected by the graphical lane:

```sh
.venv/bin/python -m pip install -e '.[dev,ui]'
```

## CLI commands

Run the small preset (three matched replicates per condition):

```sh
.venv/bin/retry-safety
```

Choose the seed and trial count, and write complete per-trial JSON plus CSV:

```sh
.venv/bin/retry-safety \
  --seed 42 \
  --trials 20 \
  --json results/retry-safety.json \
  --csv results/retry-safety.csv
```

The JSON contains `config`, `trials`, and `aggregates`. CSV is one row per trial and is convenient for spreadsheet or plotting tools. To emit JSON directly to stdout:

```sh
.venv/bin/retry-safety --trials 2 --json -
```

The equivalent module invocation is useful when the console script is not on `PATH`:

```sh
.venv/bin/python -m retry_safety --seed 7 --trials 4 --json results.json
```

The graphical UI is owned by the parallel UI lane. Once its `app.py` exists, install the UI extra and run exactly:

```sh
.venv/bin/streamlit run app.py
```

## Metrics and interpretation

Every `TrialResult` is calculated from simulator state, not judged by a language model.

| Metric | Definition | Why it matters |
| --- | --- | --- |
| `duplicate_side_effects` | Non-idempotent logical effects beyond the one intended effect; idempotent replays count as zero | Direct safety failure signal |
| `exact_final_state_correct` | Ground-truth final state equals the expected state exactly | Detects over-application even when the controller says it finished |
| `successful_completion` | The controller received success or established completion through status | Separates “the state happens to be right” from “the controller knows it is done” |
| `retries` | Operation calls after the first operation call | Measures retry behavior |
| `status_reads` | Reliable status calls made while resolving ambiguity | Shows the information-gathering cost of the safe policy |
| `calls` | Operation attempts plus status reads | Basic tool-call volume |
| `cost` | One unit per operation attempt and two units per status read | A deliberately simple proxy: status is charged extra because it is an additional round trip |

`exact_final_state_correct` and `successful_completion` are intentionally different. For example, a no-retry controller facing an after-commit failure leaves the state correct but does not know the operation completed. A blind retry can report success while leaving a non-idempotent counter at `2`, which exposes the duplicate.

A **positive result** is a reproducible difference between policies, such as fewer duplicate effects for status-before-retry or idempotency-key retry than for blind retry. Report the condition and metric, not just one overall average. A **null result** means no difference was observed under the selected tools, failure schedule, and trial count; it does not prove that retries are safe in general. Increase trials, add failure schedules, or add tool semantics before drawing a stronger conclusion.

### Example output

```text
experiment:
  seed: 42
  trial_rows: 36
  aggregate_cells: 36
  tools: 3
  policies: 4
  json: results/retry-safety.json
  csv: results/retry-safety.csv
help:
  inspect JSON for per-trial traces and aggregate rates
```

An aggregate JSON cell for a non-idempotent after-commit condition looks like this:

```json
{
  "tool_kind": "non_idempotent_mutation",
  "policy": "blind_retry",
  "failure_phase": "after_commit",
  "successful_completion_rate": 1.0,
  "exact_final_state_rate": 0.0,
  "mean_duplicate_side_effects": 1.0,
  "mean_retries": 1.0,
  "mean_status_reads": 0.0,
  "mean_calls": 2.0,
  "mean_cost": 2.0
}
```

## Tests and quality checks

After installing the development extra, run the complete fast suite:

```sh
.venv/bin/python -m pytest
```

The tests cover before- and after-commit behavior, duplicate detection, all four policies, deterministic replay, JSON round trips, aggregate metrics, and CLI JSON/CSV smoke behavior. Ruff can be run with:

```sh
.venv/bin/ruff check .
```

## Agent benchmark and paper

The agent-facing extension is `retry_safety.agent_benchmark`. It keeps the existing `DeterministicToolSession` as the oracle and adds realistic payment, messaging, fulfillment, support, calendar, and lookup task families; matched train/held-out tool surface forms for every family and operation semantics; four error wordings; paired failure schedules; deterministic baselines; a rule safety wrapper; and a machine-readable commit-uncertainty/reconciliation protocol. The controller-visible adapter never returns the simulator's `committed` field. Raw final model actions and oracle traces are retained in JSON artifacts; private model reasoning is not recorded.

Run the full credential-free deterministic agent matrix and regenerate its table and SVG figure:

```sh
.venv/bin/retry-safety-agent --seed 20260825 --trials 30 \
  --json paper/artifacts/agent_benchmark.json \
  --manifest paper/artifacts/agent_manifest.json \
  --trace-jsonl paper/artifacts/agent_traces.jsonl
.venv/bin/python scripts/analyze_results.py \
  paper/artifacts/agent_benchmark.json paper/artifacts/analysis
```

The original deterministic core matrix remains available and is used as a regression oracle:

```sh
.venv/bin/retry-safety --seed 42 --trials 30 \
  --json paper/artifacts/deterministic_core.json \
  --csv paper/artifacts/deterministic_core.csv
```

An LLM adapter is optional and provider-neutral. The completed single-facility run used an already authenticated Codex CLI, with schema-constrained final JSON only. It does not buy credentials or start a subscription, and no model comparison is claimed:

```sh
RETRY_SAFETY_CODEX_MODEL="$PI_MODEL" .venv/bin/python scripts/run_llm_matrix.py
.venv/bin/python scripts/analyze_results.py \
  paper/artifacts/llm_matrix.json paper/artifacts/llm_analysis
```

The research paper is maintained as Markdown and builds to local HTML without extra runtime dependencies:

```sh
make -C paper
```

`paper/paper.md` contains the abstract, research questions and hypotheses, formal model, related work, benchmark, methods, results, error analysis, mitigation ablations, validity threats, ethics, limitations, conclusion, references, and reproducibility statement. `paper/references.json` records verification URLs and dates for every cited source. `paper/artifacts/` contains the raw manifests/traces and regenerated analysis outputs used by the paper.

## Limitations

This is an educational core, not a production payment simulator. It has one logical operation, one state value, one injected failure, a reliable status endpoint, and no network timing, concurrent writers, partial responses, server outage, authentication, or compensation transaction. The policy controllers are deterministic and do not measure language-model comprehension. The cost function is illustrative rather than a claim about provider pricing. Results are only as broad as the explicit matrix and schedule in `ExperimentConfig`.

## Research extensions

Useful next experiments include:

- multiple failures, delayed or stale status reads, and outages of the status endpoint;
- concurrent agents operating on the same resource;
- tools with conditional writes, leases, compare-and-swap, or transactional outboxes;
- richer non-idempotent effects such as append, email, shipment, and payment authorization;
- controller policies that maintain uncertainty explicitly instead of treating every error alike;
- broader pinned-model LLM evaluations against the same simulator, with tool traces and state as ground truth;
- confidence intervals, cost distributions, and factorial analysis over failure rate and retry budget.

## Related context

The experiment follows long-standing distributed-systems work on at-least-once delivery, duplicate suppression, and the difficulty of providing exactly-once effects across a network. Idempotency tokens and status/reconciliation endpoints are common engineering responses in payment and API systems. It also connects to reliable workflow and tool-use research for agents, where a model may decide to retry after an incomplete observation. This project is a compact teaching and measurement harness combining those ideas; it does not claim absolute novelty or replace domain-specific safety analysis.
