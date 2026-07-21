# Codex-only skills

This directory is reserved for custom skills that depend on Codex-specific capabilities and cannot be expressed portably.

Portable skills stay in top-level repository folders and target `~/.agents/skills`. A Codex-only skill must be declared in `config/skills.yaml`, use `class: codex`, target only `codex`, and have a distinct declared name when a portable counterpart exists.

Codex-managed `.system` and plugin-cache skills do not belong here. The repository tooling may inventory those external capabilities in a later phase, but it must never copy or overwrite them.
