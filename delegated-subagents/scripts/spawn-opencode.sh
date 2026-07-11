#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_TYPE="${SUBAGENT_TASK_TYPE:-scout}"
PROMPT_FILE=""
MANIFEST=""
WORKDIR="${PWD}"
MODEL_HINT="${SUBAGENT_MODEL_HINT:-}"
MODELS=""
PRESERVE_FIRST=0
[[ -n "$MODEL_HINT" ]] && PRESERVE_FIRST=1
POLICY="${SUBAGENT_POLICY:-default}"
STATE_ROOT="${SUBAGENT_STATE_ROOT:-${HOME}/.codex/state/delegated-subagents/runs}"
TIMEOUT_SECONDS="${SUBAGENT_TIMEOUT_SECONDS:-1800}"
IDLE_SECONDS="${SUBAGENT_IDLE_SECONDS:-300}"
MAX_ATTEMPTS="${SUBAGENT_MAX_ATTEMPTS:-3}"
MAX_RSS_MB="${SUBAGENT_MAX_RSS_MB:-4096}"
PERMISSION_PROFILE="${SUBAGENT_PERMISSION_PROFILE:-read-only}"
ISOLATION="${SUBAGENT_ISOLATION:-managed}"
WORKTREE_ROOT="${SUBAGENT_WORKTREE_ROOT:-${HOME}/.codex/worktrees/delegated-subagents}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task) TASK_TYPE="${2:?missing task type}"; shift 2 ;;
    --prompt-file) PROMPT_FILE="${2:?missing prompt file}"; shift 2 ;;
    --manifest) MANIFEST="${2:?missing manifest}"; shift 2 ;;
    --workdir) WORKDIR="${2:?missing workdir}"; shift 2 ;;
    --hint) MODEL_HINT="${2:?missing model hint}"; PRESERVE_FIRST=1; shift 2 ;;
    --models) MODELS="${2:?missing model chain}"; PRESERVE_FIRST=1; shift 2 ;;
    --policy) POLICY="${2:?missing policy}"; shift 2 ;;
    --run-dir|--state-root) STATE_ROOT="${2:?missing state root}"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="${2:?missing timeout}"; shift 2 ;;
    --idle) IDLE_SECONDS="${2:?missing idle seconds}"; shift 2 ;;
    --max-attempts) MAX_ATTEMPTS="${2:?missing attempts}"; shift 2 ;;
    --max-rss-mb) MAX_RSS_MB="${2:?missing RSS limit}"; shift 2 ;;
    --permission-profile) PERMISSION_PROFILE="${2:?missing permission profile}"; shift 2 ;;
    --isolation) ISOLATION="${2:?missing isolation mode}"; shift 2 ;;
    --worktree-root) WORKTREE_ROOT="${2:?missing worktree root}"; shift 2 ;;
    -h|--help)
      cat <<'USAGE'
Usage: spawn-opencode.sh --prompt-file file [--manifest file] [--task scout] [--workdir repo]
       [--hint provider/model] [--models comma,separated,chain]
       [--policy default|only-free|free-first|allow-limited|airouter|mistral]
       [--permission-profile read-only|edit] [--isolation managed|none]

The subagent is non-interactive. Codex owns approvals, status, review, and acceptance.
USAGE
      exit 0
      ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$PROMPT_FILE" || ! -f "$PROMPT_FILE" ]]; then
  echo "--prompt-file is required" >&2
  exit 2
fi

if [[ -z "$MODELS" ]]; then
  resolver_args=(--task "$TASK_TYPE" --policy "$POLICY" --all)
  [[ -n "$MODEL_HINT" ]] && resolver_args+=(--hint "$MODEL_HINT")
  model_lines="$($SKILL_DIR/scripts/resolve-model.sh "${resolver_args[@]}")"
  MODELS="$(printf '%s\n' "$model_lines" | paste -sd, -)"
fi

args=(
  run --tool opencode --task "$TASK_TYPE" --prompt-file "$PROMPT_FILE"
  --workdir "$WORKDIR" --models "$MODELS" --state-root "$STATE_ROOT"
  --timeout "$TIMEOUT_SECONDS" --idle "$IDLE_SECONDS" --max-attempts "$MAX_ATTEMPTS"
  --max-rss-mb "$MAX_RSS_MB" --permission-profile "$PERMISSION_PROFILE"
  --isolation "$ISOLATION" --worktree-root "$WORKTREE_ROOT"
)
[[ -n "$MANIFEST" ]] && args+=(--manifest "$MANIFEST")
[[ "$PRESERVE_FIRST" -eq 1 ]] && args+=(--preserve-first)

exec python3 "$SKILL_DIR/scripts/delegate.py" "${args[@]}"
