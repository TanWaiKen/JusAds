# Text Ad Generation Guide

## Introduction
The Text Ad Generation tool uses Google's Gemini models (`gemini-2.5-flash` or `gemini-3.5-flash`) via the Google GenAI SDK to generate compelling, persuasive, and culturally tailored advertisement copy, headings, and captions.

## Steps for Generation
1. **Analyze Input**: Evaluate the brand product name, concept, tone, language, target market, audience demographic, and platforms (e.g. TikTok captions need different styling than LinkedIn text ads).
2. **Call Gemini**: Run a prompt asking the model to write multiple versions of headers, hooks, and body copies, ensuring strict cultural compliance.
3. **Local Action**: Format the text block (JSON format with headers, body copy, and hashtags).
4. **S3 Upload**: Optional for pure text, but can be saved as a text/JSON file on AWS S3 under `generated_ads/{project_id}/{task_id}/{filename}.txt`.
5. **Supabase Record**: Insert a new record into `public.generated_ads` with type `text`, and update the canvas node state.
