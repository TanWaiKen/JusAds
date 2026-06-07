# Frontend Design Cleanup Bugfix Design

## Overview

The JusAds dashboard frontend renders text at sizes below the project's design token minimums (10px–12px where 14px is the UI minimum), applies aggressive truncation and line-clamping that hides meaningful content, uses tight spacing (gap-0.5, space-y-0.5) that creates a cramped appearance, and imposes fixed-width side panels that squeeze the center reading column on standard desktops. The fix replaces all sub-minimum hardcoded sizes with the correct design tokens, removes restrictive truncation/clamping, upgrades spacing to the token scale, and makes the trends layout proportional — all without touching GSAP animations or shadcn/ui components.

## Glossary

- **Bug_Condition (C)**: Any Tailwind class in a dashboard page file that specifies a font size below `text-label-ui` (14px) for human-readable UI text, applies restrictive truncation/max-width or line-clamp to primary content, uses spacing below `stack-sm` (8px), or uses fixed-width side panels that squeeze center content
- **Property (P)**: The corrected rendering where all human-readable text meets the minimum token size, content is fully visible, spacing uses the design token scale, and layouts are proportional
- **Preservation**: GSAP animation timing/easing/stagger, dark mode colors, hover/active states, responsive breakpoints, filter controls, shadcn/ui components, and the compliance page (already correct) must remain unchanged
- **text-label-ui**: The 14px minimum token for all human-readable UI text (font-family: Hanken Grotesk)
- **text-code-xs**: The 11px token reserved exclusively for monospace technical data (font-family: JetBrains Mono)
- **text-code-sm**: The 13px monospace token for secondary code/data display
- **stack-sm**: The 8px minimum gap token for spacing between related items
- **stack-md**: The 16px gap token for spacing between sections

## Bug Details

### Bug Condition

The bug manifests when any dashboard page component renders text, spacing, or layout using hardcoded values that fall below the design token scale. This affects typography (text-[10px], text-[12px], text-[9px] for non-monospace content), layout (fixed 380px + 320px side panels, max-w-[170px] truncation), content visibility (line-clamp-2 on primary descriptions), and spacing (gap-0.5, space-y-0.5, mt-0.5).

**Formal Specification:**
```
FUNCTION isBugCondition(element)
  INPUT: element of type TailwindStyledElement
  OUTPUT: boolean
  
  RETURN (element.fontSize < 14px AND element.fontFamily != 'JetBrains Mono')
         OR (element.fontSize < 11px)
         OR (element.hasClass('truncate') AND element.hasClass('max-w-[170px]'))
         OR (element.hasClass('line-clamp-2') AND element.isType('primaryContent'))
         OR (element.spacing < 8px AND element.spacingType IN ['gap', 'space-y', 'mt'])
         OR (element.parentLayout == 'trends' AND element.hasFixedWidth IN [380, 320])
END FUNCTION
```

### Examples

- **home.tsx**: "AI Engine Active" badge renders at `text-[12px]` → should be `text-label-ui` (14px)
- **home.tsx**: Activity timestamps render at `text-[10px]` → should be `text-code-xs` (11px, monospace)
- **home.tsx**: Activity descriptions render at `text-[12px]` with `space-y-0.5` → should be `text-label-ui` (14px) with `space-y-stack-sm` (8px)
- **trends.tsx**: Signal descriptions render at `text-[12px] line-clamp-2` → should be `text-label-ui` (14px) without line-clamp
- **trends.tsx**: Category badges render at `text-[10px]` → should be `text-code-xs` (11px, monospace-appropriate) or `text-label-ui` (14px)
- **campaigns.tsx**: Campaign titles have `truncate max-w-[170px]` → should allow wrapping with available width
- **campaigns.tsx**: Market text renders at `text-[12px]` → should be `text-label-ui` (14px)
- **campaigns.tsx**: Status badges render at `text-[10px]` → should be `text-code-xs` (11px)
- **assets.tsx**: Spec grid labels render at `text-[10px]` → should be `text-label-ui` (14px)
- **assets.tsx**: Tag text renders at `text-[10px]` → should be `text-code-xs` (11px)
- **assets.tsx**: Compliance description renders at `text-[12px]` → should be `text-label-ui` (14px)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- GSAP animations (useGSAP hooks) must continue to animate with existing timing, easing, and stagger patterns
- Dark mode color scheme (bg-dark, white/10 borders, inverted text) must remain correct
- Hover/active states on buttons and cards must continue working
- Responsive breakpoints (below 1024px single-column stacking) must remain functional
- Filter controls (category pills, status pills, type selects) must continue filtering correctly
- shadcn/ui components must not be modified
- The compliance page, which already follows the token system, must remain unchanged
- Dashboard shell sidebar (240px fixed width, nav items, active states) must remain unchanged

**Scope:**
All inputs that do NOT involve typography sizing, content truncation/clamping, element spacing, or panel fixed-widths should be completely unaffected by this fix. This includes:
- GSAP animation definitions and timing
- Color values and gradients
- Interactive event handlers (onClick, onChange)
- API service calls and data fetching
- Component structure and conditional rendering logic
- Icon sizes and SVG elements

## Hypothesized Root Cause

Based on the bug description, the most likely issues are:

1. **Incremental Design Drift**: Developers used arbitrary Tailwind values (text-[10px], text-[12px]) during rapid prototyping without referencing the @theme inline design tokens, leading to progressive deviation from the type scale

2. **Misapplication of Monospace Token**: `text-code-sm` (13px) was used for body content that should use `text-label-ui` (14px) or `text-body-md` (16px), conflating monospace data display with human-readable labels

3. **Aggressive Space Optimization**: To fit more content visually, developers used sub-minimum spacing (gap-0.5 = 2px, space-y-0.5 = 2px) and content hiding (line-clamp-2, truncate + max-width) rather than letting content breathe with the token scale

4. **Fixed-Width Panel Design**: The trends page side panels were designed with fixed pixel widths (380px left, 320px right = 700px consumed) without considering that this leaves insufficient center column width on standard 1024px–1440px displays

## Correctness Properties

Property 1: Bug Condition - Typography Token Compliance

_For any_ text element in a dashboard page where the current font size is below `text-label-ui` (14px) and the content is human-readable UI text (not monospace technical data), the fixed code SHALL render that element using `text-label-ui` (14px) or higher from the design token scale, ensuring all human-readable text meets the minimum readability threshold.

**Validates: Requirements 2.1, 2.6, 2.7, 2.8**

Property 2: Bug Condition - Content Visibility

_For any_ primary content element (descriptions, titles, impact text) where `line-clamp-2` or `truncate max-w-[170px]` is applied, the fixed code SHALL remove the restrictive clamping/truncation and allow the content to display fully using appropriate line heights and wrapping.

**Validates: Requirements 2.2, 2.3**

Property 3: Bug Condition - Spacing Token Compliance

_For any_ spacing declaration (gap, space-y, mt) between related content items where the current value is below `stack-sm` (8px), the fixed code SHALL use `stack-sm` (8px) as the minimum spacing between related items and `stack-md` (16px) between sections.

**Validates: Requirements 2.4**

Property 4: Bug Condition - Proportional Layout

_For any_ multi-column layout where fixed-width side panels squeeze the center reading column below 480px on standard desktops (1024px–1440px), the fixed code SHALL use proportional or flexible column sizing that maintains minimum readable center width.

**Validates: Requirements 2.5**

Property 5: Preservation - Animation and Interaction Integrity

_For any_ GSAP animation definition, hover state, active state, dark mode style, responsive breakpoint, or filter control, the fixed code SHALL produce exactly the same behavior as the original code, preserving all animation timing, visual effects, and interactive functionality.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `frontend/src/pages/home.tsx`

**Specific Changes**:
1. **AI Engine Active badge**: Replace `text-[12px]` with `text-label-ui`
2. **Activity timestamps**: Replace `text-[10px]` with `text-code-xs` (appropriate for monospace time data)
3. **Activity descriptions**: Replace `text-[12px]` with `text-label-ui`
4. **Activity item spacing**: Replace `space-y-0.5` with `gap-stack-sm` (using the 8px token)
5. **Stat card subtitles**: Replace `text-code-sm` with `text-label-ui` (non-code body content)
6. **Activity icon margin**: Replace `mt-0.5` with appropriate token-based spacing

**File**: `frontend/src/pages/trends.tsx`

**Specific Changes**:
1. **Left column width**: Replace `lg:w-[380px]` with proportional flex (e.g., `lg:w-1/4` or `lg:basis-[300px] lg:shrink-0`)
2. **Right column width**: Replace `lg:w-[320px]` with proportional flex (e.g., `lg:w-1/4` or `lg:basis-[280px] lg:shrink-0`)
3. **Signal descriptions**: Replace `text-[12px] line-clamp-2` with `text-label-ui` (remove line-clamp-2)
4. **Category/risk badges**: Replace `text-[10px]` with `text-code-xs` (11px)
5. **Header subtitle**: Replace `text-[12px]` with `text-label-ui`
6. **Briefcase panel description**: Replace `text-[12px]` with `text-label-ui`
7. **Briefcase item descriptions**: Remove `line-clamp-2` from impact text
8. **Onboarding banner description**: Replace `text-[12.5px]` with `text-label-ui`

**File**: `frontend/src/pages/campaigns.tsx`

**Specific Changes**:
1. **Campaign titles**: Remove `truncate max-w-[170px]`, allow natural wrapping
2. **Market text**: Replace `text-[12px]` with `text-label-ui`
3. **Status badges**: Replace `text-[10px]` with `text-code-xs`
4. **Campaign card spacing**: Replace `mb-1.5` with `mb-stack-sm` equivalent where needed

**File**: `frontend/src/pages/assets.tsx`

**Specific Changes**:
1. **Specs grid labels**: Replace `text-[10px]` with `text-label-ui`
2. **Specs grid values**: Replace `text-xs` (12px) with `text-label-ui` (14px)
3. **Tag text**: Replace `text-[10px]` with `text-code-xs` (11px, monospace appropriate for tags)
4. **Compliance description**: Replace `text-[12px]` with `text-label-ui`
5. **Campaign subtitle spacing**: Replace `mt-0.5` with `mt-stack-sm` equivalent
6. **Specs grid internal spacing**: Replace `space-y-0.5` with `space-y-1` or `gap-stack-sm`
7. **Compliance badge**: Replace `text-[9px]` with `text-code-xs` (11px)

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code by scanning for sub-minimum token usage, then verify the fix applies correct tokens and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write a script or test that greps all dashboard page files for hardcoded sub-minimum sizes (text-[10px], text-[12px], text-[9px]), restrictive truncation patterns (truncate max-w-[170px]), content hiding (line-clamp-2 on non-overflow content), and sub-minimum spacing (gap-0.5, space-y-0.5, mt-0.5). Run on UNFIXED code to catalog all violations.

**Test Cases**:
1. **Typography Audit**: Scan home.tsx, trends.tsx, campaigns.tsx, assets.tsx for text-[10px], text-[12px], text-[9px] classes (will find multiple violations on unfixed code)
2. **Truncation Audit**: Scan for `max-w-[170px]` combined with `truncate` (will find violation in campaigns.tsx)
3. **Line-Clamp Audit**: Scan for `line-clamp-2` on primary content descriptions (will find violations in trends.tsx)
4. **Spacing Audit**: Scan for `space-y-0.5`, `gap-0.5`, `mt-0.5` in content areas (will find violations across pages)
5. **Fixed-Width Panel Audit**: Check trends.tsx for `w-[380px]` and `w-[320px]` (will find violation)

**Expected Counterexamples**:
- Multiple instances of text-[10px] and text-[12px] in all four page files
- Campaign titles constrained to 170px max-width
- Possible causes: design drift during rapid prototyping, copy-paste of arbitrary values

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL element WHERE isBugCondition(element) DO
  result := renderElement_fixed(element)
  ASSERT result.computedFontSize >= 14px OR (result.fontFamily == 'JetBrains Mono' AND result.computedFontSize >= 11px)
  ASSERT NOT result.hasClass('line-clamp-2') WHEN element.isType('primaryContent')
  ASSERT NOT (result.hasClass('truncate') AND result.hasClass('max-w-[170px]'))
  ASSERT result.computedSpacing >= 8px WHEN element.spacingType IN ['gap', 'space-y']
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL element WHERE NOT isBugCondition(element) DO
  ASSERT renderElement_original(element) = renderElement_fixed(element)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain (various viewport sizes, theme modes, data states)
- It catches edge cases that manual unit tests might miss (empty data, long strings, single items)
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for GSAP animations, hover states, dark mode rendering, and filter interactions, then write tests capturing that behavior remains identical after the fix.

**Test Cases**:
1. **GSAP Animation Preservation**: Verify that all useGSAP hooks produce the same animation timelines (same selectors, durations, easings, staggers) before and after fix
2. **Dark Mode Preservation**: Verify that dark: variant classes remain unchanged and render correctly
3. **Responsive Layout Preservation**: Verify that mobile breakpoint behavior (stacking, overflow scroll) remains unchanged
4. **Filter Interaction Preservation**: Verify that filter pill clicks and select changes produce same filtering results

### Unit Tests

- Verify each page file contains no instances of text-[10px], text-[12px], or text-[9px] for non-monospace content after fix
- Verify campaign titles no longer have max-w-[170px] constraint
- Verify trends signal descriptions no longer have line-clamp-2
- Verify all spacing values meet stack-sm (8px) minimum
- Verify trends layout uses proportional widths instead of fixed pixel panels

### Property-Based Tests

- Generate random viewport widths (1024px–1920px) and verify center column in trends maintains ≥480px readable width
- Generate random campaign title lengths and verify no truncation at 170px occurs
- Generate random activity lists and verify spacing between items is always ≥8px
- Generate random theme states (light/dark) and verify GSAP animation selectors remain unchanged

### Integration Tests

- Render each dashboard page and verify no computed font size falls below 14px for Hanken Grotesk text
- Render trends page at 1280px width and verify center column has adequate reading width
- Toggle dark mode on each page and verify visual consistency maintained
- Trigger GSAP animations and verify entrance animations still play correctly
