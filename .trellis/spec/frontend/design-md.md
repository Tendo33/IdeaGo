# DESIGN.md Workflow

Use this before UI or visual-system work in the Vite frontend.

## Current State

The `main` branch does not currently have a root `DESIGN.md`. Do not invent a
new visual direction while doing non-UI work. Existing UI code and screenshots in
`docs/assets/` are the current practical reference until a design source is
created.

## Source Priority

1. A future project root `DESIGN.md`
2. Existing UI implementation and product screenshots
3. This spec's frontend rules
4. A selected design-md reference from `awesome-design-md` or `getdesign.md`

## When A UI Task Changes Visual Direction

Before major visible UI work, choose or create a root `DESIGN.md` using a
relevant design-md starting point from:

- `https://github.com/VoltAgent/awesome-design-md`
- `https://getdesign.md`

For IdeaGo, prefer a product style that supports decision intelligence,
evidence scanning, progress feedback, and dense report reading. Do not blindly
copy a brand; adapt mood, spacing, typography, and interaction patterns to this
product.

## Implementation Rules

- Translate the visual direction into Tailwind v4 semantic tokens and reusable
  components.
- Preserve accessibility, responsiveness, visible focus states, and bilingual
  text fitting.
- Do not overwrite an existing `DESIGN.md` without explicit user approval.
- Mention which design source and viewports were checked for visible UI changes.
