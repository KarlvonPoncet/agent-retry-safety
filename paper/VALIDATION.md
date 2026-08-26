# Validation evidence

Recorded 2026-08-26 in the task worktree.

```text
.venv/bin/python -m pytest --cov=retry_safety --cov-report=term-missing
47 passed, 1 skipped
TOTAL coverage: 92%

.venv/bin/ruff check .
All checks passed!

make -C paper
(make reports the target is up to date after `python3 scripts/build_paper.py`)

sha256sum -c paper/artifacts/SHA256SUMS
12 artifact files: OK
```

Artifact generation commands and the model-facility boundary are documented in
`README.md` and `paper/paper.md`. The credential-free deterministic artifacts
contain 360 core rows and 11,520 agent rows. The authenticated single-facility
matrix contains 432 model rows; its final schema-constrained outputs are in
`paper/artifacts/llm_matrix_traces.jsonl`; corrected same-key replays use the
exact original key and contain no placeholder key. No private reasoning is stored.
