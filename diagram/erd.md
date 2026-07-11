# JusAds — Entity Relationship Diagram

## Full Database Schema (including Migration 020)

```mermaid
erDiagram
    %% ─── Core Entities ───────────────────────────────────────────────────

    users {
        text email PK
        boolean is_onboarded
        timestamptz created_at
    }

    projects {
        uuid id PK
        text owner_email
        text name
        text description
        timestamptz created_at
        timestamptz updated_at
    }

    project_members {
        uuid id PK
        uuid project_id FK
        text email
        text role
        timestamptz invited_at
    }

    business_profiles {
        uuid id PK
        text owner_email UK
        text company_name
        text product_category
        text product_description
        text[] target_platforms
        text[] target_markets
        text logo_s3_key
        boolean onboarding_complete
        timestamptz created_at
        timestamptz updated_at
    }

    %% ─── Task Layer ──────────────────────────────────────────────────────

    tasks {
        uuid id PK
        uuid project_id FK
        text type
        text status
        text summary
        jsonb pipeline_state
        timestamptz created_at
        timestamptz updated_at
    }

    compliance_checks {
        uuid task_id PK_FK
        uuid project_id FK
        text media_type
        text market
        text ethnicity
        text age_group
        text platform
        numeric risk_percentage
        text status
        jsonb result_json
        text s3_upload_key
        text s3_segmented_key
        text s3_remix_key
        jsonb remediation_metadata
        timestamptz created_at
        timestamptz updated_at
    }

    violations {
        uuid id PK
        uuid task_id FK
        integer violation_index
        text type
        text severity
        text description
        numeric start_time
        numeric end_time
        text clip_s3_key
        timestamptz created_at
    }

    %% ─── Rules & Personas ────────────────────────────────────────────────

    ad_policy_rules {
        text id PK
        text source
        text regulator
        text framework
        text category
        text rule_title
        text rule_text
        text applies_to
        text enforcement
        date effective_date
        date last_updated
        text tags
        timestamptz created_at
    }

    personas {
        bigint id PK
        text market
        text ethnicity
        text age_group
        jsonb persona_data
        timestamptz created_at
        timestamptz updated_at
    }

    platform_rules {
        uuid id PK
        text platform
        text media_type
        text aspect_ratio
        integer max_duration_seconds
        integer max_file_size_mb
        jsonb additional_rules
        timestamptz created_at
    }

    %% ─── Pipeline & Chat ─────────────────────────────────────────────────

    pipeline_progress {
        uuid id PK
        uuid task_id
        text step_name
        text status
        text message
        timestamptz created_at
        timestamptz updated_at
    }

    chat_messages {
        uuid id PK
        uuid project_id
        uuid task_id FK
        text role
        text content
        jsonb attachments
        timestamptz created_at
    }

    %% ─── Generation ──────────────────────────────────────────────────────

    storyboard_scenes {
        uuid id PK
        uuid project_id FK
        uuid task_id
        integer scene_index
        numeric timestamp_start
        numeric timestamp_end
        text visual_prompt
        text audio_script
        text s3_anchor_image_key
        text s3_raw_video_key
        text status
        timestamptz created_at
        timestamptz updated_at
    }

    generated_ads {
        uuid id PK
        uuid project_id FK
        uuid task_id FK
        text media_type
        text platform
        text caption
        text prompt_used
        text s3_media_key
        uuid parent_ad_id FK
        text status
        jsonb metadata
        text compliance_status
        jsonb compliance_result
        uuid compliance_task_id
        timestamptz distributed_at
        text distribution_platform
        text distribution_post_id
        text s3_draft_key
        text s3_rendered_key
        timestamptz created_at
        timestamptz updated_at
    }

    remediation_logs {
        uuid id PK
        uuid task_id FK
        text agent_strategy
        text modified_media_type
        text previous_s3_key
        text remediated_s3_key
        integer quality_score
        integer attempt_number
        timestamptz created_at
    }

    brand_voices {
        uuid id PK
        uuid project_id FK "nullable"
        text voice_id
        text voice_name
        text description
        text sample_url
        text market
        text ethnicity
        text gender
        text language_code
        boolean is_custom_clone
        text status
        timestamptz created_at
        timestamptz updated_at
    }

    %% ─── Research & Intelligence Layer (Migration 020) ───────────────────

    trends_cache {
        uuid id PK
        text platform
        text content_type
        text title
        text url
        jsonb engagement_metrics
        text[] hashtags
        text[] categories
        text cultural_event_tag
        text market
        timestamptz scraped_at
        uuid scrape_batch_id
        timestamptz created_at
    }

    cultural_events {
        uuid id PK
        text name
        text market
        date start_date
        date end_date
        text event_type
        text[] tags
        integer impact_score
        timestamptz created_at
    }

    post_statistics_cache {
        uuid id PK
        uuid generated_ad_id FK
        text platform
        text post_external_id
        integer impressions
        integer clicks
        numeric engagement_rate
        integer reach
        integer conversions
        jsonb raw_metrics
        timestamptz fetched_at
    }

    tavily_usage_log {
        uuid id PK
        uuid task_id
        text query
        integer results_count
        text search_depth
        timestamptz invoked_at
    }

    %% ─── Relationships ───────────────────────────────────────────────────

    projects ||--o{ tasks : "has"
    projects ||--o{ project_members : "shared with"
    projects ||--o{ storyboard_scenes : "contains"
    projects ||--o{ generated_ads : "produces"
    projects ||--o{ brand_voices : "owns"

    tasks ||--o| compliance_checks : "extends (1:1)"
    tasks ||--o{ chat_messages : "has turns"
    tasks ||--o{ pipeline_progress : "tracks"

    compliance_checks ||--o{ violations : "flags"
    compliance_checks ||--o{ remediation_logs : "attempts"

    generated_ads ||--o{ post_statistics_cache : "tracked by"
    generated_ads ||--o| generated_ads : "parent (self-ref)"
```

## Table Summary

| # | Table | Purpose | Migration |
|---|-------|---------|-----------|
| 1 | users | User accounts | Initial |
| 2 | projects | Project containers | Initial |
| 3 | project_members | Shared access | Initial |
| 4 | business_profiles | Company/product onboarding | Initial |
| 5 | tasks | Compliance + generation tasks | Initial |
| 6 | compliance_checks | Compliance check results (1:1 with task) | Initial |
| 7 | violations | Per-violation records | Initial |
| 8 | ad_policy_rules | Regulatory rules (replaces Qdrant) | Initial |
| 9 | personas | Cultural persona JSONB blobs | Initial |
| 10 | pipeline_progress | Step-by-step pipeline tracking | Initial |
| 11 | platform_rules | Platform format constraints | Initial |
| 12 | chat_messages | Generation chat turns | Initial |
| 13 | storyboard_scenes | Multi-scene video tracking | Initial |
| 14 | generated_ads | Generated ad outputs | Initial |
| 15 | remediation_logs | Remediation audit trail | Initial |
| 16 | brand_voices | ElevenLabs voice clones | Initial |
| 17 | **trends_cache** | Apify scraped trending content | **020** |
| 18 | **cultural_events** | Cultural/global events calendar | **020** |
| 19 | **post_statistics_cache** | Zernio post metrics cache | **020** |
| 20 | **tavily_usage_log** | Tavily cost monitoring | **020** |

## New Columns (Migration 020)

| Table | Column | Type | Purpose |
|-------|--------|------|---------|
| generated_ads | s3_draft_key | text | CapCut draft ZIP S3 key |
| generated_ads | s3_rendered_key | text | Rendered MP4 S3 key |
