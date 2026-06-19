---
name: needs-analysis
description: Use when a request is early, vague, exploratory, or potentially larger than it sounds, especially when the user asks for analysis, discovery, scoping, feasibility, problem framing, risks, unknowns, user needs, goals, constraints, or what should be built first.
---

# Needs Analysis

Clarify the actual need before turning it into requirements, design, or code. The goal is to avoid building from the first phrasing when the real problem, user, constraint, or success condition is still soft.

## When To Use

Use this skill when:

- The user describes an idea, pain point, product direction, bug theme, or unclear request.
- The request may hide multiple projects or phases.
- The user asks "what should we do?", "is this worth it?", "what am I missing?", or "help me think this through".
- Implementation would require guessing intent, audience, priority, security posture, data behavior, or user-visible semantics.

Do not over-gate tiny mechanical edits. For a clear one-file task, proceed normally.

## Workflow

1. Inspect available context: request text, repo docs, existing issues, screenshots, errors, and prior decisions.
2. Identify the user or stakeholder, the current pain, and the desired outcome.
3. Separate symptoms from underlying needs.
4. Name constraints: time, compatibility, privacy, data, UX, release, operational, and support constraints.
5. Surface unknowns that would change the solution.
6. Propose a smallest useful next step.

Ask at most one clarifying question when the answer materially changes scope. If a reasonable assumption is safe, state it and continue.

## Output Shape

Use a compact readout:

```markdown
Bottom line: [one sentence with the real need and recommended next step].

Needs analysis

| Area | Read | Implication |
|---|---|---|
| User/problem | Who is affected and what hurts | What outcome matters |
| Current state | Evidence from repo, issue, screenshot, or request | What must stay true |
| Constraints | Time, release, security, data, UX, platform | How this narrows options |
| Unknowns | Decisions or missing facts | Whether to ask, assume, or defer |
| First slice | Smallest valuable step | Why this should come first |
```

End with `Next:` and route to `requirements-spec`, `solution-design`, or direct implementation if enough is known.

## Analysis Prompts

Use these questions internally:

- Who experiences the problem, and what would they notice when it is solved?
- Is the request asking for an outcome, a feature, a tool, a fix, or a process?
- What is explicitly out of scope?
- What risks become expensive if discovered late?
- What could be delivered as a thin first slice without closing future options?

## Rules

- Preserve the user's original wording when it contains useful intent.
- Do not turn analysis into a full implementation plan unless the user asks for a plan.
- Mark assumptions clearly.
- If `summary-tables` is available, use it for the final readout.
- If the next step is a formal requirement set, use `requirements-spec`.
