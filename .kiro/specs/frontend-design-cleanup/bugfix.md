# Bugfix Requirements Document

## Introduction

The JusAds dashboard frontend suffers from widespread typography and layout issues that undermine readability and professional appearance. Text is rendered at sizes well below the project's own design token minimums (e.g., 10px–12px inline text when the design system specifies 14px as the smallest UI label). Containers use aggressive truncation and line-clamping that hides meaningful content, sidebars impose narrow max-widths that cut off titles, and spacing between elements is too tight (gap-0.5, space-y-0.5) resulting in a cramped, cluttered interface. These issues affect all dashboard pages: home, campaigns, assets, trends, compliance, profile, and the shell layout.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN text labels, badges, timestamps, or metadata are rendered across dashboard pages THEN the system uses hardcoded sizes below the design token minimum (text-[10px], text-[12px], text-[9px]) making content difficult to read

1.2 WHEN campaign titles are displayed in the campaigns sidebar list THEN the system applies `truncate max-w-[170px]` which cuts off meaningful title text regardless of available space

1.3 WHEN trend signal descriptions, briefcase impact text, and activity descriptions are displayed THEN the system applies `line-clamp-2` or `truncate` hiding important content from the user

1.4 WHEN activity items, asset card details, or signal card metadata are displayed THEN the system uses extremely tight spacing (gap-0.5, space-y-0.5, mt-0.5) creating a cramped, unprofessional appearance

1.5 WHEN the three-column trends layout is rendered on standard desktop screens (1024px–1440px) THEN the left signal list (380px) and right briefcase panel (320px) squeeze the center detail column leaving insufficient reading width

1.6 WHEN asset detail drawer metadata sections (specs grid, tags, compliance) are rendered THEN the system uses text-[10px] for labels and text-[12px] for values which contradicts the design system minimum of text-label-ui (14px)

1.7 WHEN the home page "AI Engine Active" badge and activity timestamps are rendered THEN the system uses text-[10px] and text-[12px] creating visual inconsistency with the design token scale

1.8 WHEN card internal content is rendered (stat cards, promo card, insight items) THEN the system uses text-code-sm (13px) for body content that should use text-label-ui (14px) or text-body-md (16px) per the design specification's 18px minimum body text rule

### Expected Behavior (Correct)

2.1 WHEN text labels, badges, timestamps, or metadata are rendered across dashboard pages THEN the system SHALL use the established design tokens with text-code-xs (11px) as the absolute minimum only for monospace technical data, and text-label-ui (14px) as the minimum for all human-readable UI text

2.2 WHEN campaign titles are displayed in the campaigns sidebar list THEN the system SHALL remove the restrictive max-w-[170px] constraint and allow titles to use available sidebar width, wrapping to a second line if needed rather than truncating

2.3 WHEN trend signal descriptions, briefcase impact text, and activity descriptions are displayed THEN the system SHALL show full content using appropriate line heights and spacing, removing line-clamp restrictions on primary content areas

2.4 WHEN activity items, asset card details, or signal card metadata are displayed THEN the system SHALL use the design token spacing scale (stack-sm: 8px minimum gap between related items, stack-md: 16px between sections)

2.5 WHEN the three-column trends layout is rendered on standard desktop screens (1024px–1440px) THEN the system SHALL use proportional column sizing (e.g., flexible widths or responsive breakpoints) ensuring the center detail column maintains a minimum readable width of approximately 480px

2.6 WHEN asset detail drawer metadata sections (specs grid, tags, compliance) are rendered THEN the system SHALL use text-label-ui (14px) for labels and text-body-md (16px) for values, following the design token hierarchy

2.7 WHEN the home page "AI Engine Active" badge and activity timestamps are rendered THEN the system SHALL use text-code-xs (11px) for timestamps only and text-label-ui (14px) for badges and descriptive text, maintaining consistency with the design token scale

2.8 WHEN card internal content is rendered (stat cards, promo card, insight items) THEN the system SHALL use text-label-ui (14px) as the minimum for descriptive text and text-body-md (16px) for paragraph-length content, aligning with the Design.md specification of 18px body text

### Unchanged Behavior (Regression Prevention)

3.1 WHEN GSAP animations are triggered on page mount or element transitions THEN the system SHALL CONTINUE TO animate with the existing timing, easing, and stagger patterns without visual regression

3.2 WHEN the dashboard shell sidebar navigation is used on desktop THEN the system SHALL CONTINUE TO display the fixed 240px sidebar with existing nav items, icons, and active state styling

3.3 WHEN dark mode is active THEN the system SHALL CONTINUE TO apply the existing dark color scheme (bg-dark, white/10 borders, inverted text colors) correctly across all components

3.4 WHEN interactive elements (buttons, cards, filter pills) receive hover or click events THEN the system SHALL CONTINUE TO display existing hover effects, scale transitions, and active states

3.5 WHEN the compliance page pipeline status indicator, upload form, and review queue table are rendered THEN the system SHALL CONTINUE TO function with the existing design token usage (these components already follow the token system correctly)

3.6 WHEN responsive breakpoints collapse multi-column layouts to single-column on mobile (below 1024px) THEN the system SHALL CONTINUE TO stack columns vertically with appropriate overflow scrolling

3.7 WHEN filter controls (category pills, status pills, type selects) are interacted with THEN the system SHALL CONTINUE TO filter content correctly with existing visual feedback patterns
