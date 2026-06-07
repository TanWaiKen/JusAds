# Requirements Document

## Introduction

Redesign the compliance page from a flat "upload → table" layout into a step-by-step project-based workflow. Each compliance check becomes a navigable "project" with a unique `check_id`. The new flow guides users through Upload → Check → Review → Remix → Compare steps, eliminating duplicate remix affordances and adding a side-by-side comparison view for original vs. remixed content.

This is a frontend-only redesign. The backend API contract (`POST /api/compliance/check` and `POST /api/compliance/{check_id}/remix`) remains unchanged.

## Glossary

- **Compliance_Workspace**: The redesigned page component that replaces the current flat compliance page, organizing each compliance check as a navigable project with step-based progression.
- **Project**: A single compliance check session identified by a `check_id`, persisted in client state so the user can navigate between past and current checks.
- **Step_Navigator**: A visual stepper component that displays the current workflow step (Upload, Check, Review, Remix, Compare) and allows navigation between completed steps.
- **Review_View**: A focused single-project view that displays violations, compliance score, and risk level for one check at a time, replacing the table-based review pattern.
- **Comparison_View**: A side-by-side layout showing the original content with its violations alongside the remixed compliant version.
- **Project_Sidebar**: A navigation panel listing all compliance check projects, allowing the user to switch between them.
- **Auto_Remix_Action**: The single unified remix trigger that replaces the current duplicate "Remix It" button and "Fix issues with AI" button.
- **Pipeline_Progress**: The streaming progress indicator that shows LangGraph node statuses during the Check and Remix steps.

## Requirements

### Requirement 1: Project-Based State Management

**User Story:** As a compliance reviewer, I want each compliance check to be treated as an independent project with its own state, so that I can navigate between checks without losing progress.

#### Acceptance Criteria

1. WHEN a new compliance check is submitted, THE Compliance_Workspace SHALL create a new Project with a unique `check_id` and set its initial step to "check".
2. THE Compliance_Workspace SHALL persist all Project data (check_id, step, result, remix result) in client-side state so projects survive navigation between them.
3. WHEN the user selects a Project from the Project_Sidebar, THE Compliance_Workspace SHALL restore that Project's current step and display its associated data.
4. THE Project_Sidebar SHALL display all Projects ordered by creation time (newest first) with their campaign name, media type icon, risk level badge, and current step indicator.
5. WHEN a Project is in an error state, THE Project_Sidebar SHALL display an error indicator on that Project's entry.

### Requirement 2: Step-Based Workflow Navigation

**User Story:** As a compliance reviewer, I want to follow a clear progression through Upload → Check → Review → Remix → Compare steps, so that I always know where I am in the compliance process.

#### Acceptance Criteria

1. THE Step_Navigator SHALL display five steps in order: Upload, Check, Review, Remix, Compare.
2. THE Step_Navigator SHALL visually distinguish the current active step, completed steps, and steps not yet reached.
3. WHEN the user clicks a completed step in the Step_Navigator, THE Compliance_Workspace SHALL navigate back to that step's view within the current Project.
4. THE Step_Navigator SHALL prevent navigation to steps that have not been reached (forward-only progression unless a step is already completed).
5. WHEN the compliance check stream completes successfully, THE Compliance_Workspace SHALL automatically advance the Project from the "check" step to the "review" step.
6. WHEN the remix stream completes successfully, THE Compliance_Workspace SHALL automatically advance the Project from the "remix" step to the "compare" step.

### Requirement 3: Upload Step

**User Story:** As a compliance reviewer, I want to upload a file or paste text to start a new compliance check, so that I can initiate the workflow.

#### Acceptance Criteria

1. THE Compliance_Workspace SHALL reuse the existing UploadForm component for the Upload step.
2. WHEN the user submits the Upload form, THE Compliance_Workspace SHALL transition to the Check step and begin streaming the compliance pipeline.
3. IF the upload form submission fails due to a network error, THEN THE Compliance_Workspace SHALL display an error message with a retry option and remain on the Upload step.

### Requirement 4: Check Step with Streaming Progress

**User Story:** As a compliance reviewer, I want to see real-time progress of the compliance pipeline, so that I know which analysis stages are running or complete.

#### Acceptance Criteria

1. WHILE the compliance check is streaming, THE Pipeline_Progress SHALL display each LangGraph node's status (running, completed, error) with its description.
2. WHILE the compliance check is streaming, THE Step_Navigator SHALL show the "Check" step as active with a loading indicator.
3. WHEN a node status event is received from the SSE stream, THE Pipeline_Progress SHALL update that node's display within 100 milliseconds.
4. IF the compliance check stream fails, THEN THE Compliance_Workspace SHALL display an error state with the error message and a retry button.
5. WHEN the retry button is clicked, THE Compliance_Workspace SHALL re-submit the original upload parameters to the compliance API.

### Requirement 5: Review Step — Focused Single-Project View

**User Story:** As a compliance reviewer, I want to see violations, score, and risk level in a focused view for one check at a time, so that I can review results without distraction from other checks.

#### Acceptance Criteria

1. THE Review_View SHALL display the compliance score with a GSAP count-up animation from 0 to the final value.
2. THE Review_View SHALL display the risk level (High, Medium, Low) with the corresponding color coding (red, amber, green).
3. THE Review_View SHALL display the explanation text from the compliance result.
4. THE Review_View SHALL list all violations with their category, severity badge, type label, description, and clip player (when clip_url is available).
5. WHEN no violations are found, THE Review_View SHALL display a success state indicating the asset passed all checks.
6. THE Review_View SHALL NOT display a table of multiple compliance checks; it shows only the currently selected Project's results.

### Requirement 6: Single Unified Remix Action

**User Story:** As a compliance reviewer, I want one clear "Auto-Remix" action to generate a compliant version, so that I am not confused by multiple remix buttons doing the same thing.

#### Acceptance Criteria

1. THE Review_View SHALL display exactly one Auto_Remix_Action button when violations exist in the current Project.
2. THE Compliance_Workspace SHALL NOT display a separate "Fix issues with AI" button anywhere in the interface.
3. WHEN the user clicks the Auto_Remix_Action button, THE Compliance_Workspace SHALL transition to the Remix step and begin streaming the remix pipeline via `POST /api/compliance/{check_id}/remix`.
4. WHILE the remix is streaming, THE Pipeline_Progress SHALL display each remix node's status (running, completed, error) with its description.
5. IF the remix stream fails, THEN THE Compliance_Workspace SHALL display an error message with a retry option on the Remix step.

### Requirement 7: Comparison View — Original vs. Remixed

**User Story:** As a compliance reviewer, I want to see the original content with its violations side-by-side with the remixed compliant version, so that I can verify the fixes are acceptable.

#### Acceptance Criteria

1. THE Comparison_View SHALL display a two-panel layout: original content on the left and remixed content on the right.
2. THE Comparison_View SHALL show the original violations list on the left panel with their severity and description.
3. THE Comparison_View SHALL show the remixed result (compliant version details) on the right panel.
4. THE Comparison_View SHALL display the original compliance score on the left and the remixed compliance score on the right (when available from the remix result).
5. WHEN the remix result does not include a new compliance score, THE Comparison_View SHALL display a "Compliant" badge on the right panel instead.
6. THE Comparison_View SHALL animate the panel entrance using GSAP (left panel slides in from left, right panel slides in from right).

### Requirement 8: Project Sidebar Navigation

**User Story:** As a compliance reviewer, I want to navigate between multiple compliance check projects, so that I can manage ongoing work without losing any previous results.

#### Acceptance Criteria

1. THE Project_Sidebar SHALL be visible on all steps of the workflow except during the Upload step of a new project (when no projects exist yet).
2. WHEN the user clicks a Project in the Project_Sidebar, THE Compliance_Workspace SHALL switch the main content area to display that Project at its current step.
3. THE Project_Sidebar SHALL display each Project's campaign name (derived from filename or "Text Ad"), media type icon, and a colored dot indicating risk level.
4. THE Project_Sidebar SHALL highlight the currently active Project with a visual indicator (border or background emphasis).
5. WHEN a new Project is created, THE Project_Sidebar SHALL animate the new entry's entrance using GSAP (slide down + fade in).

### Requirement 9: GSAP Animation Integration

**User Story:** As a user, I want smooth, purposeful animations throughout the workflow, so that the interface feels polished and transitions are not jarring.

#### Acceptance Criteria

1. THE Step_Navigator SHALL animate step transitions using GSAP (active indicator slides to the new step position).
2. WHEN the main content area changes between steps, THE Compliance_Workspace SHALL animate the outgoing content fading out and incoming content fading in using GSAP with a duration between 0.3 and 0.5 seconds.
3. THE Review_View SHALL animate violation cards entrance with a staggered GSAP animation (stagger between 0.06 and 0.12 seconds).
4. ALL GSAP animations SHALL use the `useGSAP` hook from `@gsap/react` with a scoped container ref.
5. ALL GSAP animations SHALL animate only transform and opacity properties for performance (using `x`, `y`, `scale`, `opacity`, or `autoAlpha`).

### Requirement 10: Accessibility Preservation

**User Story:** As a user who relies on a keyboard or screen reader, I want the redesigned compliance workspace to remain fully accessible, so that I can complete compliance workflows without a mouse.

#### Acceptance Criteria

1. THE Step_Navigator SHALL be navigable via keyboard (Tab to focus steps, Enter/Space to activate completed steps).
2. THE Step_Navigator SHALL use `aria-current="step"` on the active step and `aria-disabled="true"` on unreachable steps.
3. THE Project_Sidebar SHALL be navigable via keyboard (Tab/Arrow keys to move between projects, Enter to select).
4. THE Project_Sidebar SHALL use `role="listbox"` with `role="option"` for each Project entry and `aria-selected` for the active project.
5. WHEN the Pipeline_Progress updates with new node statuses, THE Compliance_Workspace SHALL announce changes to screen readers via an `aria-live="polite"` region.
6. THE Comparison_View panels SHALL be labeled with `aria-label` attributes ("Original content with violations" and "Remixed compliant version").

### Requirement 11: Dark and Light Mode Support

**User Story:** As a user, I want the compliance workspace to look correct in both dark and light mode, so that my theme preference is respected.

#### Acceptance Criteria

1. THE Compliance_Workspace SHALL use only semantic color tokens from the project's design system (e.g., `text-text-primary`, `bg-surface-panel`, `border-border-default`) for all new components.
2. THE Compliance_Workspace SHALL NOT use hardcoded color values (e.g., `#ffffff`, `rgb(0,0,0)`) that would break in the opposite theme.
3. WHEN the user switches between dark and light mode, THE Compliance_Workspace SHALL update all colors immediately without requiring a page refresh.

### Requirement 12: Component Architecture Constraints

**User Story:** As a developer, I want the redesigned workspace to follow the project's component architecture, so that the codebase remains consistent and maintainable.

#### Acceptance Criteria

1. THE Compliance_Workspace SHALL NOT modify any files in `src/components/ui/` (shadcn primitives).
2. THE Compliance_Workspace SHALL create new components in `src/components/compliance/` for any new UI elements (Step_Navigator, Comparison_View, Project_Sidebar).
3. THE Compliance_Workspace SHALL reuse existing hooks (`useComplianceCheck`, `useComplianceRemix`) without modifying their public API.
4. THE Compliance_Workspace SHALL define all new TypeScript types in `src/types/compliance.ts`.
5. THE Compliance_Workspace SHALL use path aliases (`@/`) for all imports following existing project conventions.
