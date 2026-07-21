# Contributing

This repository publishes skills authored and maintained by Henrik. It is intentionally a first-party catalog, not a mirror or package collection for third-party skills.

## Accepted changes

- Fixes and improvements to an existing Henrik-authored skill.
- New Henrik-authored skills approved for public distribution.
- Validator, test, metadata, documentation, and packaging improvements.

Do not add copied, imported, mirrored, or vendored third-party skills. Third-party skills used in Henrik's device baseline are reviewed and pinned privately in `agent-baseline/vendor/`.

## Skill contract

Every skill must:

- Have a lowercase hyphenated directory and matching `SKILL.md` frontmatter name.
- Be declared in `config/skills.yaml` with `ownership: first-party` and `publication: public`.
- Target `agents` when portable or `codex` when genuinely Codex-specific.
- Avoid personal filesystem paths, private endpoints, credentials, customer data, and machine-specific assumptions.
- Include valid `agents/openai.yaml` metadata.

Run before opening a pull request:

```bash
gitleaks git . --staged --redact --no-banner
gitleaks git . --redact --no-banner
ruby scripts/skills validate
ruby tests/test_skills_cli.rb
```

Never commit `.env` files, API keys, access or refresh tokens, private keys,
credentials, real telemetry exports, internal hosting metadata, or secret-bearing
fixtures. Use obviously synthetic placeholders in tests. If a real credential
is ever committed, revoke or rotate it first; deleting the file in a later
commit is not sufficient because Git history retains it.

Keep changes focused. Do not include generated installation output or edits from `~/.agents/skills` or `~/.codex/skills`.
