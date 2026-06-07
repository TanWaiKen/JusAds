# Requirements Document

## Introduction

This feature integrates the existing LangGraph-based compliance checking backend (`langgraph_api.py`) into the React frontend compliance page. The integration replaces the current mock data with real API calls, supports multi-modal file uploads (video, image, audio, text) with SSE streaming for real-time progress, and renders compliance results matching the Figma design. The UI displays a summary dashboard, active review queue, detail panel with Issues/AI Suggestions tabs, violation clip playback for video, and real-time node status updates during LangGraph processing.

## Glossary

- **Compliance_Page**: The React page component at `frontend/src/pages/compliance.tsx` that displays the compliance checking interface
- **LangGraph_API**: The FastAPI backend at `backend/langgraph_api.py` exposing `POST /api/compliance/check` and `GET /api/compliance/{check_id}`
- **SSE_Stream**: Server-Sent Events stream returned by the compliance check endpoint providing real-time node status updates
- **Node_Status_Event**: An SSE event of type `node_status` indicating a LangGraph node has completed processing (router, text_check, image_check, transcribe, video_check, parse_violations, extract_clips)
- **Result_Event**: An SSE event of type `result` containing the final compliance check response data
- **Compliance_Result**: The final response object containing check_id, score, risk_level, explanation, suggestion, violations, and processing metadata
- **Violation_Clip**: An extracted video segment corresponding to a detected violation, served as an MP4 file from the backend `/clips/` static mount
- **Detail_Panel**: The right-side panel in the Figma design showing asset details, Issues tab, AI Suggestions tab, and action buttons
- **Summary_Cards**: The four bento-grid cards at the top of the page showing Ready to Publish, Needing Attention, Checks Pending, and Top Risk Flags
- **Review_Queue**: The table listing all compliance check items with their campaign name, platform, risk level, flags, status, and last checked time
- **Upload_Form**: The UI component allowing users to select a file (video, image, audio) or enter text, choose market/ethnicity/age_group parameters, and submit for compliance checking
- **GSAP_Animation**: Animations using the GSAP library with the `useGSAP` hook following project conventions for page entrances, staggered card reveals, and score count-up effects
- **Figma_Design_System**: The set of HTML reference files in the `figma/` folder (home.html, compliance.html, assets.html, profile.html, campaign.html, trends.html) that define the canonical design tokens, layout structure, component patterns, and visual language for the application
- **Design_Tokens**: The color, spacing, typography, and border-radius values defined in the Tailwind config within the Figma reference files, including aurora-purple (#7928ca), cosmic-pink (#ff0080), emerald-glow (#50e3c2), ship-red (#ee0000), bg-dark (#0a0a0f), and the surface hierarchy (surface, surface-container-low, surface-container, surface-container-high, surface-container-highest, surface-container-lowest)
- **Layout_Shell**: The fixed sidebar (240px width) + sticky top navigation bar + main content area (max-width 1200px) structure used consistently across all Figma reference pages

## Requirements

### Requirement 1: Multi-Modal File Upload Submission

**User Story:** As a compliance reviewer, I want to upload video, image, audio, or text content for compliance checking, so that I can validate any ad asset type against Malaysian regulatory guidelines.

#### Acceptance Criteria

1. THE Upload_Form SHALL accept file uploads with MIME types `video/*`, `image/*`, and `audio/*`, and a text input field for plain text ads
2. WHEN a file is selected, THE Upload_Form SHALL display the filename, detected media type icon, and file size
3. THE Upload_Form SHALL provide dropdown selectors for market (default: "malaysia"), ethnicity (default: "malay"), and age_group (default: "all_ages") parameters
4. WHEN the user submits the form with a file, THE Compliance_Page SHALL send a `POST` request to `/api/compliance/check` with the file and parameters as `multipart/form-data`
5. WHEN the user submits the form with text only, THE Compliance_Page SHALL send a `POST` request to `/api/compliance/check` with the text and parameters as `multipart/form-data`
6. IF no file and no text is provided, THEN THE Upload_Form SHALL disable the submit button and display a validation message

### Requirement 2: SSE Streaming and Real-Time Node Status

**User Story:** As a compliance reviewer, I want to see real-time progress as the LangGraph pipeline processes my asset, so that I understand what stage the analysis is at and how long it takes.

#### Acceptance Criteria

1. WHEN a compliance check is submitted, THE Compliance_Page SHALL consume the SSE stream response from the LangGraph_API
2. WHEN a Node_Status_Event is received, THE Compliance_Page SHALL update the processing UI to show the completed node name and its description
3. THE Compliance_Page SHALL display a visual pipeline indicator showing the sequence of nodes (router → check → parse → extract) with completed/active/pending states
4. WHILE the SSE stream is active, THE Compliance_Page SHALL display a loading state with the current node description text
5. WHEN the Result_Event is received, THE Compliance_Page SHALL transition from the loading state to displaying the full compliance results
6. IF the SSE stream connection fails or times out, THEN THE Compliance_Page SHALL display an error message with a retry button

### Requirement 3: Compliance Results Display

**User Story:** As a compliance reviewer, I want to see the compliance score, risk level, explanation, and suggestions clearly, so that I can quickly assess whether an asset is safe to publish.

#### Acceptance Criteria

1. WHEN a Result_Event is received, THE Compliance_Page SHALL display the compliance score (0–100) with a GSAP count-up animation from 0 to the final value
2. THE Compliance_Page SHALL display the risk_level as a color-coded badge (High = red, Medium = amber, Low = green) matching the Figma design
3. THE Compliance_Page SHALL display the explanation text from the Compliance_Result
4. THE Compliance_Page SHALL display the suggestion text from the Compliance_Result
5. WHEN the result contains a persona object, THE Compliance_Page SHALL display the persona demographics and cultural context information
6. THE Compliance_Page SHALL display the processing_time_seconds value

### Requirement 4: Violation List and Video Clip Playback

**User Story:** As a compliance reviewer, I want to see each violation with its extracted video clip, so that I can visually verify the flagged content and understand the exact problematic segment.

#### Acceptance Criteria

1. WHEN the Compliance_Result contains violations, THE Detail_Panel SHALL render each violation as a card showing its category, severity, type (visual/audio), and description
2. WHEN a violation has a non-null clip_url, THE Detail_Panel SHALL render a video player element with the clip source URL resolved against the backend base URL
3. WHEN the user clicks a violation clip, THE Detail_Panel SHALL play the video inline with standard HTML5 video controls
4. THE Detail_Panel SHALL display the violation timestamp range (start–end in seconds) for each violation
5. IF a violation has a null clip_url, THEN THE Detail_Panel SHALL display the violation details without a video player and show a "Clip unavailable" indicator

### Requirement 5: Detail Panel with Issues and AI Suggestions Tabs

**User Story:** As a compliance reviewer, I want to switch between viewing issues and AI-generated fix suggestions in a tabbed panel, so that I can review problems and their solutions side by side.

#### Acceptance Criteria

1. THE Detail_Panel SHALL display two tabs: "Issues" and "AI Suggestions" matching the Figma design layout
2. WHEN the Issues tab is active, THE Detail_Panel SHALL list all violations with their category, severity border color (error = red, warning = amber), and description text
3. WHEN the AI Suggestions tab is active, THE Detail_Panel SHALL display suggestion cards with "Original" and "Suggested" columns, an "Apply" button, and a "Keep" button
4. THE Detail_Panel SHALL display a "Fix issues with AI" button in the Issues tab that triggers the AI remediation flow
5. THE Detail_Panel SHALL display a "Mark as resolved & re-run" button in the pinned footer area that re-submits the asset for compliance checking
6. WHEN a compliance check has zero violations, THE Detail_Panel SHALL display a success state indicating the asset passes all checks

### Requirement 6: Summary Cards Dashboard

**User Story:** As a compliance reviewer, I want to see an overview of all compliance check statuses at a glance, so that I can prioritize which assets need immediate attention.

#### Acceptance Criteria

1. THE Summary_Cards SHALL display four cards: "Ready to Publish" count, "Needing Attention" count, "Checks Pending" count, and "Top Risk Flags" tags
2. THE Summary_Cards SHALL animate on page load using GSAP staggered entrance (y offset + opacity fade-in)
3. WHEN a new compliance check completes, THE Summary_Cards SHALL update their counts to reflect the new totals
4. THE "Needing Attention" card SHALL display a red left border and "HIGH RISK" badge when high-risk items exist, matching the Figma design

### Requirement 7: Active Review Queue Table

**User Story:** As a compliance reviewer, I want to see all compliance checks in a sortable queue table, so that I can select any asset to view its detailed results.

#### Acceptance Criteria

1. THE Review_Queue SHALL display columns: Campaign & Asset (with thumbnail), Platform icons, Risk Level badge, Flags (colored dots), Status, and Last Checked timestamp
2. WHEN the user clicks a row in the Review_Queue, THE Compliance_Page SHALL select that item and display its details in the Detail_Panel
3. THE Review_Queue SHALL highlight the currently selected row with a purple border matching the Figma `aurora-border-active` style
4. THE Review_Queue SHALL provide a "Filter by Risk Level" dropdown to filter items by All, High, Medium, or Low risk
5. WHEN a new compliance check is submitted, THE Review_Queue SHALL add the item with "In progress" status and an animated spinner icon

### Requirement 8: GSAP Page Animations

**User Story:** As a user, I want the compliance page to feel polished and dynamic with smooth animations, so that the experience feels professional and premium.

#### Acceptance Criteria

1. WHEN the Compliance_Page mounts, THE Summary_Cards SHALL animate in with a staggered `gsap.from()` using y: 30, opacity: 0, stagger: 0.1, duration: 0.5
2. WHEN the Compliance_Page mounts, THE Review_Queue rows SHALL animate in with a staggered entrance after the Summary_Cards complete
3. WHEN a compliance result score is displayed, THE Compliance_Page SHALL use `gsap.to()` to animate the number counting up from 0 to the final score value
4. WHEN the Detail_Panel opens or switches items, THE Detail_Panel content SHALL animate with a fade-in and slight y-offset transition
5. THE Compliance_Page SHALL use the `useGSAP` hook with a scoped container ref for all animations, following project GSAP conventions

### Requirement 9: Error Handling and Edge Cases

**User Story:** As a compliance reviewer, I want clear feedback when something goes wrong during a compliance check, so that I can understand the issue and take corrective action.

#### Acceptance Criteria

1. IF the backend returns a 400 status (missing file/text), THEN THE Compliance_Page SHALL display a validation error message to the user
2. IF the backend is unreachable or returns a 5xx status, THEN THE Compliance_Page SHALL display a connection error with a "Retry" button
3. IF the SSE stream terminates unexpectedly before a Result_Event, THEN THE Compliance_Page SHALL display a partial failure message and offer to retry
4. WHILE a compliance check is in progress, THE Upload_Form SHALL disable the submit button to prevent duplicate submissions
5. IF a file exceeds 100MB, THEN THE Upload_Form SHALL display a file size warning before submission


### Requirement 10: Figma Design System Compliance

**User Story:** As a developer, I want the frontend to closely follow the Figma HTML reference files in the `figma/` folder, so that the implemented UI is visually consistent with the approved design system across all pages.

#### Acceptance Criteria

1. THE Compliance_Page SHALL use the Layout_Shell structure: a fixed sidebar (width 240px, `w-sidebar-width`) on the left, a sticky top navigation bar, and a main content area with `max-w-[1200px]` centered horizontally with `mx-auto` and page margin of 40px (`p-margin-page`)
2. THE Compliance_Page SHALL use Design_Tokens for all color values, including `aurora-purple` (#7928ca) for active/highlight accents, `cosmic-pink` (#ff0080) for secondary accents, `emerald-glow` (#50e3c2) for success states, `ship-red` (#ee0000) for critical actions, and the surface hierarchy (`surface`, `surface-container-low`, `surface-container`, `surface-container-high`, `surface-container-highest`, `surface-container-lowest`) for background layering
3. THE Compliance_Page SHALL use Hanken Grotesk as the primary UI typeface with the defined size scale: `headline-lg` (48px), `headline-md` (32px), `headline-sm` (24px), `label-ui` (14px), `body-md` (16px), `body-lg` (18px), and JetBrains Mono for code and data display: `code-sm` (13px), `code-xs` (11px)
4. THE Compliance_Page SHALL style cards with `shadow-as-border` (box-shadow: 0 0 0 1px rgba(0,0,0,0.08)), `rounded-xl` corners, and hover elevation effects matching the Figma reference patterns
5. THE Compliance_Page SHALL render risk level badges using the Figma patterns: HIGH RISK with `bg-error-container text-on-error-container` and error border, MEDIUM RISK with `bg-amber-100 text-amber-800` and amber border, LOW RISK with `bg-surface-container-highest text-text-muted`
6. THE Compliance_Page SHALL style primary buttons with `bg-primary text-on-primary rounded-lg font-label-ui text-label-ui` and secondary buttons with `shadow-as-border` border styling, matching the Figma button patterns
7. THE Compliance_Page SHALL use Material Symbols Outlined icons (loaded via Google Fonts) for all iconography, with `font-variation-settings: 'FILL' 0` for default state and `'FILL' 1` for active/selected states
8. THE Compliance_Page SHALL highlight the active sidebar navigation item with `bg-surface-container-highest`, `font-semibold`, and a `border-l-2 border-primary` left accent, matching the Figma active nav state
9. WHILE the application is in dark mode, THE Compliance_Page SHALL apply `bg-dark` (#0a0a0f) as the base background, `inverse-surface` (#2f3131) for elevated surfaces, and `inverse-on-surface` (#f0f1f1) for text on dark backgrounds
10. THE Compliance_Page SHALL use the `aurora-border-active` style (box-shadow: 0 0 0 1px transparent, 0 0 0 2px #7928ca) for the selected row in the Review_Queue and for highlighted interactive elements
11. THE Compliance_Page SHALL render violation flag indicators as small colored dots (`w-2 h-2 rounded-full`) with `bg-error` for critical flags, `bg-ship-red` for regulatory flags, and `bg-amber-500` for warning flags, matching the Figma compliance table pattern
12. THE Compliance_Page SHALL style AI suggestion cards with a header row (uppercase `code-xs` label + resolution badge), a two-column grid showing "Original" (strikethrough, muted) and "Suggested" content, and a footer with "Apply" (primary) and "Keep" (secondary border) buttons, matching the Figma Detail_Panel AI Suggestions tab
13. WHEN the viewport width is below the `lg` breakpoint (1024px), THE Compliance_Page SHALL stack the Review_Queue table and Detail_Panel vertically instead of side-by-side, maintaining readability on smaller screens
