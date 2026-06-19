---
name: design-system-guard
description: Use when reviewing or implementing UI changes that may affect design tokens, hardcoded colors, theme variables, i18n strings, component consistency, responsive behavior, accessibility, visual polish, or existing design-system conventions.
---

# Design System Guard

Keep UI work consistent with the repo's existing design system instead of drifting into one-off styling. The goal is a polished interface that respects tokens, components, layout density, accessibility, and localization rules.

## When To Use

Use this skill for:

- Frontend UI changes, visual polish, or design reviews.
- New components, controls, cards, navigation, dashboards, modals, forms, or settings surfaces.
- Hardcoded colors, theme tokens, dark/light mode, or accent behavior.
- User-visible strings and i18n.
- Responsive/mobile layout checks.
- Comparing implementation to screenshots or design references.

## Review Matrix

| Surface | Check |
|---|---|
| Tokens | Colors, borders, shadows, typography, spacing use repo variables/tokens |
| Components | Existing components/classes are reused before adding variants |
| States | Loading, empty, error, disabled, focus, hover, selected, and destructive states exist |
| Responsiveness | Text and controls fit on mobile and desktop without overlap |
| Accessibility | Semantics, labels, focus rings, contrast, keyboard behavior |
| i18n | User-visible strings use the repo localization system when one exists |
| Visual fit | Density, chrome, icons, cards, and tone match the product |
| Regression risk | Adjacent routes/components using shared styles still work |

## Flow

1. Read the repo design-system docs and relevant components.
2. Inspect the existing local pattern before inventing a new one.
3. For code changes, scan for hardcoded colors, one-off spacing, strings, and duplicated component logic.
4. Verify actual rendered surfaces when practical.
5. For UI text, update all required locale files together.
6. Report remaining manual visual QA if screenshots/browser/simulator were unavailable.

## Common Fixes

- Replace literal colors with CSS variables, theme tokens, or Swift/React Native theme values.
- Reuse existing button/input/card/list classes before creating new ones.
- Use concise user-facing copy; keep implementation detail out of UI.
- Keep destructive actions visually distinct but consistent with repo conventions.
- Prefer established icons and controls over text-heavy custom UI.

## Output Shape

```markdown
| Surface | Status | Evidence |
|---|---|---|
| Theme tokens | Fixed | Replaced `#2563eb` with `var(--accent)` |
| i18n | Missing | New settings labels need `nb` and `en` keys |
| Mobile layout | Unverified | Simulator unavailable in this session |
```

End with `Verified:` naming rendered checks, tests, screenshots, or skipped checks.
