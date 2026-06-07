# Design Document

## Overview

This design defines the technical approach for unifying dark/light mode theming across all JusAds frontend pages and restructuring the codebase for clarity. The solution centers on: (1) expanding the existing CSS custom property system in `index.css` to cover all surface/text/border/accent variations for both themes, (2) replacing inline hardcoded colors with semantic Tailwind token classes, (3) extracting shared layout primitives into reusable components, and (4) splitting large page files into focused sub-components.

## Architecture

### Theme Token System (index.css)

The existing `:root` and `.dark` selectors in `index.css` already define core tokens (background, foreground, card, primary, etc.). This design extends them with additional semantic surface and accent tokens used throughout the dashboard:

**New tokens to add:**

```
:root {
  --surface-panel: #fafafa;          /* Left/right panel backgrounds */
  --surface-card: #ffffff;           /* Card/container backgrounds */
  --surface-elevated: #ffffff;       /* Elevated cards with shadow */
  --surface-inset: #f3f3f4;         /* Inset/recessed areas */
  --text-heading: #111111;          /* Page titles, card titles */
  --text-body: #4d4d4d;             /* Body text, descriptions */
  --text-caption: #666666;          /* Captions, timestamps, labels */
  --border-default: #e5e5e5;        /* Standard borders */
  --border-subtle: #f0f0f0;         /* Dividers, inner borders */
  --accent-blue: #0080FF;           /* Primary accent */
  --accent-pink: #FF1493;           /* Secondary accent */
  --accent-emerald: #10b981;        /* Success states */
  --accent-amber: #f59e0b;          /* Warning states */
  --accent-error: #ef4444;          /* Error states */
  --input-bg: #f9fafb;             /* Input backgrounds */
  --input-border: #e5e7eb;         /* Input borders */
  --input-focus: #0080FF;          /* Input focus ring */
}

.dark {
  --surface-panel: #111116;
  --surface-card: #111116;
  --surface-elevated: #181822;
  --surface-inset: rgba(0, 0, 0, 0.2);
  --text-heading: #ffffff;
  --text-body: #a1a1aa;
  --text-caption: #71717a;
  --border-default: rgba(255, 255, 255, 0.1);
  --border-subtle: rgba(255, 255, 255, 0.05);
  --accent-blue: #4DA6FF;
  --accent-pink: #FF69B4;
  --accent-emerald: #34d399;
  --accent-amber: #fbbf24;
  --accent-error: #f87171;
  --input-bg: rgba(255, 255, 255, 0.05);
  --input-border: rgba(255, 255, 255, 0.1);
  --input-focus: #4DA6FF;
}
```

These are registered in the `@theme inline` block as Tailwind colors:
```
--color-surface-panel: var(--surface-panel);
--color-surface-card: var(--surface-card);
--color-surface-elevated: var(--surface-elevated);
--color-surface-inset: var(--surface-inset);
--color-text-heading: var(--text-heading);
--color-text-body: var(--text-body);
--color-text-caption: var(--text-caption);
--color-border-default: var(--border-default);
--color-border-subtle: var(--border-subtle);
--color-accent-blue: var(--accent-blue);
--color-accent-pink: var(--accent-pink);
--color-accent-emerald: var(--accent-emerald);
--color-accent-amber: var(--accent-amber);
--color-accent-error: var(--accent-error);
--color-input-bg: var(--input-bg);
--color-input-border: var(--input-border);
--color-input-focus: var(--input-focus);
```

### Shared Layout Components

New shared components in `src/components/layout/`:

| Component | Purpose | Props |
|-----------|---------|-------|
| `PageHeader` | Page title + subtitle + optional right-side action | `title`, `subtitle`, `action?` |
| `ContentCard` | Themed card container with consistent radius/shadow/border | `children`, `className?`, `padding?` |
| `SplitLayout` | Two or three column panel layout for campaigns/trends/assets | `left`, `center?`, `right`, `leftWidth?`, `rightWidth?` |
| `FilterBar` | Row of filter pills with active/inactive states | `filters`, `active`, `onChange` |
| `StatusBadge` | Colored badge for status/severity levels | `status`, `size?` |
| `StatCard` | Stat display with icon, value, label | `icon`, `value`, `label`, `sublabel?` |

### Page File Restructuring

Large page files get decomposed into sub-folders:

```
src/pages/
├── landing/
│   ├── index.tsx          (exports LandingPage, composes sections)
│   ├── Header.tsx
│   ├── Hero.tsx
│   ├── AboutUs.tsx
│   ├── Features.tsx
│   ├── Pricing.tsx
│   ├── Faq.tsx
│   └── Footer.tsx
├── home.tsx               (stays single file, ~150 lines after extraction)
├── dashboard.tsx          (stays single file, shell layout)
├── compliance.tsx         (stays single file, already well-structured)
├── campaigns.tsx          (moderate, may stay or split into folder)
├── assets.tsx             (moderate, may stay or split into folder)
├── trends.tsx             (moderate, may stay or split into folder)
└── profile.tsx            (small, stays single file)
```

### Token Migration Strategy

For each page, the migration follows this pattern:

1. **Replace hardcoded dark values**: `dark:bg-[#111116]` → `bg-surface-card` (which resolves to the token)
2. **Replace hardcoded light values**: `bg-[#fafafa]` → `bg-surface-panel`
3. **Replace inline text colors**: `text-gray-900 dark:text-white` → `text-text-heading`
4. **Replace inline borders**: `border-gray-200 dark:border-white/10` → `border-border-default`
5. **Eliminate dual class patterns**: Remove patterns like `bg-X dark:bg-Y` when a single token class works

### Theme Toggle Behavior

- `next-themes` ThemeProvider already handles `.dark` class toggling
- System preference (`prefers-color-scheme`) is already supported as default
- No changes needed to the toggle mechanism, only to the token values it triggers

## Component Interactions

```
ThemeProvider (next-themes)
  └── applies .dark class to <html>
        └── CSS custom properties in :root / .dark resolve
              └── Tailwind @theme inline maps tokens to utility classes
                    └── All components use semantic classes (bg-surface-card, text-text-heading, etc.)
```

## Key Design Decisions

1. **Token-first, not utility-first**: Instead of `bg-white dark:bg-[#111116]`, use `bg-surface-card`. This means one class instead of two, and theme changes only require editing `index.css`.

2. **No shadcn/ui modifications**: All theming works through CSS custom properties that shadcn already reads. The existing shadcn tokens (--background, --foreground, --card, etc.) remain unchanged.

3. **Gradual migration over full rewrite**: Each page can be migrated independently. The new tokens coexist with old patterns during migration.

4. **Landing page keeps some hardcoded values**: The hero gradient/neon glow uses specialized SVG colors that don't map to semantic tokens. These remain as inline values but get dark: variants.

5. **Extracted components are optional wrappers**: Pages can progressively adopt shared components. The migration doesn't force all pages to change simultaneously.

## File Changes Summary

| File/Path | Change Type | Description |
|-----------|------------|-------------|
| `src/index.css` | Modified | Add new semantic tokens to `:root`, `.dark`, and `@theme inline` |
| `src/components/layout/PageHeader.tsx` | New | Shared page header component |
| `src/components/layout/ContentCard.tsx` | New | Shared themed card wrapper |
| `src/components/layout/SplitLayout.tsx` | New | Shared split-panel layout |
| `src/components/layout/FilterBar.tsx` | New | Shared filter pills component |
| `src/components/layout/StatusBadge.tsx` | New | Shared status badge |
| `src/components/layout/StatCard.tsx` | New | Shared stat card |
| `src/components/layout/index.ts` | New | Barrel export for layout components |
| `src/pages/landing/index.tsx` | New | Landing page entry point (replaces landing.tsx) |
| `src/pages/landing/Header.tsx` | New | Extracted header section |
| `src/pages/landing/Hero.tsx` | New | Extracted hero section |
| `src/pages/landing/AboutUs.tsx` | New | Extracted about section |
| `src/pages/landing/Features.tsx` | New | Extracted features section |
| `src/pages/landing/Pricing.tsx` | New | Extracted pricing section |
| `src/pages/landing/Faq.tsx` | New | Extracted FAQ section |
| `src/pages/landing/Footer.tsx` | New | Extracted footer section |
| `src/pages/landing.tsx` | Deleted | Replaced by landing/ folder |
| `src/pages/home.tsx` | Modified | Migrate to semantic tokens, use shared components |
| `src/pages/dashboard.tsx` | Modified | Migrate sidebar/header to semantic tokens |
| `src/pages/compliance.tsx` | Modified | Migrate to semantic tokens |
| `src/pages/campaigns.tsx` | Modified | Migrate to semantic tokens, use shared components |
| `src/pages/assets.tsx` | Modified | Migrate to semantic tokens, use shared components |
| `src/pages/trends.tsx` | Modified | Migrate to semantic tokens, use shared components |
| `src/pages/profile.tsx` | Modified | Migrate to semantic tokens |
