# Image Ad Generation Guide

## Introduction
The Image Ad Generation tool uses Google's Imagen model (`imagen-3.0-generate-002` or `imagen-4.0-generate-001`) via the Google GenAI SDK to generate stunning, high-resolution visual advertisements. It takes a visual prompt, aspect ratio, and audience/market settings to generate culturally appropriate and compliant creatives.

## Steps for Generation
1. **Understand Requirements**: Analyze the target product, concept, market, ethnicity, and age group.
2. **Formulate Visual Prompt**: Craft a detailed visual description focusing on what to show. Modesty guidelines must be strictly followed (e.g. for modest markets, avoid showing models in revealing clothes; instead use product flat-lays or packaging).
3. **Model Parameters**:
   - Model: `imagen-3.0-generate-002` or `imagen-4.0-generate-001`
   - Aspect ratio: Typically `1:1` for square social posts, `9:16` for stories.
   - Number of images: `1`
4. **Local Execution**: Save the generated image bytes to a local temporary path.
5. **S3 Upload**: Upload the image to AWS S3 under `generated_ads/{project_id}/{task_id}/{filename}.png`.
6. **Supabase Record**: Insert a new record into `public.generated_ads` with type `image` and update the canvas node state.
