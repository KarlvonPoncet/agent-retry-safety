#!/bin/sh
# Text-only model adapter: retain only Codex's schema-constrained final answer.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
out=$(mktemp)
err=$(mktemp)
trap 'rm -f "$out" "$err"' EXIT
set -- codex exec --ephemeral --sandbox read-only --skip-git-repo-check
model=${RETRY_SAFETY_CODEX_MODEL:-${PI_MODEL:-}}
if [ -n "$model" ]; then
  set -- "$@" -m "$model"
fi
set -- "$@" --output-schema "$root/paper/action_schema.json" -o "$out" -
"$@" >/dev/null 2>"$err"
cat "$out"
