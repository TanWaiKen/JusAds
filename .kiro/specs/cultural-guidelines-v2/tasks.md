# Implementation Plan: Cultural Guidelines V2

## Overview

Extend the content compliance pipeline with cultural advertising rules for Malay, Chinese, and Indian audiences. This involves creating a cultural guideline data model, CSV ingestion pipeline, expanded RAG retrieval (top 50), ethnicity-aware filtering, pipeline file renaming with step-number prefixes, and combined regulatory + cultural evaluation.

## Tasks

- [x] 1. Pipeline file renaming and merging
  - [x] 1.1 Rename pipeline node files with step-number prefixes
    - Rename `nodes/router.py` → `nodes/step1_routing.py` and merge `nodes/market_resolver.py` content into it
    - Rename `nodes/video_pipeline.py` → `nodes/step2_video_analysis.py`
    - Rename `nodes/image_pipeline.py` → `nodes/step3_image_analysis.py`
    - Rename `nodes/text_pipeline.py` → `nodes/step4_text_analysis.py`
    - Rename `nodes/guideline_retrieval.py` → `nodes/step5_guideline_retrieval.py`
    - Rename `nodes/compliance_evaluation.py` → `nodes/step6_compliance_evaluation.py`
    - Rename `nodes/result_formatting.py` → `nodes/step7_result_formatting.py` and merge `nodes/error_handler.py` content into it
    - Delete the now-merged `nodes/market_resolver.py` and `nodes/error_handler.py` files
    - _Requirements: 9.1, 9.4, 9.5_

  - [x] 1.2 Update all import statements and orchestrator node registration
    - Update `orchestrator.py` to import from new module names and register renamed nodes
    - Update `nodes/__init__.py` to export from new module names
    - Update any cross-node imports referencing old file names
    - Update test files that import from old node module names
    - _Requirements: 9.2, 9.3_

- [x] 2. Cultural guideline data model and schema extensions
  - [x] 2.1 Create cultural guideline Pydantic models
    - Create `models/cultural_schemas.py` with `Ethnicity`, `AgeGroup`, `CulturalCategory`, `Severity` enums
    - Implement `GuidelineEntry` Pydantic model with field validators for market, ethnicity, age_group, category, severity, and guideline_text (max 500 chars)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [x] 2.2 Write property test for GuidelineEntry field validation
    - **Property 1: GuidelineEntry Field Validation**
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6**

  - [x] 2.3 Write property test for GuidelineEntry text length constraint
    - **Property 2: GuidelineEntry Text Length Constraint**
    - **Validates: Requirements 1.7**

  - [x] 2.4 Extend ContentSubmission schema with target_ethnicity and target_age_group
    - Add `target_ethnicity` field to `models/schemas.py` ContentSubmission with default "all" and pattern validation
    - Add `target_age_group` field to `models/schemas.py` ContentSubmission with default "all_ages" and pattern validation
    - _Requirements: 6.5, 11.1_

  - [x] 2.5 Extend PipelineState with cultural guideline fields
    - Add `target_ethnicity`, `target_age_group`, `regulatory_guidelines`, `cultural_guidelines`, `retrieved_guidelines`, and `guideline_sources` fields to PipelineState
    - _Requirements: 11.1, 6.5_

  - [x] 2.6 Add guideline_source field to violation location models
    - Add `guideline_source: Literal["regulatory", "cultural"]` field to `TextIssueLocation`, `ImageIssueLocation`, and `VideoIssueLocation` models with default "regulatory"
    - _Requirements: 10.3_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Cultural guideline ingestion from CSV
  - [x] 4.1 Create the cultural guideline ingestion module
    - Create `ingest_cultural.py` with `ingest_cultural_guidelines(csv_path, recreate)` function
    - Implement `validate_guideline_row(row, row_number)` validation function
    - Parse CSV rows, validate against GuidelineEntry schema, skip invalid rows with logged warnings
    - Embed valid guideline_text using Cohere embed-v4 (1024 dimensions) via AWS Bedrock
    - Upsert points to Qdrant `cultural-guidelines` collection with all metadata as payload
    - Return `IngestionResult` with total_ingested, rows_skipped, collection_name, and errors list
    - Handle file-not-found and empty-file error cases
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 1.8_

  - [x] 4.2 Write property test for CSV ingestion valid row round-trip
    - **Property 11: CSV Ingestion Valid Row Round-Trip**
    - **Validates: Requirements 8.1**

  - [x] 4.3 Write property test for CSV ingestion invalid row graceful skip
    - **Property 12: CSV Ingestion Invalid Row Graceful Skip**
    - **Validates: Requirements 8.2, 8.3**

  - [x] 4.4 Write property test for ingestion report completeness
    - **Property 13: Ingestion Report Completeness**
    - **Validates: Requirements 8.6**

  - [x] 4.5 Create cultural guidelines CSV data files
    - Create `data/cultural_guidelines.csv` with at least 15 Malay/Malaysia, 15 Chinese/Malaysia, 15 Indian/Malaysia guidelines
    - Include at least 5 Malay/Singapore, 5 Chinese/Singapore, 5 Indian/Singapore guidelines
    - Cover required categories per ethnicity: body_exposure, modesty, halal_compliance, religious_sensitivity, suggestive_content, food_taboos for Malay; superstitions, number_symbolism, color_symbolism, ancestral_respect, food_taboos, religious_sensitivity for Chinese; religious_sensitivity, food_taboos, caste_sensitivity, color_symbolism, ancestral_respect, gender_norms for Indian
    - Ensure guideline_text content matches specific requirements (aurat rules, number 4/8, deity placement, etc.)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2_

- [x] 5. Expanded RAG retrieval with ethnicity and age group filtering
  - [x] 5.1 Update config.py with expanded retrieval settings
    - Change `QDRANT_TOP_K` default from 5 to 50
    - Add `CULTURAL_COLLECTION_NAME` config with default "cultural-guidelines"
    - Add `CULTURAL_COLLECTION_CONFIG` dict with vector_size=1024 and distance="Cosine"
    - _Requirements: 7.1_

  - [x] 5.2 Implement combined regulatory + cultural retrieval in step5_guideline_retrieval.py
    - Embed content using Cohere embed-v4 with input_type="search_query"
    - Query regulatory collection (market-specific) with limit=50, no payload filter
    - Query cultural collection with Qdrant payload filter for market, ethnicity, and age_group with limit=50
    - Implement age_group filtering logic: include "all_ages" always, include specific age_group only when matching content target
    - Implement ethnicity filtering logic: when target is specific ethnicity, include matching + "all"; when target is "all", include all ethnicities
    - Merge both result sets, rank by similarity score descending, take top 50 combined
    - Label each result as "regulatory" or "cultural" for the evaluation prompt
    - Use Pegasus_Description for video, unified content description for image, raw text for text content
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 5.3, 6.1, 6.2, 6.3, 6.4, 11.2, 11.3, 11.4_

  - [x] 5.3 Write property test for age group filtering correctness
    - **Property 4: Age Group Filtering Correctness**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

  - [x] 5.4 Write property test for ethnicity filtering correctness
    - **Property 5: Ethnicity Filtering Correctness**
    - **Validates: Requirements 11.2, 11.3, 11.5**

  - [x] 5.5 Write property test for combined retrieval merge ranking
    - **Property 6: Combined Retrieval Merge Ranking**
    - **Validates: Requirements 7.2, 7.3, 10.1**

- [x] 6. Combined regulatory + cultural compliance evaluation
  - [x] 6.1 Update step6_compliance_evaluation.py with combined evaluation prompt
    - Format retrieved guidelines into clearly labeled "Regulatory Guidelines" and "Cultural Guidelines" sections in the evaluation prompt
    - Pass all 50 retrieved guidelines as context to the evaluation LLM
    - Parse LLM response to tag each violation with guideline_source ("regulatory" or "cultural")
    - Map cultural severity to compliance severity: high→Severe, medium→Moderate, low→Minor
    - _Requirements: 10.2, 10.3, 5.4, 5.5, 5.6_

  - [x] 6.2 Write property test for guideline source labeling in prompt
    - **Property 7: Guideline Source Labeling in Prompt**
    - **Validates: Requirements 10.2**

  - [x] 6.3 Write property test for cultural violation source labeling
    - **Property 8: Cultural Violation Source Labeling**
    - **Validates: Requirements 10.3**

  - [x] 6.4 Write property test for severity mapping
    - **Property 3: Cultural Severity to Compliance Severity Mapping**
    - **Validates: Requirements 5.4, 5.5, 5.6**

  - [x] 6.5 Update scoring to apply equally to cultural and regulatory violations
    - Ensure the scoring formula `max(0, round(100 - sum(weight × multiplier)))` applies identically regardless of guideline_source
    - Sort high_risk_indicators by severity: Severe first, then Moderate, then Minor
    - _Requirements: 10.4, 10.5_

  - [x] 6.6 Write property test for scoring formula equality
    - **Property 9: Scoring Formula Applies Equally to Cultural and Regulatory Violations**
    - **Validates: Requirements 10.4**

  - [x] 6.7 Write property test for violation severity ordering
    - **Property 10: Violation Severity Ordering**
    - **Validates: Requirements 10.5**

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Input validation and wiring
  - [x] 8.1 Add ethnicity validation in step1_routing.py
    - Validate `target_ethnicity` against allowed values {"malay", "chinese", "indian", "all"}
    - Return validation error with supported values list if invalid
    - Validate `target_age_group` against allowed values {"all_ages", "adults_only", "children"}
    - Pass validated ethnicity and age_group into PipelineState
    - _Requirements: 11.5, 6.5_

  - [x] 8.2 Wire cultural guideline flow through orchestrator
    - Update `orchestrator.py` to pass target_ethnicity and target_age_group through the state graph
    - Ensure step5 receives ethnicity/age_group from state for filtering
    - Ensure step6 receives labeled guidelines from step5
    - Ensure step7 formats cultural violations with guideline_source in output
    - _Requirements: 10.1, 10.2, 10.3, 11.2_

  - [x] 8.3 Create Hypothesis test generators for cultural guidelines
    - Create `generators/cultural_guidelines.py` with strategies for GuidelineEntry fields
    - Create `generators/csv_rows.py` with strategies for valid and invalid CSV rows
    - Extend `generators/submissions.py` with ethnicity and age_group strategies
    - Extend `generators/results.py` with guideline_source field
    - _Requirements: 1.1, 11.1, 6.5_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (Properties 1–13)
- Unit tests validate specific examples and edge cases
- The pipeline file renaming (task 1) is done first to establish the new file structure before adding cultural features
- The design uses Python with Pydantic, Hypothesis for PBT, and Qdrant for vector storage
- Status legend: `[x]` = complete, `[-]` = in progress / partially done, `[~]` = under review / needs verification, `[ ]` = not started

### Property Test Coverage Summary

| Property | Task | Status | Requirement(s) |
|----------|------|--------|----------------|
| Property 1: GuidelineEntry Field Validation | 2.2 | [x] | 1.2, 1.3, 1.4, 1.5, 1.6 |
| Property 2: GuidelineEntry Text Length Constraint | 2.3 | [x] | 1.7 |
| Property 3: Cultural Severity to Compliance Severity Mapping | 6.4 | [ ] | 5.4, 5.5, 5.6 |
| Property 4: Age Group Filtering Correctness | 5.3 | [x] | 6.1, 6.2, 6.3, 6.4 |
| Property 5: Ethnicity Filtering Correctness | 5.4 | [x] | 11.2, 11.3, 11.5 |
| Property 6: Combined Retrieval Merge Ranking | 5.5 | [x] | 7.2, 7.3, 10.1 |
| Property 7: Guideline Source Labeling in Prompt | 6.2 | [ ] | 10.2 |
| Property 8: Cultural Violation Source Labeling | 6.3 | [ ] | 10.3 |
| Property 9: Scoring Formula Applies Equally | 6.6 | [ ] | 10.4 |
| Property 10: Violation Severity Ordering | 6.7 | [ ] | 10.5 |
| Property 11: CSV Ingestion Valid Row Round-Trip | 4.2 | [x] | 8.1 |
| Property 12: CSV Ingestion Invalid Row Graceful Skip | 4.3 | [x] | 8.2, 8.3 |
| Property 13: Ingestion Report Completeness | 4.4 | [x] | 8.6 |

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5", "2.6", "5.1"] },
    { "id": 3, "tasks": ["4.1", "4.5", "8.3"] },
    { "id": 4, "tasks": ["4.2", "4.3", "4.4", "5.2"] },
    { "id": 5, "tasks": ["5.3", "5.4", "5.5", "6.1"] },
    { "id": 6, "tasks": ["6.2", "6.3", "6.4", "6.5", "8.1"] },
    { "id": 7, "tasks": ["6.6", "6.7", "8.2"] }
  ]
}
```
