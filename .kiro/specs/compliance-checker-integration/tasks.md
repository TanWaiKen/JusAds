# Implementation Plan: Compliance Checker Integration

## Overview

This plan integrates the LangGraph compliance backend into the React frontend by fixing the existing API service, creating a custom SSE streaming hook, building Figma-aligned UI components, and wiring everything together with GSAP animations. Tasks are ordered to establish foundations first (types, API fixes, hook), then build components bottom-up, and finally integrate at the page level.

## Tasks

- [x] 1. Fix API service and establish shared types
  - [x] 1.1 Fix `complianceApi.ts` endpoint URL and FormData field
    - Change `checkComplianceStream` URL from `/api/compliance/check/stream` to `/api/compliance/check`
    - Change FormData field from `"video"` to `"file"` to match backend's expected field name
    - Add text submission support (append `"text"` field when no file provided)
    - Export `API_BASE` constant for use by other modules
    - _Requirements: 1.4, 1.5_

  - [x] 1.2 Create shared TypeScript interfaces for queue state
    - Create `frontend/src/types/compliance.ts` with `QueueItem`, `ViolationFlag`, `RiskLevel`, `UploadParams`, `QueueAction`, and `ErrorState` interfaces from design
    - Export all types for use across components
    - _Requirements: 7.1, 6.1_

  - [x] 1.3 Create `useComplianceCheck` custom hook
    - Create `frontend/src/hooks/useComplianceCheck.ts`
    - Implement SSE stream consumption via fetch + ReadableStream reader
    - Track `nodeStatuses` array, `currentNode`, `isStreaming`, and `error` state
    - Implement `submit(params: UploadParams)` that constructs FormData and calls `/api/compliance/check`
    - Implement `retry()` function that re-submits last params
    - Handle stream failure/timeout with error state
    - _Requirements: 2.1, 2.5, 2.6, 9.2, 9.3_

  - [ ]* 1.4 Write property test for FormData construction (Property 2)
    - **Property 2: FormData construction preserves all parameters**
    - **Validates: Requirements 1.4, 1.5**
    - Use fast-check to generate random file/text + market/ethnicity/ageGroup combinations
    - Assert FormData contains all expected fields with exact values

- [x] 2. Build Upload Form and Pipeline Status components
  - [x] 2.1 Create `UploadForm` component
    - Create `frontend/src/components/compliance/UploadForm.tsx`
    - Accept `video/*`, `image/*`, `audio/*` file types and text input
    - Display filename, media type icon (Material Symbols), and formatted file size on selection
    - Render dropdowns for market (default "malaysia"), ethnicity (default "malay"), age_group (default "all_ages")
    - Disable submit when no file/text provided or when `isSubmitting` is true
    - Validate file size < 100MB with warning message
    - Style with Figma design tokens: surface hierarchy, Hanken Grotesk, rounded-xl cards
    - _Requirements: 1.1, 1.2, 1.3, 1.6, 9.1, 9.4, 9.5, 10.4, 10.6_

  - [ ]* 2.2 Write property test for file preview metadata (Property 1)
    - **Property 1: File preview displays all metadata**
    - **Validates: Requirements 1.2**
    - Use fast-check to generate random filenames, MIME types, and file sizes
    - Assert rendered output contains filename, correct media icon, and formatted size

  - [x] 2.3 Create `PipelineStatusIndicator` component
    - Create `frontend/src/components/compliance/PipelineStatusIndicator.tsx`
    - Display pipeline nodes as horizontal sequence with Material Symbols icons
    - Color nodes: completed = emerald-glow, active = aurora-purple with pulse, pending = muted
    - Show only relevant nodes for detected media type path
    - Display current node description text below indicator
    - _Requirements: 2.2, 2.3, 2.4_

  - [ ]* 2.4 Write property test for pipeline node state classification (Property 3)
    - **Property 3: Pipeline node state classification**
    - **Validates: Requirements 2.2, 2.3**
    - Use fast-check to generate random subsets of pipeline nodes as "completed"
    - Assert correct classification of completed/active/pending for each node

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Build Summary Cards and Review Queue components
  - [x] 4.1 Create `SummaryCards` component
    - Create `frontend/src/components/compliance/SummaryCards.tsx`
    - Render four bento-grid cards: Ready to Publish, Needing Attention, Checks Pending, Top Risk Flags
    - "Needing Attention" card shows red left border and "HIGH RISK" badge when high-risk items exist
    - Implement GSAP staggered entrance with `useGSAP`: `gsap.from()` y: 30, opacity: 0, stagger: 0.1, duration: 0.5
    - Style with Figma design tokens: shadow-as-border, rounded-xl, surface hierarchy
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 8.1, 10.2, 10.4_

  - [ ]* 4.2 Write property test for summary card counts (Property 9)
    - **Property 9: Summary card counts derived from queue state**
    - **Validates: Requirements 6.1, 6.3**
    - Use fast-check to generate random arrays of QueueItems with mixed statuses
    - Assert counts match: passed → Ready, needs_changes → Attention, in_progress → Pending

  - [x] 4.3 Create `ReviewQueueTable` component
    - Create `frontend/src/components/compliance/ReviewQueueTable.tsx`
    - Display columns: Campaign & Asset (thumbnail), Platform icons, Risk Level badge, Flags (colored dots), Status, Last Checked
    - Highlight selected row with `aurora-border-active` style (box-shadow: 0 0 0 2px #7928ca)
    - Provide "Filter by Risk Level" dropdown (All, High, Medium, Low)
    - Show "In progress" status with animated spinner for active checks
    - Animate rows with GSAP staggered entrance after summary cards using `useGSAP`
    - Style flag dots: `w-2 h-2 rounded-full` with bg-error, bg-ship-red, bg-amber-500
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 8.2, 10.5, 10.10, 10.11_

  - [ ]* 4.4 Write property test for risk level badge color mapping (Property 4)
    - **Property 4: Risk level badge color mapping**
    - **Validates: Requirements 3.2, 10.5**
    - Use fast-check to generate random risk level values
    - Assert correct CSS classes for each risk level

  - [ ]* 4.5 Write property test for selected row highlighting (Property 10)
    - **Property 10: Selected row highlighting exclusivity**
    - **Validates: Requirements 7.3, 10.10**
    - Use fast-check to generate random queue arrays + random selected ID
    - Assert exactly one row has aurora-border-active style

  - [ ]* 4.6 Write property test for risk level filter (Property 11)
    - **Property 11: Risk level filter correctness**
    - **Validates: Requirements 7.4**
    - Use fast-check to generate random queue arrays + random filter value
    - Assert displayed rows match filter criteria

- [x] 5. Build Detail Panel with tabs and Violation Clip Player
  - [x] 5.1 Create `ViolationClipPlayer` component
    - Create `frontend/src/components/compliance/ViolationClipPlayer.tsx`
    - Render HTML5 video player with clip source resolved against API_BASE
    - Display timestamp range (start–end seconds)
    - Show "Clip unavailable" indicator when clip_url is null
    - Standard video controls for inline playback
    - _Requirements: 4.2, 4.3, 4.4, 4.5_

  - [x] 5.2 Create `DetailPanel` component with Issues and AI Suggestions tabs
    - Create `frontend/src/components/compliance/DetailPanel.tsx`
    - Render two tabs: "Issues" and "AI Suggestions" matching Figma layout
    - Issues tab: list violations with category, severity border color (error=red, warning=amber), description
    - Issues tab: include "Fix issues with AI" button
    - AI Suggestions tab: render suggestion cards with "Original" (strikethrough, muted) and "Suggested" columns, "Apply" and "Keep" buttons
    - Pinned footer with "Mark as resolved & re-run" button
    - Success state when zero violations
    - Animate content with fade-in + y-offset on tab/item switch using `useGSAP`
    - Style with Figma tokens: uppercase code-xs labels, two-column grid, primary/secondary buttons
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 8.4, 10.4, 10.6, 10.12_

  - [ ]* 5.3 Write property test for violation card rendering (Property 6)
    - **Property 6: Violation card renders all fields with resolved clip URL**
    - **Validates: Requirements 4.1, 4.2, 4.4**
    - Use fast-check to generate random Violation objects with/without clip_url
    - Assert card contains category, severity, type, description, timestamp, and correct video src

  - [ ]* 5.4 Write property test for violation severity color mapping (Property 7)
    - **Property 7: Violation severity and category to color mapping**
    - **Validates: Requirements 5.2, 10.11**
    - Use fast-check to generate random violations with different severity/category values
    - Assert correct border color and flag dot color classes

  - [ ]* 5.5 Write property test for AI suggestion card structure (Property 8)
    - **Property 8: AI suggestion card structure**
    - **Validates: Requirements 5.3, 10.12**
    - Use fast-check to generate random suggestion objects
    - Assert card contains uppercase label, two-column grid, strikethrough original, Apply/Keep buttons

  - [ ]* 5.6 Write property test for compliance result fields (Property 5)
    - **Property 5: Compliance result fields rendered**
    - **Validates: Requirements 3.3, 3.4, 3.5, 3.6**
    - Use fast-check to generate random ComplianceResult objects
    - Assert all four fields (explanation, suggestion, processing_time, persona) are rendered

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Integrate page component and wire everything together
  - [x] 7.1 Rewrite `compliance.tsx` page component
    - Replace entire `compliance.tsx` with new implementation using real components
    - Implement queue state with `useReducer` and `QueueAction` types
    - Wire `useComplianceCheck` hook for submissions
    - Compose: SummaryCards, UploadForm, PipelineStatusIndicator, ReviewQueueTable, DetailPanel
    - Implement selected item state and pass to DetailPanel
    - Handle re-run flow: "Mark as resolved & re-run" triggers new submission
    - Use Layout Shell structure: main content area with `max-w-[1200px]`, `mx-auto`, `p-margin-page`
    - Responsive: stack ReviewQueueTable and DetailPanel vertically below `lg` breakpoint
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 7.2, 8.3, 8.5, 9.4, 10.1, 10.2, 10.3, 10.7, 10.8, 10.9, 10.13_

  - [x] 7.2 Implement GSAP page-level animations
    - Score count-up animation: `gsap.to()` from 0 to final score value
    - Summary cards staggered entrance on mount
    - Queue rows staggered entrance after cards complete
    - Detail panel fade-in + y-offset on selection change
    - Use `useGSAP` with scoped container ref for all animations
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 7.3 Remove mock `complianceService.ts`
    - Delete or empty `frontend/src/services/complianceService.ts` (no longer needed)
    - Remove any remaining imports of `complianceService` from the codebase
    - _Requirements: All (replaces mock with real integration)_

- [-] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The existing `complianceApi.ts` types (ComplianceResult, NodeStatus, Violation, etc.) are reused — no duplication
- GSAP animations follow the `useGSAP` hook pattern with scoped container refs per project conventions
- All components use Figma design tokens: aurora-purple, surface hierarchy, Hanken Grotesk, Material Symbols Outlined

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1"] },
    { "id": 2, "tasks": ["1.4", "2.2", "2.3"] },
    { "id": 3, "tasks": ["2.4", "4.1", "4.3"] },
    { "id": 4, "tasks": ["4.2", "4.4", "4.5", "4.6", "5.1"] },
    { "id": 5, "tasks": ["5.2"] },
    { "id": 6, "tasks": ["5.3", "5.4", "5.5", "5.6"] },
    { "id": 7, "tasks": ["7.1"] },
    { "id": 8, "tasks": ["7.2", "7.3"] }
  ]
}
```
