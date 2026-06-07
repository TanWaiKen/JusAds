# Implementation Plan

## Overview

This task list follows the exploratory bugfix workflow to fix typography, truncation, spacing, and layout token violations across the JusAds dashboard pages (home.tsx, trends.tsx, campaigns.tsx, assets.tsx). The approach: write tests BEFORE fixing to understand the bug, preserve existing behavior, then implement and validate.

## Tasks

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Sub-Minimum Typography, Truncation, Spacing, and Fixed-Width Violations
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists across all four dashboard pages
  - **Scoped PBT Approach**: Scope the property to concrete failing cases found in home.tsx, trends.tsx, campaigns.tsx, and assets.tsx
  - Write a property-based test (using Vitest + fast-check) that:
    - Reads the source of home.tsx, trends.tsx, campaigns.tsx, assets.tsx
    - For each file, asserts NO occurrence of `text-[10px]`, `text-[12px]`, `text-[9px]`, `text-[12.5px]` for non-monospace UI text
    - Asserts NO occurrence of `truncate` combined with `max-w-[170px]`
    - Asserts NO occurrence of `line-clamp-2` on primary content descriptions
    - Asserts NO occurrence of sub-minimum spacing: `gap-0.5`, `space-y-0.5`, `mt-0.5`
    - Asserts NO occurrence of fixed-width panel classes: `w-[380px]`, `w-[320px]`
  - The test assertions match the Expected Behavior from design: all UI text ≥ 14px (text-label-ui), monospace ≥ 11px (text-code-xs), spacing ≥ 8px (stack-sm), proportional layouts
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists in all four page files)
  - Document counterexamples found (e.g., "home.tsx contains text-[10px] at line N", "campaigns.tsx has truncate max-w-[170px]")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Animation, Dark Mode, Hover States, Responsive Breakpoints, and Filter Controls Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe on UNFIXED code:
    - All `useGSAP` hook definitions, animation selectors, durations, easings, and stagger values in home.tsx, trends.tsx, campaigns.tsx, assets.tsx
    - All `dark:` variant classes remain present and unmodified
    - All hover/active state classes (hover:, active:, group-hover:) are intact
    - All responsive breakpoint classes (lg:, md:, sm:) for layout stacking remain present
    - All filter control logic (onClick handlers for category/status pills, onChange for selects) is unchanged
    - The compliance page source is completely untouched
    - The dashboard shell sidebar (240px width, nav items, active states) is unchanged
  - Write property-based tests (using Vitest + fast-check) that:
    - Extract all GSAP animation configurations (selectors, duration, ease, stagger, delay) from each page and assert they match observed baseline snapshots
    - Assert all `dark:` variant classes found in baseline exist unchanged after any modification
    - Assert all hover/active state class patterns remain identical
    - Assert responsive breakpoint classes for column stacking (lg:flex-row, lg:grid-cols-*) are preserved
    - Assert compliance.tsx file content is byte-identical to baseline
    - Assert dashboard.tsx sidebar structure is unchanged
  - Verify tests PASS on UNFIXED code (confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [x] 3. Fix for typography, truncation, spacing, and layout token violations across dashboard pages

  - [x] 3.1 Fix home.tsx typography and spacing
    - Replace `text-[12px]` with `text-label-ui` on AI Engine Active badge
    - Replace `text-[10px]` with `text-code-xs` on activity timestamps (monospace time data)
    - Replace `text-[12px]` with `text-label-ui` on activity descriptions
    - Replace `space-y-0.5` with `gap-stack-sm` (8px token) on activity item spacing
    - Replace `text-code-sm` with `text-label-ui` on stat card subtitles (non-code body content)
    - Replace `mt-0.5` with appropriate token-based spacing on activity icon margin
    - _Bug_Condition: isBugCondition(element) where element.fontSize < 14px AND fontFamily != 'JetBrains Mono', OR element.spacing < 8px_
    - _Expected_Behavior: All UI text renders at text-label-ui (14px) minimum, timestamps at text-code-xs (11px), spacing at stack-sm (8px) minimum_
    - _Preservation: GSAP animations in useGSAP hooks, dark mode classes, hover states, responsive breakpoints must remain unchanged_
    - _Requirements: 2.1, 2.4, 2.7, 2.8_

  - [x] 3.2 Fix trends.tsx layout, typography, and content visibility
    - Replace `lg:w-[380px]` with proportional flex sizing (e.g., `lg:w-1/4` or `lg:basis-[300px] lg:shrink-0`)
    - Replace `lg:w-[320px]` with proportional flex sizing (e.g., `lg:w-1/4` or `lg:basis-[280px] lg:shrink-0`)
    - Replace `text-[12px] line-clamp-2` with `text-label-ui` and remove `line-clamp-2` on signal descriptions
    - Replace `text-[10px]` with `text-code-xs` on category/risk badges
    - Replace `text-[12px]` with `text-label-ui` on header subtitle
    - Replace `text-[12px]` with `text-label-ui` on briefcase panel description
    - Remove `line-clamp-2` from briefcase impact text
    - Replace `text-[12.5px]` with `text-label-ui` on onboarding banner description
    - _Bug_Condition: isBugCondition(element) where element.hasFixedWidth IN [380, 320], OR element.hasClass('line-clamp-2') on primaryContent, OR element.fontSize < 14px for UI text_
    - _Expected_Behavior: Proportional columns maintaining ≥480px center width, full content visible, all text at token minimums_
    - _Preservation: GSAP animations, dark mode, hover states, filter pill interactions must remain unchanged_
    - _Requirements: 2.1, 2.3, 2.5_

  - [x] 3.3 Fix campaigns.tsx truncation and typography
    - Remove `truncate max-w-[170px]` from campaign titles, allow natural wrapping with available sidebar width
    - Replace `text-[12px]` with `text-label-ui` on market text
    - Replace `text-[10px]` with `text-code-xs` on status badges
    - Replace `mb-1.5` with `mb-stack-sm` equivalent where spacing is sub-minimum
    - _Bug_Condition: isBugCondition(element) where element.hasClass('truncate') AND element.hasClass('max-w-[170px]'), OR element.fontSize < 14px for non-monospace_
    - _Expected_Behavior: Titles wrap naturally within available width, all text at token minimums_
    - _Preservation: GSAP animations, dark mode, hover/active states on campaign cards, filter controls must remain unchanged_
    - _Requirements: 2.1, 2.2_

  - [x] 3.4 Fix assets.tsx typography and spacing
    - Replace `text-[10px]` with `text-label-ui` on specs grid labels
    - Replace `text-xs` (12px) with `text-label-ui` (14px) on specs grid values
    - Replace `text-[10px]` with `text-code-xs` on tag text (monospace appropriate)
    - Replace `text-[12px]` with `text-label-ui` on compliance description
    - Replace `mt-0.5` with `mt-stack-sm` equivalent on campaign subtitle spacing
    - Replace `space-y-0.5` with `space-y-1` or `gap-stack-sm` on specs grid internal spacing
    - Replace `text-[9px]` with `text-code-xs` on compliance badge
    - _Bug_Condition: isBugCondition(element) where element.fontSize < 14px for labels/values, OR element.spacing < 8px_
    - _Expected_Behavior: Labels at text-label-ui (14px), tags at text-code-xs (11px), spacing at stack-sm (8px) minimum_
    - _Preservation: GSAP animations, dark mode, hover states, responsive behavior must remain unchanged_
    - _Requirements: 2.1, 2.4, 2.6_

  - [x] 3.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Sub-Minimum Typography, Truncation, Spacing, and Fixed-Width Violations Resolved
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior (no sub-minimum tokens, no restrictive truncation, no tight spacing, no fixed-width panels)
    - When this test passes, it confirms all bug conditions are resolved across all four pages
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [x] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - Animation, Dark Mode, Hover States, Responsive Breakpoints, and Filter Controls Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all GSAP animations, dark mode, hover states, responsive breakpoints, filter controls, compliance page, and sidebar remain unchanged after fix
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [x] 4. Checkpoint - Ensure all tests pass
  - Run full test suite to confirm both exploration and preservation tests pass
  - Verify no TypeScript compilation errors introduced
  - Verify no lint errors introduced
  - Ensure the compliance page was NOT modified (byte-identical check)
  - Ask the user if questions arise

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1", "2"] },
    { "id": 1, "tasks": ["3.1", "3.2", "3.3", "3.4"] },
    { "id": 2, "tasks": ["3.5"] },
    { "id": 3, "tasks": ["3.6"] },
    { "id": 4, "tasks": ["4"] }
  ]
}
```

## Notes

- The compliance page (compliance.tsx) is already correct and MUST NOT be modified
- All changes are limited to: home.tsx, trends.tsx, campaigns.tsx, assets.tsx
- Design tokens referenced: text-label-ui (14px), text-code-xs (11px), text-code-sm (13px), stack-sm (8px), stack-md (16px)
- Property-based tests use Vitest + fast-check for automated input generation
- GSAP animations, shadcn/ui components, dark mode, hover states, and responsive breakpoints must be preserved exactly
