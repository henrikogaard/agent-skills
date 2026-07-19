# Delegated Subagent Model Matrix

This is a task-fit policy, not a static availability list. Before every
OpenCode routing decision run:

```bash
scripts/refresh-models.sh --task <task> --json
```

The command calls `opencode models`, discovers every identifier matching
`^opencode/.*free` case-insensitively, and evaluates current local outcomes.

## Cost Sources

| Route | Cost source | Default role |
|---|---|---|
| Devin `swe-1.7` | Free for this installation | Bounded implementation and repair after smoke success |
| `opencode/*free*` | Free, verified from live model identifier | Scout and independent pre-review when task-fit |
| `airouter/*` | Free for this installation | Scout/reviewer fallback |
| Cursor Composer | Cursor subscription | Reliable implementation, debugging, repair, coordination |
| Mistral | Mistral subscription | Independent strong fallback or explicit request |
| Main/native Codex | OpenAI subscription | Scope, full final review, integration, decisions |

## Task Routing

| Task | Primary | Polish/reviewer | Fallback |
|---|---|---|---|
| `scout`, `bulk` | Best live usable free OpenCode model | Another free model only for conflicting evidence | `airouter/Qwen3.6` |
| Mechanical edit | SWE 1.7 | Live usable free reviewer | Composer 2.5 Fast |
| `code-small` | SWE 1.7 after smoke success | Composer Fast or independent usable free reviewer | Composer 2.5 |
| `debug` | Composer 2.5 | SWE 1.7 or Mistral Medium | Mistral Medium |
| Approved complex slice | Composer 2.5 | Different-family SWE or Mistral review | Return to Codex |
| `review` | Different family from implementer; prefer usable free, SWE, or Composer Fast | Not applicable | Mistral Medium |
| `closure-validation` | Live usable free review/general model | Deterministic checklist | aiRouter Qwen |
| Decomposable epic | Composer coordinates bounded free/SWE slices | Independent review per slice | Mistral only when requested |

## Free Model Usability

The runtime recognizes these current task-fit patterns but still requires live
visibility:

| Model pattern | Established tasks |
|---|---|
| `north-mini-code-free` | `code-small`, `debug`, `review` |
| `deepseek-v4-flash-free` | `scout`, `bulk`, `review`, `closure-validation` |
| `nemotron-3-ultra-free` | `scout`, `review`, `closure-validation` |
| `mimo-v2.5-free` | `scout`, `bulk`, `review`, `closure-validation` |
| `hy3-free` | `scout`, `bulk`, `review` |

Classification rules:

- `usable`: live and established for the requested task, without repeated hard
  failure evidence.
- `probe-only`: new/unknown or not established for this task. It may run a
  bounded read-only probe and can be explicitly requested.
- `excluded`: three recent comparable hard failures with no success. Re-enable
  only after a deliberate smoke probe succeeds.

Do not equate malformed-report failures with poor code quality when diagnosing
a route. Record provider failure, report failure, policy failure, and incorrect
patch separately.

## Explicit Requests

Explicit safe model requests override defaults and remain first in the chain:

| Request | Route |
|---|---|
| `launch subagents with SWE 1.7` | `spawn-devin.sh --model swe-1.7` |
| `use Composer` | `spawn-cursor.sh --model composer-2.5` |
| `use Composer Fast` | `spawn-cursor.sh --model composer-2.5-fast` |
| `only free OpenCode` | `spawn-opencode.sh --policy only-free` |
| explicit `airouter/...` | OpenCode wrapper with that exact model |
| explicit `mistral/...` | OpenCode wrapper with that exact model |

Never use OpenCodeGo without explicit permission. Never use local `omlx/*`
models for delegated work. An explicit model changes routing, not the mandatory
external polish and Codex final-review gates.
