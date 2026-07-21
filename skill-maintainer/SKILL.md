---
name: skill-maintainer
description: Use when auditing, creating, updating, validating, installing, syncing, or documenting personal agent skill folders, SKILL.md frontmatter, skill README tables, imported skill bundles, OpenAI metadata, or Codex/Claude/OpenCode skill installs.
---

# Skill Maintainer

Maintain a personal skill repository as a portable source of truth. Separate custom skills from imported/vendor bundles, keep metadata valid, and sync installed copies intentionally.

## When To Use

Use this skill when:

- Adding or editing skills in a skill repository.
- Checking which skills are custom versus imported.
- Updating README skill tables or install docs.
- Syncing skills into `~/.codex/skills`, `~/.claude/skills`, or OpenCode paths.
- Validating `SKILL.md` frontmatter and `agents/openai.yaml`.
- Preparing a skill set for reuse across tools.

## Repository Shape

Prefer this shape for custom skills:

```text
skill-name/
  SKILL.md
  agents/
    openai.yaml
```

Use additional `scripts/`, `references/`, or `assets/` only when repeated work or heavy reference material justifies it.

## Maintenance Flow

1. List skill folders and distinguish top-level custom skills from imported bundles.
2. Read each custom `SKILL.md` frontmatter.
3. Check required files: `SKILL.md`, optional `agents/openai.yaml`, README entry.
4. Validate names use lowercase hyphenated identifiers.
5. Keep descriptions trigger-focused, preferably under 500 characters.
6. Update README tables when skills are added, renamed, or removed.
7. Sync installed copies only after the source repo is correct.
8. Report validation gaps and install state.

## Classification Cues

| Cue | Likely classification |
|---|---|
| Top-level folder with local `agents/openai.yaml` | Custom personal skill |
| Nested under an imported or vendor bundle folder | Imported/vendor skill |
| Contains vendor `LICENSE.txt` and brand references | Imported/vendor skill |
| Missing README entry | Custom skill needing documentation |

## Validation

Check at minimum:

- Frontmatter has `name` and `description`.
- Name matches folder name.
- Description says when to use the skill, not a long workflow summary.
- Markdown has a clear title and practical instructions.
- README entry matches the skill's actual purpose.
- Installed copy matches source when sync was requested.

If the official validator is unavailable due to missing dependencies, run a lightweight frontmatter parse and say so.

## Output Shape

Use a table:

```markdown
| Skill | Status | Action |
|---|---|---|
| `summary-tables` | Valid, installed | No action |
| `summary-router` | Missing README entry | Add row |
```

End with `Verified:` including checks run and anything skipped.
