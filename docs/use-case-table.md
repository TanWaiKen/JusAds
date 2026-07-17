# JusAds — Use Case Table

*Derived from `diagram/jusads_usecase.drawio`*

---

## Actors

| Actor | Description |
|-------|-------------|
| Project Member | A user who belongs to a project team. Can access all standard features including compliance checking, generation, asset management, and analytics. |
| Project Owner | An elevated role that inherits all Project Member capabilities plus project access control. |

---

## Use Cases

| UC-ID | Use Case Name | Actor(s) | Description | Priority | Precondition(s) | Main Flow | Post Condition(s) | Relationships |
|-------|---------------|----------|-------------|----------|-----------------|-----------|-------------------|---------------|
| UC-01 | Login | Project Member | Authenticates the user into the JusAds platform via AWS Cognito OAuth. | High | User has a registered account. | 1) User enters credentials. 2) System authenticates via Cognito. 3) User is redirected to the dashboard. | User session is active; JWT token stored. | **«include»** UC-02 (User Onboarding) |
| UC-02 | User Onboarding | Project Member | Guides new users through initial setup: profile creation, company details, and first project creation. | High | User has successfully logged in for the first time. | 1) System detects new user. 2) Onboarding wizard collects company name, industry, and target markets. 3) System creates a default project. | User profile and default project are created. | Included by UC-01 |
| UC-03 | Manage Profile | Project Member | Allows users to view and update their profile settings (name, avatar, company details, notification preferences). | Medium | User is logged in. | 1) User navigates to Profile page. 2) User edits fields. 3) System saves updates. | Profile is updated in Supabase. | — |
| UC-04 | Create Project | Project Member | Creates a new project workspace for organizing ads, compliance checks, and generated content. | High | User is logged in. | 1) User clicks "Create Project." 2) User enters project name, target market, platform. 3) System creates project in Supabase. | New project is available in dashboard. | **«extend»** UC-05, UC-06 |
| UC-05 | Generate Ad Creative (text/image/audio/video) | Project Member | Uses AI to generate ad creatives in one or more media types based on a user brief, brand context, and platform rules. | High | A project exists; user has described the ad brief. | 1) User enters natural language brief in chat. 2) System detects desired media types. 3) System resolves platform rules. 4) System fans out to media-specific agents. 5) Generated ads are saved to the project. | Generated ads stored in Supabase with S3 media URLs. | Extends UC-04; Extended by UC-06; **«extend»** from UC-07 (Browse Prompt Library) |
| UC-06 | Ad Compliance and Localization Check | Project Member | Runs the multi-modal compliance pipeline against an ad creative to detect regulatory and cultural violations for the target market. | High | An ad creative exists (uploaded or generated). | 1) User selects an ad to check. 2) System fetches rules for market/platform. 3) System transcribes audio/video if needed. 4) AI analyzes content against rules. 5) Bias check and judges evaluation run. 6) Decision: Pass / Remediate / Reject. | Compliance result stored with risk score and violations. | Extends UC-04; Extended by UC-07 (Remediation) |
| UC-07 | Ad Remediation (auto-fix violations) | Project Member | Automatically fixes non-compliant content using inpainting, text rewrite, or TTS re-voicing based on compliance findings. | High | Compliance check returned "remediate" decision. | 1) System fetches compliance result. 2) User confirms aspect ratio (human-in-the-loop). 3) System applies media-specific remediation. 4) Remediated asset uploaded to S3. | Remediated ad available alongside original for comparison. | Extends UC-06 |
| UC-08 | Browse Prompt Library | Project Member | Allows users to browse and select pre-built prompt templates to accelerate ad generation. | Medium | User is logged in; prompt library is populated. | 1) User opens Prompt Library. 2) User filters by category/platform. 3) User selects a template. 4) Template populates the generation chat. | Selected template pre-fills generation brief. | **«extend»** UC-05 |
| UC-09 | Manage Project | Project Member | Allows users to view, edit, rename, archive, or delete projects and their associated tasks. | Medium | At least one project exists. | 1) User selects a project. 2) User edits settings or manages tasks. 3) System persists changes. | Project metadata updated. | Extended by UC-13 (Manage Generation or Compliance Check Task) |
| UC-10 | Manage Assets | Project Member | Provides a central view for managing all media assets (uploaded and generated) including tagging, filtering, and downloading. | Medium | Project exists with associated assets. | 1) User navigates to Assets page. 2) User browses/filters assets. 3) User can download, delete, or tag assets. | Asset state updated in Supabase. | **«extend»** UC-11 (Distribute) |
| UC-11 | Distribute Assets to Social Media | Project Member | Publishes approved ads to social platforms (TikTok, Instagram, YouTube) via Zernio SDK integration. | Medium | Ad is published (passed compliance + human approval). | 1) User selects a published ad. 2) User selects target platform. 3) System posts via Zernio API. 4) Distribution metadata recorded. | Ad posted to social platform; analytics tracking begins. | Extends UC-10 |
| UC-12 | Social Media Post Live Analysis | Project Member | Monitors live performance metrics (impressions, likes, shares, engagement) of distributed ads from social platforms. | Low | Ad has been distributed to at least one platform. | 1) User navigates to Analytics. 2) System fetches metrics from Zernio. 3) Charts and KPIs displayed. | Real-time analytics displayed. | — |
| UC-13 | Manage Generation or Compliance Check Task | Project Member | View status, retry, or cancel individual generation and compliance tasks within a project. | Medium | A project has active or completed tasks. | 1) User views task list. 2) User can retry failed tasks or cancel running ones. 3) System updates task status. | Task status updated in pipeline_progress. | Extends UC-09 |
| UC-14 | Trending Analysis based on Company Context | Project Member | Provides AI-driven trend analysis customized to the user's company industry, target market, and product category. | Low | User has company profile configured. | 1) User navigates to Trends page. 2) System fetches trend data. 3) Trends displayed with relevance to company context. | Trend insights presented. | — |
| UC-15 | Control Project Access Permission | Project Owner | Allows project owners to manage team member access, invite new members, and set role-based permissions. | High | User is the project owner. | 1) Owner navigates to Project Settings → Access. 2) Owner invites members or changes roles. 3) System updates access control. | Permissions updated; new members can access project. | — |

---

## Relationship Summary

| Relationship | From | To | Type |
|-------------|------|-----|------|
| Login includes Onboarding | UC-01 | UC-02 | «include» |
| Generate extends Create Project | UC-05 | UC-04 | «extend» |
| Compliance extends Create Project | UC-06 | UC-04 | «extend» |
| Prompt Library extends Generate | UC-08 | UC-05 | «extend» |
| Compliance extends Generate | UC-06 | UC-05 | «extend» |
| Remediation extends Compliance | UC-07 | UC-06 | «extend» |
| Distribute extends Manage Assets | UC-11 | UC-10 | «extend» |
| Manage Task extends Manage Project | UC-13 | UC-09 | «extend» |

---

## Notes

- **Project Owner** inherits all Project Member use cases (generalization relationship shown in diagram).
- The compliance and generation pipelines use LangGraph StateGraph orchestration with WebSocket-based progress streaming.
- Distribution requires a human-in-the-loop publishing gate — non-compliant ads cannot be distributed.
