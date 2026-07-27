# JusAds — Final Year Project Summary

## 1. Cover Page

**JusAds: Localized AI Advertising Generation and Compliance Assistant**

Final Year Project proposal/presentation for an AI-assisted system that helps
businesses create localized advertising concepts, media, and compliance reviews
for Southeast Asian markets.

## 2. Problem Statement

Small businesses often create ads without specialist creative, cultural, or
regulatory support. Existing creative tools generate content quickly but do not
consistently connect a business brief, local audience context, policy risks,
trend references, production workflow, and auditable remediation in one place.
This can cause generic advertising, costly revisions, and avoidable cultural or
claim-related problems.

## 3. Aim and Objective

**Aim:** develop a secure web platform that assists marketers in producing
localized ad ideas and media while identifying potential compliance risks.

Objectives:

1. Capture a company profile, market, audience, product, and campaign brief.
2. Generate localized text, image, audio, and video advertising concepts.
3. Provide trend and creative-reference research that can be reused from cache.
4. Run explainable compliance checks and an auditable remediation/recheck flow.
5. Protect tenant data, private media, and historical project records.

## 4. Target User

- Malaysian and Southeast Asian SMEs, retailers, food businesses, and agencies.
- Marketing teams that need faster localized creative ideation.
- Compliance/review staff who need traceable findings and remediation history.
- Project owners who need reusable business, audience, and brand context.

## 5. System Unique Proposition and Functions

JusAds combines localized generation with a compliance workflow rather than
presenting generation as a final answer. Its differentiators are market and
persona context, culturally aware creative planning, trend-source references,
multi-modal generation, and remediation that remains pending until a recheck
passes. Key functions include onboarding, project/task management, easy and
advanced generation, trend intelligence, compliance review, remediation,
private media delivery, and shared campaign assets.

## 6. Domain Research

The domain combines digital advertising, localization, cultural sensitivity,
advertising claims, generative AI, and media production. The project treats
market context as more than translation: language, local events, audience
expectations, product category, and platform format influence the creative
brief. Compliance output is a decision-support tool; policy/legal review still
requires accountable human and organisation processes.

## 7. Similar Systems in Paper and in Market

Market comparisons include general design/generation platforms, video editors,
and ad-management systems. They commonly provide templates, editing, copy
generation, or media publishing, but do not necessarily provide an integrated
Malaysia/Southeast-Asia localization and pending-recheck compliance lifecycle.

Relevant research areas include multimodal content generation, retrieval and
grounding, human-in-the-loop AI, explainable classification, media forensics,
and fairness/cultural-sensitivity evaluation. The final report should cite
peer-reviewed papers selected through the university library rather than claim
that any commercial product is a direct equivalent.

## 8. Technical Research

The system uses a React frontend, FastAPI backend, PostgreSQL/Supabase data
store, private S3-compatible media storage, Cognito/OIDC authentication, and
AI-provider integrations for generation/research. Trend data is cached to
control API cost; YouTube hook references use a verified-user, company-context
cache. Compliance uses rules and primary model evaluation; an optional
synthetic text-triage POC is advisory only and disabled by default.

## 9. System Development Methodology

An iterative Agile approach is suitable: collect requirements, prototype a
vertical workflow, test with representative users, review risks, and deliver in
small increments. Each iteration should include acceptance criteria,
security/privacy checks, error handling, test evidence, and retrospective
improvements.

## 10. Data Gathering

Inputs include user-provided company profile/brief data, approved public trend
sources, public cultural-event references, and system-generated task records.
Do not train models on customer uploads by default. Future labelled feedback
requires consent/lawful basis, provenance, de-identification, retention rules,
access controls, and human label governance.

## 11. System Design

The architecture has five layers: React presentation; authenticated API routes;
domain modules for generation, compliance, and trends; PostgreSQL persistence;
and external AI/media providers. Projects own tasks; tasks own generated assets
and compliance records. Private media is stored as object keys and exposed only
through short-lived authorized URLs. Remediation versions are immutable and
must be re-evaluated before a compliant status is shown.

## 12. Implementation

Implemented modules include business onboarding, dashboard/project management,
easy and advanced ad generation, image/audio/video workflows, trend signals,
daily ideas, cached YouTube hook references, compliance analysis, remediation,
recheck lifecycle, Cognito bearer-token checks, ownership checks, and private
media access. The codebase separates `jusads_generation`, `jusads_compliance`,
and `jusads_trends` domain responsibilities.

## 13. Unit Testing

Unit tests cover deterministic helpers and contracts such as authorization,
private-media schema rules, remediation state transitions, daily ideas, the
synthetic advisory triage POC, and YouTube hook-cache query/serialization.
External AI/provider calls should be mocked in unit tests; a passing unit test
does not prove a provider response is correct in production.

## 14. Acceptance Testing

Acceptance tests should use an authenticated isolated account and test-only
records. Core scenarios are: create a project, generate an ad, retrieve
authorized private media, submit a compliance check, observe progress/error
states, remediate, see `pending_recheck`, and see a final verified status only
after re-evaluation. Historical presentation records must be read-only during
testing.

## 15. Limitation

AI outputs can be incomplete, biased, or inaccurate. Public trend search may
return irrelevant references and cannot prove a video is a paid ad. Provider
quotas, rate limits, cost, latency, media-render time, and third-party API
availability affect the experience. Compliance assistance is not legal advice
and needs policy-owner/human review for high-impact decisions.

## 16. Future Enhancement

Possible work includes verified policy knowledge bases, stronger multilingual
evaluation, improved video continuity and sound design, richer team roles,
approval workflows, analytics feedback loops, policy version dashboards, model
monitoring, and a governed labelled-feedback learning layer. Any future model
promotion must meet precision, recall, false-negative, calibration, drift,
cost, latency, privacy, and rollback criteria.

## 17. Conclusion

JusAds demonstrates how generative advertising assistance can be connected to
local context, trend inspiration, secure media handling, and an auditable
compliance/recheck cycle. Its value is not only faster generation, but making
the process more reviewable and safer to operate.

## 18. System Demonstration Flow

1. Sign in through Cognito and complete the company profile.
2. Create a project and choose market, audience, and campaign objective.
3. Use Easy or Advanced generation to create a concept and media plan.
4. Open Trends to view saved creative signals and company-context YouTube hook
   references.
5. Generate/select an advertisement and submit it for compliance review.
6. Review findings, media previews, and suggested changes.
7. Start remediation when appropriate; show the `pending recheck` state.
8. Present the recheck outcome and private authorized media link.
9. Return to the project dashboard to show stored tasks and results.

## 19. Thank You Page

**Thank you**

Questions and discussion.

Suggested closing message: *JusAds supports faster localized creativity while
keeping verification, human accountability, and data protection in the flow.*
