#!/usr/bin/env bash
set -euo pipefail

TASK_TYPE="scout"
HINT="${SUBAGENT_MODEL_HINT:-}"
POLICY="${SUBAGENT_POLICY:-default}"
PRINT_ALL=0
EMITTED_MODELS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task) TASK_TYPE="${2:?missing task type}"; shift 2 ;;
    --hint) HINT="${2:?missing model hint}"; shift 2 ;;
    --policy) POLICY="${2:?missing policy}"; shift 2 ;;
    --all) PRINT_ALL=1; shift ;;
    -h|--help)
      cat <<'USAGE'
Usage: resolve-model.sh [--task scout|bulk|code-small|debug|review|closure-validation] [--hint provider/model] [--policy default|only-free|free-first|allow-limited|airouter|mistral] [--all]
USAGE
      exit 0
      ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if ! command -v opencode >/dev/null 2>&1; then
  echo "opencode is not installed" >&2
  exit 127
fi

MODELS="$(opencode models)"

has_model() {
  printf '%s\n' "$MODELS" | grep -Fxq "$1"
}

emit_model() {
  local model="$1"
  if printf '%s\n' "$EMITTED_MODELS" | grep -Fxq "$model"; then
    return 1
  fi
  printf '%s\n' "$model"
  EMITTED_MODELS="${EMITTED_MODELS}${EMITTED_MODELS:+
}${model}"
  return 0
}

print_available() {
  local emitted=0
  for model in "$@"; do
    if has_model "$model" && emit_model "$model"; then
      emitted=1
      [[ "$PRINT_ALL" -eq 0 ]] && return 0
    fi
  done
  [[ "$emitted" -eq 1 ]]
}

free_chain=(
  "opencode/deepseek-v4-flash-free"
  "opencode/north-mini-code-free"
  "opencode/mimo-v2.5-free"
  "opencode/nemotron-3-ultra-free"
  "opencode/hy3-free"
)

airouter_chain=(
  "airouter/DeepSeek-V4-Flash"
  "airouter/Qwen3.6"
)

mistral_chain=(
  "mistral/mistral-medium-latest"
  "mistral/codestral-latest"
)

case "$TASK_TYPE" in
  scout)
    default_chain=("${free_chain[@]}" "${airouter_chain[@]}")
    limited_chain=("opencode-go/deepseek-v4-flash" "opencode-go/qwen3.6-plus")
    ;;
  bulk)
    default_chain=("opencode/deepseek-v4-flash-free" "opencode/mimo-v2.5-free" "${airouter_chain[@]}")
    limited_chain=("opencode-go/deepseek-v4-flash")
    ;;
  code-small)
    default_chain=("opencode/north-mini-code-free" "airouter/Qwen3.6" "airouter/DeepSeek-V4-Flash")
    limited_chain=("opencode-go/kimi-k2.7-code" "opencode-go/qwen3.7-plus" "opencode-go/deepseek-v4-flash")
    ;;
  debug)
    default_chain=("opencode/north-mini-code-free" "airouter/Qwen3.6" "opencode/deepseek-v4-flash-free")
    limited_chain=("opencode-go/qwen3.7-plus" "opencode-go/deepseek-v4-pro" "opencode-go/kimi-k2.7-code")
    ;;
  review)
    default_chain=("opencode/nemotron-3-ultra-free" "airouter/Qwen3.6" "airouter/DeepSeek-V4-Flash")
    limited_chain=("opencode-go/qwen3.7-max" "opencode-go/qwen3.7-plus")
    ;;
  closure-validation)
    default_chain=("opencode/nemotron-3-ultra-free" "airouter/Qwen3.6" "airouter/DeepSeek-V4-Flash")
    limited_chain=("opencode-go/qwen3.7-max" "opencode-go/qwen3.7-plus" "opencode-go/deepseek-v4-pro")
    ;;
  *)
    echo "unknown task type: $TASK_TYPE" >&2
    exit 2
    ;;
esac

if [[ -n "$HINT" ]]; then
  case "$HINT" in
    */*)
      if has_model "$HINT"; then
        emit_model "$HINT" || true
        [[ "$PRINT_ALL" -eq 0 ]] && exit 0
      else
        echo "hinted model is not visible to opencode: $HINT" >&2
      fi
      ;;
    *free*|*Free*)
      POLICY="only-free"
      ;;
    *airouter*|*aiRouter*)
      POLICY="airouter"
      ;;
    *mistral*|*Mistral*)
      POLICY="mistral"
      ;;
    *opencodego*|*OpenCodeGo*|*opencode-go*)
      POLICY="allow-limited"
      ;;
  esac
fi

case "$POLICY" in
  only-free)
    print_available "${free_chain[@]}"
    ;;
  free-first)
    print_available "${free_chain[@]}" "${default_chain[@]}"
    ;;
  airouter)
    print_available "${airouter_chain[@]}" "${default_chain[@]}"
    ;;
  mistral)
    print_available "${mistral_chain[@]}" "${default_chain[@]}"
    ;;
  allow-limited)
    print_available "${default_chain[@]}" "${limited_chain[@]}"
    ;;
  default)
    print_available "${default_chain[@]}"
    ;;
  *)
    echo "unknown policy: $POLICY" >&2
    exit 2
    ;;
esac
