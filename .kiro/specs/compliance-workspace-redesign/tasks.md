# Implementation Plan: Compliance Workspace Redesign

## Overview

Transform the compliance page from a flat "upload → table → detail panel" layout into a step-based, project-centric workspace. Each compliance check becomes a navigable Project progressing through Upload → Check → Review → Remix → Compare steps. Implementation uses React 19, TypeScript, Tailwind CSS 4, shadcn/ui, and GSAP with `@gsap/react`. All existing hooks and API services remain unchanged.

## Tasks

- [x] 1. Define new TypeScript types and constants
  - [x] 1.1 Extend `src/types/compliance.ts` with new types
    - Add `WorkflowStep`, `StepDefinition`, `Project`, `ProjectError`, `ProjectAction`, and `ProjectStore` types
    - Add the `WORKFLOW_STEPS` constant array
    - Keep all existing types (`QueueItem`, `UploadParams`, `QueueAction`, etc.) intact for backward compatibility
    - _Requirements: 12.4, 1.1, 1.2, 2.1_

- [x] 2. Implement project state reducer
  - [x] 2.1 Create `projectReducer` function in `src/pages/compliance.tsx` (or a dedicated file imported by it)
    - Implement all `ProjectAction` cases: `CREATE_PROJECT`, `SET_ACTIVE_PROJECT`, `ADVANCE_STEP`, `SET_RESULT`, `SET_REMIX_RESULT`, `SET_ERROR`, `CLEAR_ERROR`, `NAVIGATE_TO_STEP`
    - Enforce state transition rules: `NAVIGATE_TO_STEP` only allows steps in `completedSteps`; `SET_RESULT` auto-advances to "review"; `SET_REMIX_RESULT` auto-advances to "compare"
    - _Requirements: 1.1, 1.2, 2.3, 2.4, 2.5, 2.6_

  - [x]* 2.2 Write property test: Project creation produces unique ID and correct initial state
    - **Property 1: Project creation produces unique ID and correct initial state**
    - **Validates: Requirements 1.1, 3.2**

  - [x]* 2.3 Write property test: Project data round-trip across navigation
    - **Property 2: Project data round-trip across navigation**
    - **Validates: Requirements 1.2, 1.3, 8.2**

  - [x]* 2.4 Write property test: Step state classification
    - **Property 4: Step state classification**
    - **Validates: Requirements 2.2**

  - [x]* 2.5 Write property test: Step navigation rules
    - **Property 5: Step navigation rules**
    - **Validates: Requirements 2.3, 2.4**

  - [x]* 2.6 Write property test: Auto-advancement on stream completion
    - **Property 6: Auto-advancement on stream completion**
    - **Validates: Requirements 2.5, 2.6**

- [x] 3. Build StepNavigator component
  - [x] 3.1 Create `src/components/compliance/StepNavigator.tsx`
    - Render five steps (Upload, Check, Review, Remix, Compare) as an ordered list inside a `<nav>` element
    - Visually distinguish active, completed, and unreachable steps using Tailwind semantic tokens
    - Implement keyboard navigation: Tab to focus, Enter/Space to activate completed steps, `tabIndex={-1}` on unreachable steps
    - Set `aria-current="step"` on the active step, `aria-disabled="true"` on unreachable steps
    - Animate active indicator slide on step change using `useGSAP` with scoped container ref (duration 0.3s, property `x` + `opacity`)
    - Accept props: `steps`, `currentStep`, `completedSteps`, `onStepClick`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 9.1, 10.1, 10.2_

  - [x]* 3.2 Write property test: StepNavigator ARIA correctness
    - **Property 14: Step_Navigator ARIA correctness**
    - **Validates: Requirements 10.2**

- [x] 4. Build ProjectSidebar component
  - [x] 4.1 Create `src/components/compliance/ProjectSidebar.tsx`
    - Render all projects in descending `createdAt` order (newest first)
    - Each entry displays: campaign name, media type icon, risk level colored dot (red/amber/green), current step indicator, error indicator when applicable
    - Highlight the active project with background emphasis
    - Use `role="listbox"` on container, `role="option"` on each entry, `aria-selected="true"` on the active project
    - Keyboard navigation: Tab/Arrow keys to move between projects, Enter to select
    - GSAP animation for new project entrance: slide down + fade in (duration 0.3s, properties `y` + `opacity`)
    - GSAP animation for selection change: background emphasis transition (duration 0.2s, `autoAlpha`)
    - Accept props: `projects`, `activeProjectId`, `onSelectProject`
    - _Requirements: 1.4, 1.5, 8.1, 8.2, 8.3, 8.4, 8.5, 9.4, 10.3, 10.4, 11.1_

  - [x]* 4.2 Write property test: Sidebar ordering and field display
    - **Property 3: Sidebar ordering and field display**
    - **Validates: Requirements 1.4, 8.3**

  - [x]* 4.3 Write property test: Active project highlight exclusivity
    - **Property 13: Active project highlight exclusivity**
    - **Validates: Requirements 8.4**

  - [x]* 4.4 Write property test: ProjectSidebar ARIA roles
    - **Property 15: Project_Sidebar ARIA roles**
    - **Validates: Requirements 10.4**

  - [x]* 4.5 Write property test: Sidebar visibility rules
    - **Property 12: Sidebar visibility rules**
    - **Validates: Requirements 8.1**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Build UploadStep component
  - [x] 6.1 Create `src/components/compliance/UploadStep.tsx`
    - Render the existing `UploadForm` component, passing through `onSubmit` and `isSubmitting` props
    - Display error state with error message and retry button when `error` prop is non-null and `retryable` is true
    - Use consistent error banner pattern: `role="alert"`, `bg-error-container` styling, material icon
    - Accept props: `onSubmit`, `isSubmitting`, `error`, `onRetry`
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 7. Build CheckStep component
  - [x] 7.1 Create `src/components/compliance/CheckStep.tsx`
    - Render `PipelineStatusIndicator` component with streaming node statuses
    - Include an `aria-live="polite"` region that announces node status changes to screen readers
    - Display error state with retry button when stream fails
    - Accept props: `nodeStatuses`, `currentNode`, `isStreaming`, `mediaType`, `error`, `onRetry`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.5_

  - [x]* 7.2 Write property test: Pipeline node status display completeness
    - **Property 7: Pipeline node status display completeness**
    - **Validates: Requirements 4.1, 6.4**

  - [x]* 7.3 Write property test: Retry re-submits original parameters
    - **Property 8: Retry re-submits original parameters**
    - **Validates: Requirements 4.5**

- [x] 8. Build ReviewStep component
  - [x] 8.1 Create `src/components/compliance/ReviewStep.tsx`
    - Display compliance score with GSAP count-up animation from 0 to final value (duration 1.5s, `snap: { textContent: 1 }`)
    - Display risk level with color coding: red/error for "High", amber for "Medium", green/emerald for "Low"
    - Display explanation text from the compliance result
    - Render all violations with: category heading, severity badge, type label, description body, `ViolationClipPlayer` when `clip_url` is non-null
    - Stagger violation card entrance using GSAP (duration 0.35s, stagger 0.08s, properties `y` + `opacity`)
    - Show a success state when no violations exist
    - Display exactly one "Auto-Remix" button when violations exist; zero when no violations
    - No "Fix issues with AI" button anywhere
    - Accept props: `result`, `onStartRemix`, `isRemixAvailable`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 9.3, 9.4, 9.5, 11.1_

  - [x]* 8.2 Write property test: Risk level to color mapping
    - **Property 9: Risk level to color mapping**
    - **Validates: Requirements 5.2**

  - [x]* 8.3 Write property test: Violation rendering completeness
    - **Property 10: Violation rendering completeness**
    - **Validates: Requirements 5.4**

  - [x]* 8.4 Write property test: Remix button presence
    - **Property 11: Remix button presence**
    - **Validates: Requirements 6.1**

- [x] 9. Build RemixStep component
  - [x] 9.1 Create `src/components/compliance/RemixStep.tsx`
    - Render `PipelineStatusIndicator` for remix pipeline progress (reuse same component as CheckStep)
    - Include an `aria-live="polite"` region for screen reader announcements
    - Display error state with retry button when remix stream fails
    - Show success indicator when remix completes
    - Accept props: `remixNodes`, `isRemixing`, `remixComplete`, `remixError`, `onRetry`
    - _Requirements: 6.3, 6.4, 6.5, 10.5_

- [x] 10. Build ComparisonView component
  - [x] 10.1 Create `src/components/compliance/ComparisonView.tsx`
    - Render two-panel grid layout: original on left, remixed on right
    - Left panel: original violations list with severity and description, original compliance score, `ViolationClipPlayer` for clips
    - Right panel: remixed result details, remixed score when available, "Compliant" badge when score not available
    - Label panels with `aria-label`: "Original content with violations" (left) and "Remixed compliant version" (right)
    - GSAP panel entrance: left slides from left, right slides from right (duration 0.5s, property `x` + `opacity`)
    - Accept props: `originalResult`, `remixResult`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 9.4, 9.5, 10.6, 11.1_

- [x] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Rewrite compliance.tsx as ComplianceWorkspace orchestrator
  - [x] 12.1 Rewrite `src/pages/compliance.tsx` as the ComplianceWorkspace
    - Replace the existing `queueReducer` with `projectReducer` using `useReducer`
    - Wire existing hooks: `useComplianceCheck()` and `useComplianceRemix()` — no API changes
    - Implement `handleSubmit`: create project via `CREATE_PROJECT`, call `complianceCheck.submit()`, dispatch `SET_RESULT` on success or `SET_ERROR` on failure
    - Implement `handleStartRemix`: dispatch `ADVANCE_STEP` to "remix", call `remix.startRemix()`, dispatch `SET_REMIX_RESULT` on success or `SET_ERROR` on failure
    - Implement `handleRetry` for both check and remix errors using stored `uploadParams`
    - Conditionally render the correct step component based on active project's `currentStep`
    - Show `ProjectSidebar` on all steps except Upload step when no projects exist
    - Show `StepNavigator` with current project's step state
    - Animate step transitions: outgoing content fades out (duration 0.2s), incoming fades in (duration 0.4s) using GSAP timeline with `useGSAP`
    - Use semantic color tokens throughout; no hardcoded colors
    - Import path aliases (`@/`) for all imports
    - _Requirements: 1.1, 1.2, 1.3, 2.5, 2.6, 3.2, 4.5, 6.3, 8.1, 9.2, 9.4, 11.1, 11.2, 11.3, 12.3, 12.5_

- [x] 13. Remove deprecated components
  - [x] 13.1 Remove deprecated component files
    - Delete `src/components/compliance/SummaryCards.tsx`
    - Delete `src/components/compliance/ReviewQueueTable.tsx`
    - Delete `src/components/compliance/DetailPanel.tsx`
    - Remove any unused imports referencing these components from other files
    - Verify build still compiles cleanly after removal
    - _Requirements: 12.2_

- [x] 14. Final verification and dark/light mode pass
  - [x] 14.1 Verify dark/light mode compatibility and lint
    - Run `npm run lint` and `npm run build` from `frontend/` to confirm no errors
    - Audit all new components for hardcoded color values; replace any found with semantic tokens
    - Ensure all Tailwind classes use semantic tokens (`text-text-primary`, `bg-surface-panel`, `border-border-default`, etc.)
    - Verify no modifications to `src/components/ui/` files
    - _Requirements: 11.1, 11.2, 11.3, 12.1_

- [x] 15. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using fast-check (minimum 100 iterations)
- Unit tests validate specific examples and edge cases
- All GSAP animations use `useGSAP` hook with scoped container refs per project conventions
- Existing hooks (`useComplianceCheck`, `useComplianceRemix`) and services (`complianceApi`) are reused without modification
- The `projectReducer` replaces the existing `queueReducer` — the old reducer code is removed when compliance.tsx is rewritten

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5", "2.6", "3.1", "4.1"] },
    { "id": 3, "tasks": ["3.2", "4.2", "4.3", "4.4", "4.5", "6.1", "7.1", "8.1", "9.1", "10.1"] },
    { "id": 4, "tasks": ["7.2", "7.3", "8.2", "8.3", "8.4"] },
    { "id": 5, "tasks": ["12.1"] },
    { "id": 6, "tasks": ["13.1"] },
    { "id": 7, "tasks": ["14.1"] }
  ]
}
```
