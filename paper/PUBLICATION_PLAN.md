# Publication-readiness plan

## Recommendation

Position this as **a benchmark and measurement-method paper about agent decisions under commit ambiguity**, not a discovery of retry safety or evidence that a new prompt prevents agent failures.

The existing work has a useful deterministic oracle, inspectable traces, explicit limitations, and an honest single-model null result. Its main obstacles are evidentiary and methodological, not prose quality. No plan can guarantee acceptance; the goal is a defensible contribution with independently reproducible evidence.

Recommended path: correct and audit the existing paper first, then strengthen the empirical study for a benchmark/reliability venue. A narrower workshop or technical-report submission is a reasonable alternative if new model evaluation is unavailable. Select the actual venue after checking current scope, deadlines, length, artifact, anonymity, and AI-assistance policies; none have been verified here.

## Review basis

Reviewed `paper.md`, reference metadata, validation notes, README, controller/prompt implementation, model launcher, matrix runner, and model artifact counts. All 12 committed artifact checksums passed during this review. Tests and external literature verification were not rerun. No model calls were made.

Verified from the current model artifacts:

- 432 total rows, but only **288 rows invoke the model**, comprising **400 model decisions**. The 144 no-failure rows return before calling the model.
- Replicate 0 is before commit, replicate 1 is after commit, and replicate 2 is no failure. There is **one invocation trajectory per phase × tool × wording × variant cell**, not three repetitions per phase.
- The manifest identifies the model as `codex:gpt-5.6-luna`. Whether this is an immutable, externally reproducible snapshot needs verification.

## Phase 1 — Repair claims and definitions (publication blockers)

### 1. Correct the experimental accounting

**Files:** `paper/paper.md`, `README.md`, analysis outputs.

- State the design explicitly: deterministic matrix = 12 tools × 4 wordings × 8 controller/variant configurations × 30 schedule entries = 11,520 rows. Model matrix = 12 × 4 × 3 variants × 3 phases = 432 rows.
- Distinguish configuration coverage, repeated deterministic executions, model-exercised trajectories, and individual model decisions.
- Correct §8's assertion that model cells have three replicates for each phase. The three schedule entries cover different phases.
- Describe no-failure model rows as harness controls, not evidence of model behavior.
- Rename “train/held-out” to “base/paraphrased” unless an actual frozen development split and its use can be documented. There is no model training procedure described.

**Done when:** every denominator and replication claim is generated from artifacts and agrees across abstract, methods, results, and limitations.

### 2. Stop interpreting hard-coded policy differences as prompt evidence

**Files:** `src/retry_safety/agent_benchmark.py`, `paper/paper.md` §§4, 6, 7.

- The deterministic `prompt_only` branch explicitly replays without a key. Its duplicate rate follows from the implementation; it does not show that cautionary language fails in an LLM.
- Reframe this as a controller-mechanism sanity check. Remove claims that it establishes the necessity of an explicit protocol: same-key retry already supplies a counterexample under the benchmark assumptions.
- Audit treatment equivalence. The model's natural-language prompt is shorter and less prescriptive than the machine-readable transition system; syntax and information content are confounded.
- Note that `_protocol_prompt` currently returns the same reconciliation prose for deterministic natural-language and prompt-only variants, despite different hard-coded actions.
- Keep the model result prominent: **no observed safety or completion improvement from the protocol variants in the tested setting**.

**Done when:** deterministic mechanism checks and empirical model interventions have separate names, interpretations, and tables.

### 3. Separate safety, success, and knowledge

- Define safety as absence of unintended effects; report exact-state correctness separately. A never-executed operation can be safe but incomplete.
- Call `successful_completion` “observed completion within the trial budget,” rather than implying an unbounded liveness guarantee.
- Rename the existing `unsafe_retry` outcome to “duplicate-effect incidence,” or explicitly state its narrower meaning every time it is interpreted.
- Add a decision-level metric: unprotected replay of a non-idempotent request while commit remains unresolved. Define treatment of authoritative negative status and same-key deduplication before scoring.
- Report false completion/unsupported completion if the action interface is extended to let the model declare success; currently the harness automatically terminates on success or positive status.

**Done when:** a metric dictionary and representative traces distinguish risky decisions, actual harm, final-state correctness, and observed completion.

## Phase 2 — Audit the experimental boundary (before new model runs)

### 4. Establish that the model is isolated from the oracle

**Files:** `scripts/codex_action.sh`, model adapter, boundary tests.

The opaque Python interface does not by itself prove isolation of the external agent. The launcher uses a read-only Codex sandbox, but inherits its working directory and does not visibly disable native tools. Read-only access may still allow reading source, artifacts, local instructions, or hidden state. This is a risk to investigate, not evidence that leakage occurred.

- Prefer a text-only inference API with native tools disabled, or run the agent facility in an isolated directory/container containing no oracle code, results, or repository instructions.
- Document effective system/developer context, enabled tools, working directory, filesystem and network permissions, CLI version, and model settings.
- Add adversarial boundary tests for access to oracle fields, schedules, file paths, and identifier-derived phase information. Keep paired identifiers from inadvertently exposing the answer.
- Retain sanitized execution metadata and tool-use events, not private reasoning, to establish the actual boundary.
- Record malformed outputs, model command failures, timeouts, and retry handling rather than silently losing or replacing unsuccessful evaluations.
- If the historical environment cannot be established, qualify the old run as a pilot and rerun the primary experiment in the audited environment.

**Done when:** an independent reviewer can verify precisely what the model could observe and do.

### 5. Make protocol guarantees match implementation

- Check the advertised “retry once” and “stop/escalate if still unknown” transitions against actual retry-budget handling.
- The current status interface exposes a completion boolean; it cannot exercise an unresolved status outcome. Either scope the current protocol to a reliable two-outcome endpoint or add and test a real `unknown` status.
- State key guarantees explicitly: scope, lifetime, same payload, atomic deduplication, and original-request key attachment.
- Explain that the harness binds `use_same_key=true` to the original bytes. This tests selection of a protected replay, not the model's ability to preserve or generate request identifiers.
- Add paired-observation tests: before- and after-commit trials must be indistinguishable until legitimate reconciliation, apart from phase-independent identifiers.

**Done when:** all claimed protocol transitions and safety assumptions have tests or are explicitly marked untested.

## Phase 3 — Strengthen the contribution and evaluation

### 6. Establish novelty against the closest work

- Search current work on agent fault injection, tool errors, retries, stateful evaluation, transaction safety, durable execution, and idempotency.
- Build a related-work comparison covering hidden commit state, paired counterfactual failures, duplicate-effect scoring, key support, reconciliation, and public replay artifacts.
- Distinguish verified bibliographic metadata from verified novelty. The existing reference record establishes the former, not the latter.
- Update archival versions where appropriate and remove tangential FLP discussion unless it supports a precise argument.
- Consider a short proposition: when pre/post-commit states produce the same observation and neither deduplication nor reconciliation is available, a controller cannot guarantee both exactly one effect and completion across both states. State assumptions and give a short indistinguishability proof, clearly identifying this as established systems reasoning rather than new theory.

**Done when:** the introduction explains a specific missing evaluation capability and supports that gap with current, directly relevant citations.

### 7. Run an informative, preregistered model study

Preserve the existing matrix as version 1. Freeze a versioned protocol, analysis plan, prompts, and scenario set before collecting confirmatory evidence.

**Primary question:** how do available recovery mechanisms and explicit guidance affect duplicate effects, unresolved completion, and recovery cost?

Recommended design:

- Budget permitting, include at least three pinned models spanning two families/providers. This improves coverage, not a guarantee of model-general conclusions. With one model, scope the paper accordingly.
- Compare no extra guidance, caution only, a complete prose protocol, and a semantically equivalent machine-readable protocol.
- Separately vary available mechanisms: status plus keys, keys only, status only, neither. Explicitly document capabilities in the prompt and execution environment.
- Keep explicit semantics as a controlled baseline; add a separate condition using realistic tool documentation without oracle-style semantics labels. The current prompt supplies those labels directly.
- Repeat independent model trajectories within each phase/condition. Use paired scenarios across treatments and randomized/interleaved execution order to reduce service-time confounding.
- Choose sample size from a declared target precision or minimum meaningful effect, with a capped cost estimate and fixed stopping rule. Do not treat paraphrases or repeated deterministic rows as independent random evidence.
- Include all attempts and operational failures. Do not rerun failures selectively or expand tests only until a preferred effect appears.

**High-value realism additions, in order:**

1. Unavailable/unknown status plus repeated transport failures: tests whether the controller preserves uncertainty and respects budgets.
2. A small local append-only transaction ledger with operation identities: tests more than renamed integer counters without contacting real providers.
3. Key misuse or expiry under explicit contracts: tests the boundary of protected replay.

Defer concurrency, compensation, multi-agent races, and a large domain suite unless required by the central claim. They can turn this into several different papers. Include stale status only with a clearly specified consistency model; absence in stale status must not be treated as proof of non-commit.

**Done when:** the benchmark can distinguish controller behavior on meaningful, prospectively chosen cases, with either positive or null results. No paid runs without budget approval.

### 8. Replace misleading uncertainty with design-aware analysis

- Report deterministic results as exact finite-suite outcomes. Remove inferential Wilson intervals from repeated deterministic cells; duplicating identical cases does not strengthen empirical confidence.
- For model results, specify the sampling population, independent unit, within-scenario repetitions, and pairing. Use paired estimates and uncertainty methods appropriate to that hierarchy; do not pool all trace rows as independent draws.
- Prioritize effect sizes and confidence intervals over significance labels. Zero observed failures does not establish zero risk.
- Report operation attempts, status reads, model decisions, latency, and token usage separately. Keep weighted cost as an optional sensitivity analysis, not evidence that reconciliation inherently costs twice an operation.
- Show the primary non-idempotent failure strata separately from easy/read-only/no-failure controls.
- Generate a claims ledger linking every numerical statement to an artifact query and a regression assertion.

**Done when:** a reviewer can reproduce each result and understand what its uncertainty does and does not mean.

## Phase 4 — Rewrite around the strongest evidence

Suggested main-text structure:

1. **Introduction:** one concrete ambiguous-commit example, the evaluation gap, three bounded contributions.
2. **Problem and assumptions:** distinguish hidden state, observations, effects, and recovery capabilities.
3. **Benchmark:** oracle/controller boundary, scenarios, interventions, metrics.
4. **Validation and study design:** deterministic conformance checks separate from model experiments.
5. **Results:** primary model findings, mechanism/representation effects, cost and error analysis.
6. **Related work, limitations, and conclusion:** concise and directly tied to the actual claims.

Move exhaustive tool inventories, complete prompts, JSON schemas, detailed commands, and per-cell tables to appendices/artifact documentation. Consolidate repeated disclaimers without weakening them. Remove implementation-history language such as “corrected traces” from the main argument; preserve provenance in a changelog. Replace “responsible disclosure” with “responsible use” unless an actual disclosure occurred.

Add three publication figures:

- The same visible timeout arising from two different commit states.
- The audited controller/oracle boundary and information flow.
- Safety versus observed completion, with recovery-call components and model uncertainty where justified.

Build a venue-compliant PDF with working citations, readable vector figures, selectable text, author/anonymity metadata, and reproducible source. HTML alone is not the submission deliverable for most research venues.

**Done when:** the abstract accurately summarizes the strongest empirical finding, including a null result if that remains the finding, without leading with inflated deterministic sample size.

## Phase 5 — Release and independent review

- Add appropriate code and artifact licenses after confirming ownership; no top-level license was found in this review.
- Freeze a release commit and dependency/environment record. Record model/CLI versions, effective settings, prompt hashes, run timestamps, and artifact checksums.
- Separate three commands/workflows: offline analysis of archived results, deterministic regeneration, and optional fresh model evaluation. State that fresh model results need not be byte-identical.
- Add CI for tests, lint, claim assertions, offline analysis, and paper build. Keep credentials and paid model calls out of routine CI.
- Replay archived final model actions through the oracle and compare outcomes, without claiming this reproduces fresh inference.
- Ask a fresh-environment reproducer to build the paper and regenerate all reported tables without model access.
- Obtain one distributed-systems review and one agent-evaluation/statistics review. Resolve major objections in a response log.
- Archive the release at a durable repository with a persistent identifier where appropriate; check venue anonymity before publishing identifying materials.
- Complete venue checklist, ethics/data statement, AI-assistance disclosure where required, bibliography verification, and final PDF inspection.

**Done when:** no unresolved correctness or isolation issue remains, every claim has evidence, independent reproduction succeeds, and the submission satisfies venue rules.

## Sequence, effort, and decision gates

Indicative hands-on effort, excluding model queue time and reviewer turnaround:

1. **Claims and boundary audit:** 3–5 working days. Gate: trust the existing evidence or explicitly demote it to a pilot.
2. **Novelty and experiment design:** 2–4 days. Gate: choose narrow report/workshop path or approve expanded study and budget.
3. **Benchmark improvements and model study:** 1–3 weeks, scope dependent. Gate: freeze complete results, including nulls and failures.
4. **Analysis, rewrite, and figures:** 4–7 days.
5. **Independent reproduction and submission packaging:** 3–5 days plus external review.

For a narrow report/workshop path, skip the broad model expansion, not the accounting corrections, boundary qualification, statistical fixes, or independent reproduction. State that the contribution is an audited conformance harness with a scoped model pilot; venue suitability still depends on novelty review.

## Final submission gate

- [ ] Contribution is distinct from established idempotency engineering.
- [ ] Model isolation is demonstrated or historical evidence is explicitly qualified.
- [ ] Counts distinguish trajectories, model decisions, and deterministic repeats.
- [ ] Ablation claims match what was actually manipulated.
- [ ] No unsupported held-out generalization, protocol-necessity, or zero-risk claim remains.
- [ ] Protocol guarantees match tested execution behavior.
- [ ] Statistical analysis respects the experimental unit and paired design.
- [ ] Every headline number regenerates from frozen artifacts.
- [ ] Null findings, infrastructure failures, and limitations are retained.
- [ ] Independent scientific review and offline reproduction are complete.
- [ ] Licensed, versioned artifacts and a venue-compliant PDF are ready.
