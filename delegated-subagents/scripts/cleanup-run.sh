#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_ROOT="${SUBAGENT_STATE_ROOT:-${HOME}/.codex/state/delegated-subagents/runs}"
args=(cleanup)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) args+=(--dry-run); shift ;;
    --state-root) STATE_ROOT="${2:?missing state root}"; shift 2 ;;
    --include-finished) shift ;;
    *) STATE_ROOT="$1"; shift ;;
  esac
done

exec python3 "$SKILL_DIR/scripts/delegate.py" "${args[@]}" --state-root "$STATE_ROOT"
