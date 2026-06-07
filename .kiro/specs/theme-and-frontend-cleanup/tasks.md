# Implementation Tasks

## Task 1: Expand Theme Token System in index.css

- [x] 1.1 Add semantic surface tokens (`--surface-panel`, `--surface-card`, `--surface-elevated`, `--surface-inset`) to `:root` with light mode values
- [x] 1.2 Add semantic text tokens (`--text-heading`, `--text-body`, `--text-caption`) to `:root` with light mode values
- [x] 1.3 Add semantic border tokens (`--border-default`, `--border-subtle`) to `:root` with light mode values
- [x] 1.4 Add semantic accent tokens (`--accent-blue`, `--accent-pink`, `--accent-emerald`, `--accent-amber`, `--accent-error`) to `:root` with light mode values
- [x] 1.5 Add semantic input tokens (`--input-bg`, `--input-border`, `--input-focus`) to `:root` with light mode values
- [x] 1.6 Add all corresponding dark mode values to the `.dark` selector
- [x] 1.7 Register all new tokens in the `@theme inline` block as Tailwind color utilities (e.g., `--color-surface-panel: var(--surface-panel)`)
- [x] 1.8 Verify the build compiles without errors after token additions

## Task 2: Create Shared Layout Components

- [x] 2.1 Create `src/components/layout/PageHeader.tsx` — accepts `title`, `subtitle`, optional `action` slot; uses `text-text-heading` and `text-text-body` tokens
- [x] 2.2 Create `src/components/layout/ContentCard.tsx` — themed card wrapper using `bg-surface-card`, `border-border-default`, consistent radius and shadow
- [x] 2.3 Create `src/components/layout/SplitLayout.tsx` — configurable two or three column layout using `bg-surface-panel` for side panels
- [x] 2.4 Create `src/components/layout/FilterBar.tsx` — row of pill buttons with active state using accent tokens and inactive using `bg-surface-inset`
- [x] 2.5 Create `src/components/layout/StatusBadge.tsx` — status/severity badge using accent tokens (emerald for passed, amber for warning, error for critical, gray for draft)
- [x] 2.6 Create `src/components/layout/StatCard.tsx` — stat display card using `bg-surface-card` with icon, animated number value, and label
- [x] 2.7 Create `src/components/layout/index.ts` — barrel export for all layout components
- [x] 2.8 Verify all shared components render correctly in both light and dark mode

## Task 3: Restructure Landing Page into Sub-Components

- [x] 3.1 Create `src/pages/landing/` directory
- [x] 3.2 Extract `Header` component into `src/pages/landing/Header.tsx` with its theme toggle, auth actions, and navigation
- [x] 3.3 Extract `Hero` component into `src/pages/landing/Hero.tsx` with neon gradient and CTA buttons
- [x] 3.4 Extract `AboutUs` component into `src/pages/landing/AboutUs.tsx` with ad comparison cards
- [x] 3.5 Extract `Features` component into `src/pages/landing/Features.tsx` (How It Works + Features grid)
- [x] 3.6 Extract `Pricing` component into `src/pages/landing/Pricing.tsx` with pricing cards
- [x] 3.7 Extract `Faq` component into `src/pages/landing/Faq.tsx` with accordion
- [x] 3.8 Extract `Footer` component into `src/pages/landing/Footer.tsx`
- [x] 3.9 Create `src/pages/landing/index.tsx` that composes all sections with GSAP ScrollTrigger animations
- [x] 3.10 Update route imports in `App.tsx` to use the new landing folder entry point
- [x] 3.11 Delete the old `src/pages/landing.tsx` file
- [x] 3.12 Verify landing page renders and scrolls correctly with all animations intact

## Task 4: Migrate Landing Page to Semantic Tokens

- [x] 4.1 Replace all `dark:bg-[#111116]` and `bg-white` patterns in landing sub-components with `bg-surface-card` or `bg-surface-panel`
- [x] 4.2 Replace `text-[#111]` / `dark:text-white` with `text-text-heading` for headings and titles
- [x] 4.3 Replace `text-[#111]/60` / `dark:text-gray-400` with `text-text-body` or `text-text-caption`
- [x] 4.4 Replace `border-gray-200 dark:border-white/10` with `border-border-default`
- [x] 4.5 Replace hardcoded button styles with token-based variants (primary: `bg-foreground text-background`, secondary: `bg-surface-card border-border-default`)
- [x] 4.6 Update pricing card borders and backgrounds to use token classes
- [x] 4.7 Update FAQ accordion items to use `bg-surface-card` and `border-border-default`
- [x] 4.8 Verify the landing page looks correct in both light and dark mode, matching Figma reference

## Task 5: Migrate Dashboard Shell to Semantic Tokens

- [x] 5.1 Replace sidebar `bg-white dark:bg-[#111116]` with `bg-surface-card`
- [x] 5.2 Replace sidebar borders `border-gray-200 dark:border-white/10` with `border-border-default`
- [x] 5.3 Replace header `bg-white/80 dark:bg-bg-dark/80` with `bg-surface-card/80` and backdrop-blur
- [x] 5.4 Replace nav item text colors with `text-text-body` (inactive) and `text-accent-blue` (active)
- [x] 5.5 Replace user profile section colors with token-based classes
- [x] 5.6 Verify sidebar, header, and main content area render correctly in both themes

## Task 6: Migrate Home Page to Semantic Tokens and Shared Components

- [x] 6.1 Replace stat card `bg-white dark:bg-[#111116]` with `bg-surface-card` and `border-border-default`
- [x] 6.2 Replace promo card and sentiment panel colors with token-based classes
- [x] 6.3 Replace activity section `bg-white dark:bg-[#111116]` with `bg-surface-card`
- [x] 6.4 Replace all `text-gray-900 dark:text-white` headings with `text-text-heading`
- [x] 6.5 Replace all `text-gray-500 dark:text-gray-400` captions with `text-text-caption`
- [x] 6.6 Optionally adopt `StatCard` shared component for the three stat cards
- [x] 6.7 Optionally adopt `ContentCard` for the promo and sentiment panels
- [x] 6.8 Verify home page animations and visual appearance in both themes

## Task 7: Migrate Campaigns Page to Semantic Tokens and Shared Components

- [x] 7.1 Replace left sidebar `bg-[#fafafa] dark:bg-[#111116]` with `bg-surface-panel`
- [x] 7.2 Replace campaign card backgrounds and borders with `bg-surface-card` / `bg-surface-elevated` and `border-border-default`
- [x] 7.3 Replace detail area `bg-white dark:bg-bg-dark` with `bg-background`
- [x] 7.4 Replace filter pill styles with `FilterBar` shared component or equivalent token classes
- [x] 7.5 Replace info grid card backgrounds `bg-[#fafafa] dark:bg-[#111116]` with `bg-surface-panel`
- [x] 7.6 Replace all heading/body/caption text colors with semantic token classes
- [x] 7.7 Replace form input styles with `bg-input-bg border-input-border focus:border-input-focus`
- [x] 7.8 Adopt `StatusBadge` for campaign status pills (Draft, Active, Review)
- [x] 7.9 Verify campaigns page renders correctly in both themes with animations intact

## Task 8: Migrate Assets Page to Semantic Tokens and Shared Components

- [x] 8.1 Replace left area `bg-white dark:bg-bg-dark` with `bg-background`
- [x] 8.2 Replace right drawer `bg-[#fafafa] dark:bg-[#111116]` with `bg-surface-panel`
- [x] 8.3 Replace asset card backgrounds and borders with `bg-surface-card` and `border-border-default`
- [x] 8.4 Replace search input styling with `bg-input-bg border-input-border` tokens
- [x] 8.5 Replace select/filter styling with token-based input classes
- [x] 8.6 Replace compliance badge in cards with `StatusBadge` component or token pattern
- [x] 8.7 Replace detail drawer text colors and label sizes with token classes
- [x] 8.8 Verify assets page renders correctly in both themes with animations intact

## Task 9: Migrate Trends Page to Semantic Tokens and Shared Components

- [x] 9.1 Replace left signal list `bg-[#fafafa] dark:bg-[#111116]` with `bg-surface-panel`
- [x] 9.2 Replace center canvas `bg-white dark:bg-bg-dark` with `bg-background`
- [x] 9.3 Replace right briefcase panel `bg-[#fafafa] dark:bg-[#111116]` with `bg-surface-panel`
- [x] 9.4 Replace signal card backgrounds and borders with `bg-surface-card` / `bg-surface-elevated` and `border-border-default`
- [x] 9.5 Replace filter pill styles with `FilterBar` or equivalent token classes
- [x] 9.6 Replace detail section backgrounds (`bg-gray-50 dark:bg-black/10`) with `bg-surface-inset`
- [x] 9.7 Replace all heading/body/caption text colors with semantic token classes
- [x] 9.8 Replace risk level badges with `StatusBadge` component or shared token pattern
- [x] 9.9 Verify trends page renders correctly in both themes with animations intact

## Task 10: Migrate Compliance Page to Semantic Tokens

- [x] 10.1 Review compliance page and sub-components for any remaining hardcoded color values
- [x] 10.2 Replace any `bg-surface-container-low` patterns with the new semantic token equivalents if needed for consistency
- [x] 10.3 Ensure compliance sub-components (SummaryCards, UploadForm, PipelineStatusIndicator, ReviewQueueTable, DetailPanel) use consistent tokens with other pages
- [x] 10.4 Verify compliance page pipeline, upload, and results display correctly in both themes

## Task 11: Migrate Profile Page to Semantic Tokens

- [x] 11.1 Replace profile card `bg-white dark:bg-[#111116]` with `bg-surface-card` and `border-border-default`
- [x] 11.2 Replace info row hover states `hover:bg-gray-50 dark:hover:bg-white/5` with `hover:bg-surface-inset`
- [x] 11.3 Replace heading and body text colors with `text-text-heading` and `text-text-caption`
- [x] 11.4 Replace avatar ring colors with token-based borders
- [x] 11.5 Verify profile page renders correctly in both themes with animations intact

## Task 12: Final Integration Verification

- [x] 12.1 Run the frontend build (`npm run build`) and confirm zero errors
- [x] 12.2 Run the linter (`npm run lint`) and confirm no new warnings related to theming changes
- [x] 12.3 Visually verify all 8 pages in light mode — check color consistency, contrast, and layout
- [x] 12.4 Visually verify all 8 pages in dark mode — check color consistency, contrast, and layout
- [x] 12.5 Test theme toggle on landing page and within dashboard — confirm instant switch with no flash or layout shift
- [x] 12.6 Test responsive behavior at mobile breakpoints in both themes
- [x] 12.7 Confirm all GSAP animations still fire correctly on page mounts and interactions
- [x] 12.8 Confirm no changes were made to `src/components/ui/` files
