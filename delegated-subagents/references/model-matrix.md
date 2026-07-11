# Delegated Subagent Model Matrix

Revise this file frequently. Free model names and provider availability drift.
Refresh the live machine-readable snapshot and review measured outcomes with:

```bash
scripts/refresh-models.sh --json
scripts/model-scorecard.sh --json
```

## User Hints

Honor explicit hints before default routing:

| Hint | Meaning |
|---|---|
| `only free OpenCode` | Use only `opencode/*-free` free models. |
| `use aiRouter` | Prefer `airouter/*` models. |
| `use Mistral Medium` | Prefer `mistral/mistral-medium-latest`. |
| `allow OpenCodeGo` | Permit `opencode-go/*` fallback models. |
| `do not use Devin` | Do not spawn Devin. |
| explicit `provider/model` | Use that model first if visible. |

## Cost Buckets

| Bucket | Cost policy | Default use |
|---|---|---|
| OpenCode free | Free; use at will | Scouting, inventory, docs, simple investigation. |
| aiRouter | Account-dependent; verify allowance | General fallback and broad delegated work. |
| Mistral Medium | Account-dependent; verify allowance | Stronger coding, debugging, review. |
| Devin/SWE 1.7 | Account-dependent; verify allowance | Longer autonomous bounded work. |
| OpenCodeGo | Subscription-limited | Use when allowed or when free/aiRouter/Mistral/Devin are insufficient. |
| GPT/Codex main | Scarce | Coordination, final review, verification, PR/release decisions. |

## Current Free OpenCode Models

Observed from the UI and `opencode models` on 2026-07-11:

| Model | Notes |
|---|---|
| `opencode/deepseek-v4-flash-free` | Good first scout and broad fallback. |
| `opencode/hy3-free` | Cheap scout fallback. |
| `opencode/mimo-v2.5-free` | Cheap scout and summary fallback. |
| `opencode/nemotron-3-ultra-free` | Cheap broad reasoning fallback. |
| `opencode/north-mini-code-free` | Cheap code-oriented scout fallback. |

## Default Chains

Use the first currently visible model in the chain, skip missing models, and
never emit the same model twice. Prefer a later model when the scorecard has
enough comparable runs to show materially better acceptance for that task type.

| Task type | Default fallback chain |
|---|---|
| `scout` | `opencode/deepseek-v4-flash-free` -> `opencode/north-mini-code-free` -> `opencode/mimo-v2.5-free` -> `airouter/DeepSeek-V4-Flash` -> `airouter/Qwen3.6` |
| `bulk` | `opencode/deepseek-v4-flash-free` -> `opencode/mimo-v2.5-free` -> `airouter/DeepSeek-V4-Flash` |
| `code-small` | `mistral/mistral-medium-latest` -> `mistral/codestral-latest` -> `airouter/Qwen3.6` -> `airouter/DeepSeek-V4-Flash` -> `opencode/north-mini-code-free` |
| `debug` | `mistral/mistral-medium-latest` -> `mistral/codestral-latest` -> `airouter/Qwen3.6` -> `opencode/deepseek-v4-flash-free` |
| `review` | `mistral/mistral-medium-latest` -> `airouter/Qwen3.6` -> `airouter/DeepSeek-V4-Flash` -> `opencode/nemotron-3-ultra-free` |
| `closure-validation` | `mistral/mistral-medium-latest` -> `airouter/Qwen3.6` -> `mistral/codestral-latest` -> `airouter/DeepSeek-V4-Flash` -> `opencode/nemotron-3-ultra-free` |
| `local` | `omlx/Qwen3-Coder-30B-A3B-Instruct-MLX-4bit` -> `omlx/Devstral-Small-2-24B-Instruct-2512-4bit` -> `omlx/DeepSeek-Coder-V2-Lite-Instruct-4bit-mlx` |

## Optional OpenCodeGo Chains

Only use when the user explicitly allows OpenCodeGo or when `SUBAGENT_POLICY=allow-limited`.

| Task type | OpenCodeGo fallback chain |
|---|---|
| `code-small` | `opencode-go/kimi-k2.7-code` -> `opencode-go/qwen3.7-plus` -> `opencode-go/deepseek-v4-flash` |
| `debug` | `opencode-go/qwen3.7-plus` -> `opencode-go/deepseek-v4-pro` -> `opencode-go/kimi-k2.7-code` |
| `review` | `opencode-go/qwen3.7-max` -> `opencode-go/qwen3.7-plus` |
| `closure-validation` | `opencode-go/qwen3.7-max` -> `opencode-go/qwen3.7-plus` -> `opencode-go/deepseek-v4-pro` |

## Devin/SWE 1.7

Use Devin/SWE 1.7 for `long-autonomous` work only when the account policy allows it, the task has clear acceptance criteria, and it is safe to run autonomously. Still keep the main Codex thread as coordinator and final reviewer.

Suggested Devin model policy:

| Policy | Model |
|---|---|
| default | `swe-1.7`; always announce the explicit model. |
| SWE work | `swe-1.7` when available through Devin CLI/config. |
| codex requested | `codex` |
| stronger reasoning requested | `opus` or explicit user-provided Devin model |

Use the runtime's `read-only` profile for investigation and `edit` for a bounded
manifest. The runtime maps these to Devin `auto` and `accept-edits`, runs Devin
with `--sandbox`, and keeps all user interaction in the main Codex task.
