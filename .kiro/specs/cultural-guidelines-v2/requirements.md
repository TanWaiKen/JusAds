# Requirements Document

## Introduction

This document specifies requirements for enhancing the content compliance pipeline with cultural advertising rules that go beyond legal/regulatory guidelines. The current system only evaluates content against regulatory frameworks (MCMC for Malaysia, IMDA/ASAS for Singapore), but fails to catch culture-specific advertising taboos such as inappropriate body exposure, suggestive actions, and ethnic-specific sensitivities. This feature adds a cultural guideline layer with ethnic-specific rules (Malay, Chinese, Indian), age-group targeting metadata, an expanded RAG retrieval window (top 50), a structured guideline data model with rich metadata, and pipeline file renaming for clarity.

## Glossary

- **Cultural_Guideline**: A non-regulatory advertising rule rooted in cultural norms, ethnic sensitivities, or social taboos that varies by market, ethnicity, and age group
- **Regulatory_Guideline**: An existing legal/regulatory rule from MCMC (Malaysia) or IMDA/ASAS (Singapore) already in the system
- **Guideline_Store**: The Qdrant vector database containing both regulatory and cultural guidelines in separate collections
- **Cultural_Collection**: A Qdrant vector collection dedicated to cultural guidelines, separate from the existing regulatory collections
- **Ethnicity**: A target ethnic audience within a market — Malay, Chinese, or Indian for both Malaysia and Singapore
- **Age_Group**: A demographic targeting category indicating which audience a guideline applies to — "all_ages", "adults_only", or "children"
- **Guideline_Entry**: A single guideline record containing market, ethnicity, age_group, category, severity, and guideline_text fields
- **RAG_Retriever**: The component that embeds content and queries the Guideline_Store for relevant guidelines using vector similarity search
- **Pegasus_Description**: The text output from TwelveLabs Pegasus video understanding model, used as the RAG query input for video content
- **Pipeline_Step**: A named processing stage in the compliance pipeline, identified by a step number prefix (step1, step2, etc.)
- **Compliance_Pipeline**: The LangGraph-orchestrated system that routes content through processing steps and evaluates it against retrieved guidelines
- **Cultural_Category**: A classification for cultural guidelines including: body_exposure, suggestive_content, religious_sensitivity, food_taboos, superstitions, color_symbolism, number_symbolism, gender_norms, ancestral_respect, caste_sensitivity

## Requirements

### Requirement 1: Cultural Guideline Data Structure

**User Story:** As a content compliance developer, I want each cultural guideline stored with structured metadata, so that guidelines can be filtered and retrieved by market, ethnicity, age group, and category.

#### Acceptance Criteria

1. THE Guideline_Entry SHALL contain the following fields: market (string), ethnicity (string), age_group (string), category (string), severity (string), and guideline_text (string)
2. THE Guideline_Entry market field SHALL accept values "malaysia" or "singapore"
3. THE Guideline_Entry ethnicity field SHALL accept values "malay", "chinese", "indian", or "all" — where "all" indicates the guideline applies across all ethnic groups in that market
4. THE Guideline_Entry age_group field SHALL accept values "all_ages", "adults_only", or "children"
5. THE Guideline_Entry category field SHALL accept values from the set: "body_exposure", "suggestive_content", "religious_sensitivity", "food_taboos", "superstitions", "color_symbolism", "number_symbolism", "gender_norms", "ancestral_respect", "caste_sensitivity", "modesty", "halal_compliance"
6. THE Guideline_Entry severity field SHALL accept values "high", "medium", or "low"
7. THE Guideline_Entry guideline_text field SHALL contain a clear, actionable description of the cultural rule in English with a maximum length of 500 characters
8. WHEN a Guideline_Entry is ingested into the Guideline_Store, THE RAG_Retriever SHALL embed the guideline_text field using Cohere embed-v4 with 1024 dimensions and store all metadata fields as payload attributes in the Qdrant point

### Requirement 2: Malay Ethnic Cultural Guidelines

**User Story:** As a content reviewer targeting Malay audiences, I want cultural rules covering Islamic sensitivities, modesty standards, halal compliance, and aurat rules, so that advertisements respect Malay cultural norms beyond what MCMC regulations require.

#### Acceptance Criteria

1. THE Cultural_Collection SHALL contain at least 15 Guideline_Entry records with ethnicity "malay" and market "malaysia"
2. THE Cultural_Collection SHALL include Malay guidelines covering the following categories at minimum: body_exposure (aurat rules for male and female depictions), modesty (clothing standards in advertising), halal_compliance (non-food halal sensitivities such as cosmetics and lifestyle products), religious_sensitivity (prayer time depictions, mosque imagery usage, Quran handling), suggestive_content (physical intimacy between genders, dance movements), and food_taboos (alcohol adjacency, pork-derived ingredients in non-food products)
3. WHEN a Guideline_Entry has ethnicity "malay" and category "body_exposure", THE guideline_text SHALL specify which body parts are considered aurat and inappropriate for advertising depiction, including but not limited to: female hair, arms above elbow, legs above knee, and male torso
4. WHEN a Guideline_Entry has ethnicity "malay" and category "suggestive_content", THE guideline_text SHALL specify actions considered inappropriate including: applying products to intimate body areas, suggestive body movements, and close physical contact between unrelated males and females
5. THE Cultural_Collection SHALL include at least 5 Guideline_Entry records with ethnicity "malay" and market "singapore" covering Islamic sensitivities specific to the Singaporean Malay community

### Requirement 3: Chinese Ethnic Cultural Guidelines

**User Story:** As a content reviewer targeting Chinese audiences, I want cultural rules covering superstitions, lucky and unlucky numbers, color symbolism, and ancestral respect, so that advertisements avoid cultural missteps with Chinese audiences.

#### Acceptance Criteria

1. THE Cultural_Collection SHALL contain at least 15 Guideline_Entry records with ethnicity "chinese" and market "malaysia"
2. THE Cultural_Collection SHALL include Chinese guidelines covering the following categories at minimum: superstitions (mirrors, clocks as gifts, umbrella indoors), number_symbolism (number 4 avoidance, number 8 preference, pricing considerations), color_symbolism (white for mourning, red for prosperity, black associations), ancestral_respect (depiction of elderly, ancestral tablets, Qing Ming imagery), food_taboos (offerings food context, vegetarian festival periods), and religious_sensitivity (Taoist and Buddhist symbol usage in commercial contexts)
3. WHEN a Guideline_Entry has ethnicity "chinese" and category "number_symbolism", THE guideline_text SHALL specify that the number 4 (associated with death) should be avoided in pricing, product quantities, and phone numbers shown in advertisements, and that the number 8 (associated with prosperity) is preferred
4. WHEN a Guideline_Entry has ethnicity "chinese" and category "color_symbolism", THE guideline_text SHALL specify that white is associated with mourning and funerals, and should not be used as a dominant celebratory color, while red signifies prosperity and good fortune
5. THE Cultural_Collection SHALL include at least 5 Guideline_Entry records with ethnicity "chinese" and market "singapore" covering cultural sensitivities specific to the Singaporean Chinese community

### Requirement 4: Indian Ethnic Cultural Guidelines

**User Story:** As a content reviewer targeting Indian audiences, I want cultural rules covering religious symbols, vegetarianism, caste sensitivity, and sacred imagery, so that advertisements respect Indian cultural norms.

#### Acceptance Criteria

1. THE Cultural_Collection SHALL contain at least 15 Guideline_Entry records with ethnicity "indian" and market "malaysia"
2. THE Cultural_Collection SHALL include Indian guidelines covering the following categories at minimum: religious_sensitivity (Hindu deity depictions, temple imagery, sacred symbols like Om and Swastika), food_taboos (beef avoidance, vegetarianism during festivals, sacred cow imagery), caste_sensitivity (occupational stereotyping, hierarchical depictions), color_symbolism (saffron and white religious significance, vermillion), ancestral_respect (elder depiction, family hierarchy), and gender_norms (married woman symbols like mangalsutra and sindoor in commercial contexts)
3. WHEN a Guideline_Entry has ethnicity "indian" and category "religious_sensitivity", THE guideline_text SHALL specify that Hindu deities and sacred symbols must not be placed on footwear, floor materials, or below waist level, and must not be used to sell alcohol or meat products
4. WHEN a Guideline_Entry has ethnicity "indian" and category "food_taboos", THE guideline_text SHALL specify that beef and beef-derived products must not be shown in contexts targeting Hindu audiences, and that cow imagery must be treated with reverence
5. THE Cultural_Collection SHALL include at least 5 Guideline_Entry records with ethnicity "indian" and market "singapore" covering cultural sensitivities specific to the Singaporean Indian community

### Requirement 5: Culture-Specific Advertising Taboos

**User Story:** As a content reviewer, I want the system to detect advertising taboos related to body exposure and suggestive actions that are culturally inappropriate but not legally prohibited, so that content like applying deodorant to intimate areas is flagged for Malaysian audiences.

#### Acceptance Criteria

1. THE Cultural_Collection SHALL contain Guideline_Entry records with category "body_exposure" that specify which body parts and body-related actions are considered taboo in advertising for each ethnicity
2. THE Cultural_Collection SHALL contain Guideline_Entry records with category "suggestive_content" that specify which physical actions, gestures, and product application methods are considered inappropriate in advertising for each ethnicity
3. WHEN the Compliance_Pipeline evaluates video content, THE RAG_Retriever SHALL use the Pegasus_Description text as the query input to retrieve culturally relevant guidelines that match the visual actions described
4. WHEN a cultural guideline with severity "high" is violated, THE Compliance_Pipeline SHALL flag the violation in the high_risk_indicators array with the corresponding Cultural_Category and a severity of "Severe"
5. WHEN a cultural guideline with severity "medium" is violated, THE Compliance_Pipeline SHALL flag the violation with a severity of "Moderate"
6. WHEN a cultural guideline with severity "low" is violated, THE Compliance_Pipeline SHALL flag the violation with a severity of "Minor"

### Requirement 6: Age Group Targeting

**User Story:** As a content reviewer, I want cultural guidelines tagged with age group applicability, so that the system can apply stricter rules for content targeting children and differentiate adult-only advertising norms.

#### Acceptance Criteria

1. WHEN a Guideline_Entry has age_group "all_ages", THE RAG_Retriever SHALL include the guideline in retrieval results regardless of the target audience of the content being evaluated
2. WHEN a Guideline_Entry has age_group "adults_only", THE RAG_Retriever SHALL include the guideline only when the content being evaluated is targeting adult audiences
3. WHEN a Guideline_Entry has age_group "children", THE RAG_Retriever SHALL include the guideline only when the content being evaluated is targeting audiences that include children
4. WHEN no target age group is specified in the Content_Submission, THE Compliance_Pipeline SHALL default to applying "all_ages" guidelines only
5. THE Content_Submission schema SHALL be extended with an optional target_age_group field accepting values "all_ages", "adults_only", or "children" with a default value of "all_ages"

### Requirement 7: Expanded RAG Retrieval

**User Story:** As a content compliance developer, I want the RAG retrieval expanded from top 5 to top 50 guidelines, so that the system achieves comprehensive coverage and does not miss relevant cultural rules due to limited retrieval.

#### Acceptance Criteria

1. WHEN retrieving guidelines for compliance evaluation, THE RAG_Retriever SHALL retrieve the top 50 guidelines ranked by vector similarity from the Guideline_Store, replacing the current top 5 limit
2. THE RAG_Retriever SHALL retrieve guidelines from both the regulatory collection and the Cultural_Collection for the specified market, combining results into a single ranked list
3. WHEN the combined retrieval returns fewer than 50 results, THE RAG_Retriever SHALL return all available results without error
4. THE RAG_Retriever SHALL pass all 50 retrieved guidelines to the compliance evaluation LLM as context for the evaluation prompt
5. WHEN processing video content, THE RAG_Retriever SHALL use the Pegasus_Description text (the output from TwelveLabs Pegasus video understanding) as the embedding query input
6. WHEN processing image content, THE RAG_Retriever SHALL use the unified content description (vision model output combined with OCR text) as the embedding query input
7. WHEN processing text content, THE RAG_Retriever SHALL use the submitted text content directly as the embedding query input

### Requirement 8: Cultural Guideline Ingestion

**User Story:** As a content compliance developer, I want a structured ingestion process for cultural guidelines, so that new guidelines can be added to the Qdrant vector store with proper metadata and embeddings.

#### Acceptance Criteria

1. WHEN a cultural guidelines CSV file is provided, THE Guideline_Store SHALL parse each row and create a Guideline_Entry with fields: market, ethnicity, age_group, category, severity, and guideline_text
2. WHEN ingesting cultural guidelines, THE Guideline_Store SHALL validate that each row contains all required fields and that field values match the allowed values defined in Requirement 1
3. IF a row in the CSV file contains an invalid field value, THEN THE Guideline_Store SHALL skip that row, log a warning with the row number and invalid field, and continue processing remaining rows
4. WHEN ingesting cultural guidelines, THE Guideline_Store SHALL embed the guideline_text field using Cohere embed-v4 with 1024 dimensions via AWS Bedrock
5. THE Guideline_Store SHALL store cultural guidelines in a dedicated Qdrant collection named "cultural-guidelines" with vector size 1024 and cosine distance metric
6. WHEN the ingestion process completes, THE Guideline_Store SHALL report the total number of guidelines ingested, the number of rows skipped due to validation errors, and the collection name
7. IF the cultural guidelines CSV file is not found or is empty, THEN THE Guideline_Store SHALL return an error indicating the file path and reason for failure without creating or modifying the collection

### Requirement 9: Pipeline File Renaming

**User Story:** As a developer, I want pipeline files renamed with step-number prefixes, so that the execution order is immediately clear from the file names.

#### Acceptance Criteria

1. THE Compliance_Pipeline SHALL rename the pipeline node files to use step-number prefixes in the following order: step1_routing.py (currently router.py), step2_video_analysis.py (currently video_pipeline.py), step3_image_analysis.py (currently image_pipeline.py), step4_text_analysis.py (currently text_pipeline.py), step5_guideline_retrieval.py (currently guideline_retrieval.py), step6_compliance_evaluation.py (currently compliance_evaluation.py), step7_result_formatting.py (currently result_formatting.py)
2. WHEN pipeline files are renamed, THE Compliance_Pipeline SHALL update all internal import statements across the codebase to reference the new file names
3. WHEN pipeline files are renamed, THE Compliance_Pipeline SHALL update the LangGraph orchestrator node registration to reference the new module names
4. THE market_resolver.py file SHALL be merged into step1_routing.py since market resolution is part of the routing decision
5. THE error_handler.py file SHALL be merged into step7_result_formatting.py since error formatting is part of result output

### Requirement 10: Combined Regulatory and Cultural Evaluation

**User Story:** As a content reviewer, I want the compliance evaluation to consider both regulatory guidelines and cultural guidelines together, so that the final compliance score reflects both legal and cultural appropriateness.

#### Acceptance Criteria

1. WHEN evaluating content compliance, THE Compliance_Pipeline SHALL retrieve guidelines from both the regulatory collection (mcmc-guidelines or singapore-imda-asas-guidelines) and the Cultural_Collection (cultural-guidelines) for the specified market
2. THE Compliance_Pipeline SHALL present both regulatory and cultural guidelines to the evaluation LLM in a single prompt, clearly labeling which guidelines are regulatory and which are cultural
3. WHEN a cultural guideline violation is detected, THE Compliance_Pipeline SHALL include it in the high_risk_indicators array with a label distinguishing it from regulatory violations
4. THE Compliance_Pipeline SHALL apply the same scoring formula to cultural violations as regulatory violations — using the category weight and severity multiplier to deduct from the starting score of 100
5. WHEN both regulatory and cultural violations are detected for the same content, THE Compliance_Pipeline SHALL rank all violations by severity (Severe first, then Moderate, then Minor) in the high_risk_indicators array regardless of whether they are regulatory or cultural

### Requirement 11: Ethnicity-Aware Filtering

**User Story:** As a content reviewer, I want to specify the target ethnic audience for content evaluation, so that the system retrieves and applies only the culturally relevant guidelines for that audience.

#### Acceptance Criteria

1. THE Content_Submission schema SHALL be extended with an optional target_ethnicity field accepting values "malay", "chinese", "indian", or "all" with a default value of "all"
2. WHEN target_ethnicity is set to a specific value (not "all"), THE RAG_Retriever SHALL filter cultural guidelines to include only those with matching ethnicity or ethnicity "all"
3. WHEN target_ethnicity is set to "all", THE RAG_Retriever SHALL retrieve cultural guidelines for all ethnicities in the specified market
4. WHEN filtering by ethnicity, THE RAG_Retriever SHALL apply the ethnicity filter as a Qdrant payload filter condition combined with the vector similarity search
5. IF target_ethnicity contains a value not in the allowed set ("malay", "chinese", "indian", "all"), THEN THE Compliance_Pipeline SHALL return a validation error listing the supported ethnicity values
