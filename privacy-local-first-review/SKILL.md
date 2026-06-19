---
name: privacy-local-first-review
description: Use when reviewing or implementing changes that may affect telemetry, external network calls, credentials, secrets, local-first behavior, data storage, privacy promises, user data flow, auth, permissions, encryption, sync, or cloud dependencies.
---

# Privacy Local-First Review

Review changes through Henrik's usual privacy posture: local-first where possible, no unnecessary telemetry, no credential exposure, and explicit user control over external services.

## When To Use

Use this skill for:

- New external API calls, analytics, logging, telemetry, or crash reporting.
- Credential, token, OAuth, SMTP, provider, or secret handling.
- Sync, cloud, storage, export, deletion, retention, or audit behavior.
- Auth, authorization, roles, project permissions, E2EE, or data isolation.
- Local-first apps where a change may introduce a server dependency.

## Review Questions

| Area | Ask |
|---|---|
| Network | Is this external call necessary, documented, and gated when appropriate? |
| Telemetry | Does anything collect usage, crash, analytics, or identifying data? |
| Credentials | Are secrets kept out of code, logs, issue comments, commits, and containers? |
| Storage | Is user data stored in the expected local/cloud location only? |
| Access | Are auth and permission checks enforced server-side or at the correct boundary? |
| Encryption | Are encrypted fields, keys, and unlock flows preserved? |
| Lifecycle | Are export, deletion, retention, audit, and migration paths still valid? |
| Docs | Do privacy/security docs and user-facing promises need updates? |

## Flow

1. Read repo privacy, security, ADR, and data-isolation docs.
2. Identify new or changed data flows.
3. Trace data from input to storage, network, logs, UI, and deletion/export paths.
4. Check credential handling and logging.
5. Verify deny/error paths, not only happy paths.
6. Update docs or call out why no doc update is needed.

## Findings Format

Lead with findings:

```markdown
| Severity | Surface | Finding | Recommendation |
|---|---|---|---|
| High | API logs | Refresh token prefix is logged | Remove token-derived value from logs |
| Medium | Docs | New export path missing from privacy docs | Update `PRIVACY.md` |
```

If no issues are found, say that clearly and list residual risk or unverified paths.

## Rules

- Do not approve telemetry or external calls just because a dependency offers them by default.
- Prefer opt-in, configuration, and explicit documentation for networked behavior.
- Never include secrets or raw private user data in handoffs.
- Use `review-before-commit` as an additional pass before publishing security-sensitive changes.
