# Requirements Document

## Introduction

This feature delivers a consistent, polished dark mode and light mode theming system across all pages of the JusAds frontend, and restructures the frontend codebase for clarity and maintainability. Currently, theming is applied inconsistently — pages use a mix of hardcoded color values, ad-hoc dark: variants, and design token references. The codebase also lacks shared layout patterns, leading to duplicated styling logic across pages. This spec unifies theming through a centralized token system and reorganizes frontend code so every page is clean, readable, and easy to maintain.

## Glossary

- **Theme_System**: The centralized set of CSS custom properties (design tokens) and Tailwind utility classes that control all color, background, border, and text styling across both light and dark modes
- **Design_Token**: A named CSS custom property (e.g., `--color-surface-container-low`) that maps to a specific color value and changes based on the active theme (light or dark)
- **Page_Component**: A top-level React component in `src/pages/` that renders a full route view (landing, home, compliance, campaigns, assets, trends, profile, dashboard)
- **Theme_Provider**: The `next-themes` based component that manages dark/light/system preference and applies the `.dark` class to the document
- **Shared_Layout_Component**: A reusable React component extracted from repeated patterns across pages (e.g., page headers, card containers, section wrappers)
- **Figma_Reference**: The HTML mockup files in `figma/` that represent the intended visual design for each page

## Requirements

### Requirement 1: Centralized Dark Mode Token Coverage

**User Story:** As a developer, I want all dark mode colors defined as design tokens in a single location, so that theme changes propagate consistently across all pages without page-level overrides.

#### Acceptance Criteria

1. THE Theme_System SHALL define dark mode values within the `.dark` selector in `index.css` for every semantic color token declared in the `@theme inline` block, including at minimum: surface backgrounds (`surface-container-low`, `surface-container-high`, `surface-container-highest`, `surface-container-lowest`, `surface-bright`), text colors (`text-primary`, `text-secondary`, `text-muted`), border/outline colors (`outline-variant`, `border`), and accent colors (`aurora-purple`, `cosmic-pink`, `emerald-glow`, `ship-red`)
2. WHEN dark mode is active, THE Theme_System SHALL resolve every semantic color token referenced in the `@theme inline` block to a valid color value, such that no token returns an undefined or inherited light-mode value
3. WHEN a Page_Component renders in dark mode, THE Page_Component SHALL contain zero inline dark-mode color overrides (i.e., zero occurrences of Tailwind arbitrary value syntax matching the pattern `dark:bg-[...]`, `dark:text-[...]`, or `dark:border-[...]`) and SHALL instead reference only Design_Tokens via Tailwind semantic classes (e.g., `bg-background`, `text-foreground`, `border-border`) or named token utilities (e.g., `bg-surface-container-low`, `text-text-muted`)
4. IF a color value is used in more than one Page_Component, THEN THE Theme_System SHALL define it as a single shared Design_Token in the `.dark` selector, and no two Page_Component files SHALL contain the same hardcoded hex or oklch color string in dark-mode utility classes
5. WHEN a new Design_Token is added to the `.dark` selector, THE Theme_System SHALL ensure the token name matches an existing entry in the `@theme inline` block so that Tailwind utility classes resolve correctly without additional configuration

### Requirement 2: Consistent Light Mode Token Coverage

**User Story:** As a developer, I want all light mode colors defined as design tokens, so that the light theme is equally maintainable and consistent.

#### Acceptance Criteria

1. THE Theme_System SHALL define light mode values within the `:root` selector in `index.css` for each token category: surface backgrounds (container-low, container-high, container-highest, container-lowest, bright, dim), text colors (primary, secondary, muted), border/outline colors (border, outline-variant), and accent colors (aurora-purple, cosmic-pink, emerald-glow, ship-red)
2. WHEN light mode is active, THE Page_Component SHALL use the same token-based Tailwind classes as dark mode (e.g., `bg-surface-container-low`, `text-text-primary`) so that each class resolves to the light mode value defined in `:root` without requiring light-specific class overrides
3. WHEN a Page_Component renders in light mode, THE Page_Component SHALL NOT use hardcoded color values (e.g., `bg-[#fafafa]`, `bg-white`, `text-[#111]`, `text-gray-900`, `bg-gray-50`) where an equivalent Design_Token exists for the same semantic purpose (surface, text, or border)
4. WHEN light mode is active, THE Theme_System SHALL define a token value for every token that has a corresponding value in the `.dark` selector, so that no token resolves to `undefined` or falls back to an inherited default in light mode
5. IF a Page_Component uses a Tailwind arbitrary value (bracket notation such as `bg-[#hex]`) for a color that maps to a defined semantic role (surface background, heading text, body text, border, or accent), THEN THE Page_Component SHALL replace that arbitrary value with the corresponding Design_Token class

### Requirement 3: Page-Level Theme Consistency

**User Story:** As a user, I want every page to look visually consistent in both dark and light mode, so that switching themes feels polished and intentional.

#### Acceptance Criteria

1. WHEN the user switches between dark and light mode, THE Theme_System SHALL update all visible surfaces, text, borders, and icons across all eight Page_Components within 300 milliseconds and without requiring a page reload
2. THE Page_Component for each page (landing, home, dashboard shell, compliance, campaigns, assets, trends, profile) SHALL use the same semantic Design_Token for each UI element category: card backgrounds SHALL use the `card` surface token, page titles SHALL use the `foreground` text token, secondary text SHALL use the `muted-foreground` token, and section containers SHALL use the `surface-container-low` token
3. WHEN cards, panels, or containers are rendered across different pages, THE Page_Components SHALL use the same `--radius` token for border-radius, the same `card-shadow` class for elevation, and the same `border` token for borders, so that a card on one page is visually indistinguishable in shape, shadow, and border from a card on any other page
4. WHEN sidebar or panel backgrounds are rendered on campaigns, trends, and assets pages, THE Page_Components SHALL use the same surface token for the left/right panel backgrounds rather than page-specific values
5. WHEN icons are rendered within themed surfaces across any Page_Component, THE Page_Components SHALL apply the `foreground` or `muted-foreground` token to icon stroke or fill colors so that icons adapt to the active theme without hardcoded color values

### Requirement 4: Shared Layout Components Extraction

**User Story:** As a developer, I want repeated layout patterns extracted into shared components, so that each page file is shorter, easier to read, and changes propagate from one place.

#### Acceptance Criteria

1. WHEN a page header pattern (title + subtitle + optional action element) appears on 2 or more pages, THE codebase SHALL provide a shared PageHeader component that accepts a title string, a subtitle string, and an optional action slot (React node), rendering them with consistent spacing and typography tokens already used in the codebase
2. WHEN a card container pattern (rounded-2xl corners, 1px border using theme border tokens, shadow, and internal padding of 20–24px) is used on 2 or more pages, THE codebase SHALL provide a shared Card component that applies these styles uniformly and accepts children for content customization
3. WHEN a split-panel layout is used for list-detail views (campaigns, trends, assets), THE codebase SHALL provide a shared SplitPanelLayout component that accepts between 2 and 3 panel slots, where each panel's width is configurable via props, and the layout collapses to a vertical stack on viewports narrower than the lg breakpoint (1024px)
4. THE shared layout components SHALL accept props for content customization while enforcing consistent spacing, borders, and theme tokens already defined in the project's Tailwind configuration
5. IF a shared layout component is rendered without its required props (title for PageHeader, children for Card), THEN THE component SHALL render nothing or display a development-time console warning, and SHALL NOT throw a runtime error that breaks the page
6. WHEN a shared layout component is used on a page, THE resulting page file SHALL import and compose the shared component instead of inlining the layout markup, reducing the repeated pattern code to a single component invocation per usage

### Requirement 5: Page File Readability and Organization

**User Story:** As a developer, I want each page file to be clean and focused on page-specific logic, so that I can understand any page quickly without parsing through styling boilerplate.

#### Acceptance Criteria

1. WHEN a Page_Component file exceeds 200 lines, THE codebase SHALL extract sub-sections into child components within a page-specific folder named after the page (e.g., `pages/landing/Hero.tsx`, `pages/landing/Features.tsx`), where each child component file is named using PascalCase matching the section it represents
2. THE Page_Component files SHALL separate static data arrays and configuration objects (such as navigation items, feature lists, FAQ entries, pricing tiers, and stats arrays containing 3 or more items) from JSX rendering by declaring them as named `const` exports above the component function or in a co-located `constants.ts` file within the page folder
3. WHEN a page uses inline helper functions that exceed 10 lines, THE Page_Component SHALL extract those functions into the page-specific folder if used only by that page, or into `src/lib/` if used by 2 or more pages
4. THE codebase SHALL maintain a consistent file structure pattern: the page entry point file contains only imports, top-level state, and a single return composing child components; each child component is self-contained with its own `useRef` for a container element and its own `useGSAP` hook scoped to that ref, importing no sibling component's internal state or refs
5. WHEN a Page_Component is split into a page-specific folder, THE page entry point file (e.g., `pages/landing/index.tsx`) SHALL not exceed 50 lines and SHALL serve only as a composition root that imports and renders child components

### Requirement 6: Landing Page Theme Polish

**User Story:** As a visitor, I want the landing page to look equally polished and intentional in both dark and light mode, so that the product makes a strong first impression regardless of theme preference.

#### Acceptance Criteria

1. WHEN the landing page renders in dark mode, THE landing Page_Component SHALL display the hero gradient, neon glow SVG, and section backgrounds using the dark theme token values defined in the project CSS (`.dark` class variables), with no element reverting to light-mode colors or appearing unstyled
2. WHEN the landing page renders in light mode, THE landing Page_Component SHALL display all body text and heading text with a minimum contrast ratio of 4.5:1 against their respective background surfaces, with no section background falling below 10% luminance difference from adjacent sections
3. WHEN pricing cards, FAQ accordion, and feature sections render in either theme, THE landing Page_Component SHALL apply the theme's `--card` and `--card-foreground` surface tokens for backgrounds and text respectively, and all card borders SHALL use the theme's `--border` token value
4. WHILE the landing page is displayed, THE landing Page_Component header navigation links SHALL render hover states with a visible color shift (from the muted default color to the full-contrast foreground color) and active states with a scale transform of 0.95, in both dark and light themes
5. WHEN the user toggles the theme via the header theme button, THE landing Page_Component SHALL re-render all sections, cards, and navigation elements in the selected theme's token values within 300ms, with no flash of the previous theme's colors

### Requirement 7: Dashboard Pages Theme Alignment

**User Story:** As a logged-in user, I want all dashboard pages (home, campaigns, assets, trends, compliance, profile) to use a unified dark/light appearance, so that navigating between pages feels seamless.

#### Acceptance Criteria

1. WHEN the dashboard shell sidebar renders, THE dashboard Page_Component SHALL use the `sidebar` design tokens (`--sidebar`, `--sidebar-foreground`, `--sidebar-border`, `--sidebar-accent`, `--sidebar-accent-foreground`, `--sidebar-primary`, `--sidebar-primary-foreground`) for background, text, border, and active-state highlighting in both themes
2. WHEN stat cards, activity lists, or summary panels render on the home page, THE home Page_Component SHALL use the `--card` and `--card-foreground` tokens for card surfaces and the `--foreground` / `--muted-foreground` tokens for text, matching the same token references used by cards on campaigns, assets, and trends pages
3. WHEN filter pills or category buttons render across campaigns, trends, and assets pages, THE Page_Components SHALL use an identical active/inactive token pair where active state applies `bg-text-primary dark:bg-white text-white dark:text-text-primary` and inactive state applies `bg-gray-100 dark:bg-white/5 text-gray-500 hover:bg-gray-200 dark:hover:bg-white/10`
4. WHEN form inputs (search bars, text inputs, selects) render across any dashboard page, THE Page_Components SHALL use the `--input` token for background, `--border` token for border, and `--ring` token for focus ring, with a visible focus ring appearing on keyboard focus
5. WHEN status badges (Draft, Active, Review, Passed, Error) render across pages, THE Page_Components SHALL use a shared token pattern where each status maps to a fixed background/text color pair: Draft uses `bg-gray-100 dark:bg-white/5 text-gray-500`, Active uses `bg-emerald-50 dark:bg-emerald-950/20 text-emerald-600`, Review uses `bg-amber-50 dark:bg-amber-950/20 text-amber-600`, Passed uses `bg-emerald-50 dark:bg-emerald-950/20 text-emerald-600`, and Error uses `bg-red-50 dark:bg-red-950/20 text-red-600`
6. WHEN the user toggles between dark and light mode while on any dashboard page, THE Page_Components SHALL update all surface, text, and border colors within 1 frame (no flash of incorrect theme) and no element SHALL retain stale theme colors from the previous mode

### Requirement 8: Figma Reference Alignment

**User Story:** As a designer, I want the implemented pages to closely match the Figma reference HTML files, so that the design intent is faithfully represented in production.

#### Acceptance Criteria

1. WHEN a Figma_Reference file exists for a page (home, profile, campaign, trends, assets, compliance), THE corresponding Page_Component SHALL use the same spacing tokens (stack-sm, stack-md, stack-lg, gutter, margin-page, sidebar-width, max-content-width) as defined in that reference for margins, padding, and gaps between sections
2. THE Page_Components SHALL apply the same typography token for each text element as specified in the Figma_Reference, matching font-family, font-size, font-weight, line-height, and letter-spacing values from the project's type scale (label-ui at 14px, body-md at 16px, body-lg at 18px, headline-sm at 24px, headline-md at 32px, headline-lg at 48px, code-sm at 13px, code-xs at 11px)
3. WHEN the Figma_Reference defines a grid layout for a section, THE Page_Component SHALL implement the same number of columns and the same proportional column width ratios (e.g., 2/3 + 1/3, equal thirds) at viewports 1024px and above
4. WHEN a Figma_Reference defines a page structure with sidebar, header, and content regions, THE Page_Component SHALL render the same structural regions in the same relative positions with the sidebar at 240px width and the content area offset accordingly
5. IF no Figma_Reference file exists for a given page, THEN THE Page_Component SHALL follow the project's established spacing tokens and typography scale without requiring visual alignment verification against a reference

### Requirement 9: Theme Toggle Accessibility

**User Story:** As a user with accessibility needs, I want the theme toggle and all themed content to remain accessible, so that switching modes does not degrade usability.

#### Acceptance Criteria

1. THE Theme_System SHALL maintain WCAG 2.1 AA contrast ratios (minimum 4.5:1 for normal text under 18pt, minimum 3:1 for large text at 18pt or 14pt bold and above) in both light and dark modes for all Design_Token text-on-background combinations
2. WHEN the theme toggle button is rendered, THE Theme_Provider SHALL expose an `aria-label` attribute describing the target state (e.g., "Switch to dark mode" when light mode is active) and the button SHALL be operable via keyboard (Enter and Space keys) with no additional pointing device required
3. WHEN focus indicators are displayed on interactive elements, THE Theme_System SHALL render focus rings with a minimum 3:1 contrast ratio against the adjacent background color in both light and dark modes
4. IF the user has set a system-level color scheme preference (prefers-color-scheme) and no theme selection is stored in local storage, THEN THE Theme_Provider SHALL apply the system preference as the default theme
5. IF the user manually selects a theme via the toggle, THEN THE Theme_Provider SHALL persist that selection in local storage and use it as the active theme on subsequent visits, overriding the system-level preference
6. WHEN the theme changes, THE Theme_System SHALL preserve the currently focused element's focus position so that keyboard and screen reader users do not lose their place in the document

### Requirement 10: No Regression to Existing Functionality

**User Story:** As a developer, I want theming and cleanup changes to not break any existing page functionality, so that the refactor is purely visual and structural.

#### Acceptance Criteria

1. WHEN GSAP animations are triggered on page mount, scroll, or interaction, THE Page_Components SHALL continue to animate with the same duration values, easing functions, and stagger intervals defined in each component's useGSAP hook prior to refactoring
2. WHEN authentication flows (login, logout, callback) are triggered, THE application SHALL complete OAuth redirects, update user session state, and render the authenticated or unauthenticated UI without errors regardless of the active theme
3. WHEN the compliance checker pipeline processes an upload, THE compliance Page_Component SHALL display all pipeline node statuses, the animated score count-up, the violation list with severity badges, and the risk-level indicator without loss of data or visual elements
4. THE application SHALL NOT modify any files within `components/ui/` — all theming SHALL flow through CSS custom properties that shadcn/ui primitives already consume
5. WHEN the viewport width is below 768px, THE Page_Components SHALL stack content vertically without horizontal overflow and maintain scrollable access to all content in both light and dark themes
6. WHEN page files are restructured or renamed during cleanup, THE application SHALL preserve all existing route paths so that navigation between pages and direct URL access continue to resolve to the correct Page_Component
