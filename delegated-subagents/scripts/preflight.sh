#!/usr/bin/env bash
set -euo pipefail

echo "== CLI availability =="
for cmd in python3 opencode devin cursor-agent git ps; do
  if command -v "$cmd" >/dev/null 2>&1; then
    printf "%-10s %s\n" "$cmd" "$(command -v "$cmd")"
  else
    printf "%-10s MISSING\n" "$cmd"
  fi
done

echo
echo "== Versions =="
opencode --version 2>/dev/null || true
devin --version 2>/dev/null || true
cursor-agent --version 2>/dev/null || true

echo
echo "== OpenCode models =="
if command -v opencode >/dev/null 2>&1; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  python3 "$SCRIPT_DIR/delegate.py" models --task scout --json
else
  echo "opencode is not installed"
fi

echo
echo "== Runtime =="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/delegate.py" --help >/dev/null
echo "delegate.py OK"
echo "state root: ${SUBAGENT_STATE_ROOT:-${HOME}/.codex/state/delegated-subagents/runs}"
