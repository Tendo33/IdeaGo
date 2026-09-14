# IdeaGo Design System

Use this document as the visual contract for the hosted product. Values come from the shipped UI in `frontend/src/styles/globals.css` and `frontend/src/components/ui`. Do not invent a second identity.

## Product and direction

- Product: IdeaGo, a hosted idea-validation workspace that turns one sentence into a decision-first research report.
- Audience: founders and builders deciding whether to pursue an idea.
- Primary task: submit an idea, watch six-source research, read a go / caution / no-go report.
- Visual direction: neo-brutalist utility. Hard borders, zero radius, offset shadows, electric blue on tinted paper.
- Tone: direct, evidence-first, slightly loud. Not playful, not enterprise-soft.
- Memorable idea: a research instrument that looks like a stamped brief, not a glowing AI dashboard.

Landing is Persuade. Login, home, report, history, profile, and admin are Operate. Legal pages are Read. Brand details stay precise on Operate surfaces; landing may be bolder without adding decoration for its own sake.

## Colors

Mapped from `:root` / `.dark` OKLCH tokens.

- Background: `oklch(0.99 0.01 100)` light / `oklch(0.15 0.005 260)` dark
- Surface: `--card` tinted off-white / charcoal
- Surface elevated: same card token plus hard offset shadow
- Text primary: `--foreground` near-black / off-white
- Text secondary: `--muted-foreground`
- Border: `--border` near-black in light, off-white in dark
- Brand accent: `--primary` electric blue `oklch(0.6 0.2 260)` (brighter in dark)
- Success / warning / danger: `--success`, `--warning`, `--destructive`
- Usage rules:
  - Use semantic tokens (`bg-background`, `text-primary`, `border-border`). Do not add raw Tailwind palette colors.
  - Google / GitHub / LinuxDo brand fills are allowed only on those provider marks.
  - Do not use cyan-to-purple gradients, gradient text, or glow.

## Typography

- Display font: Archivo Black (`--font-heading`), single weight 400, uppercase, tracking `-0.04em`
- Body font: DM Sans (`--font-sans`) 400–900
- Mono font: JetBrains Mono, for data and code only
- Heading scale: `h1` `clamp(2.5rem, 6vw, 5rem)`; `h2` `clamp(2rem, 4vw, 3.5rem)`; `h3` `clamp(1.5rem, 3vw, 2.5rem)`
- Body size: 1rem, line-height ~1.5; Operate helper text may go to 0.875rem
- Label and metadata: uppercase, wide tracking, `font-bold` / `font-black`

## Spacing, radius, and elevation

- Base spacing unit: `0.25rem`
- Content max width: `.app-shell` = `max-w-7xl` with `px-4 sm:px-6 md:px-8`
- Common gaps: 8 / 16 / 24 / 32 / 48. Tight groups, generous section breaks.
- Control height: 44px minimum. Large CTAs 56px.
- Radius scale: **0**. No rounded cards, no pills except tiny status dots.
- Shadow / border treatment: 2px or 4px `border-border` plus hard offset shadows (`1px 1px 0` through `18px 18px 0`). Hover pushes the element into the shadow. Never a zero-offset colored halo.

## Components

- Buttons: `frontend/src/components/ui/Button.tsx`. Variants `primary | secondary | destructive | warning | outline | ghost`. Compose loading with `Loader2` + `disabled`.
- Inputs and forms: `.input` class, 2px border, no radius. Labels are uppercase and visible.
- Cards and surfaces: `.card` / `.surface-card` — full border, offset shadow, no nested cards.
- Navigation: fixed 4px bottom-border bar. Icon-only compact controls must keep an `aria-label`.
- Tables and dense data: report compare panel. Tabular layout on desktop, stacked rows on mobile.
- Empty, loading, and error states: empty states name the missing work and offer the next action. Loading uses Skeleton or a labeled spinner. Errors name the problem and the recovery.
- Focus and disabled states: `focus-visible` ring using `--primary`. Disabled opacity 50%, no hover translation.

Reuse the existing primitives. Do not install shadcn or a second component system unless the task explicitly replaces this one.

## Motion and responsive behavior

- Motion intensity: low on Operate, medium on landing.
- Main transition language: 150–300ms `ease-brutal` (`cubic-bezier(0.22, 1, 0.36, 1)`) on transform and shadow. Pressed states translate into the offset shadow.
- Reduced-motion behavior: landing has `full | light | none`. Do not add a second motion language. Preserve state-change feedback even when motion is reduced.
- Mobile layout changes: keep primary actions. Do not hide Sign In, History, or submit behind unlabeled icons. 390px must not horizontal-scroll.
- Breakpoints: Tailwind defaults. Touch targets stay ≥44px at every width.

## Do and do not

- Do: keep zero radius, hard shadows, Archivo Black headings, electric blue as the only accent.
- Do: write product-specific copy. Name sources, quotas, and decisions.
- Do not: side-tab accents (`border-l-4` / `border-l-8` color bars), decorative blobs, grid overlays, infinite spin rings, glassmorphism, gradient text.
- Do not: wrap every block in a card, or use identical icon-card grids as page structure.
- Do not: invent a new visual language per page.
- Avoid unless product-specific: provider brand colors, charts, the tilted sample-report mock on landing.

## Implementation mapping

- Component foundation: `frontend/src/components/ui/{Button,Dialog,Alert,Badge,Skeleton}.tsx`
- Token file / CSS variables: `frontend/src/styles/globals.css`
- Icon set: `lucide-react`, plus authored SVGs for GitHub, Google, LinuxDo, and Hacker News
- Approved reference components: existing Button / Dialog / Alert / landing mock card. No third-party marketing kits.
