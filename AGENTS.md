# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Core API and state-machine behavior: `src/retry_safety/`.
- Agent benchmark, opaque controller boundary, and protocol schema: `src/retry_safety/agent_benchmark.py`; reproducible research commands and artifacts: `README.md` and `paper/`.
- Install and run the fast validation suite with `.venv/bin/python -m pytest`; CLI examples and UI boundary: `README.md`.
- Keep UI-owned `app.py` and `src/retry_safety_dashboard/` outside this lane.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
