# Carousel Ad Generation Guide

## Introduction
The Carousel Ad tool creates a sequence of related visual panels (typically 3 to 5 images) that a user swipes through. This format is ideal for storytelling, product features, or step-by-step guides.

## Storyboarding Panel Structure
- **Panel 1 (The Hook)**: Arresting image + bold question or statement.
- **Panel 2 (The Detail/Value)**: Showcases a primary feature or benefit.
- **Panel 3 (The Proof/Demo)**: Demonstration or comparative highlight.
- **Panel 4 (The Secondary Benefit)**: Additional value proposition or testimonial.
- **Panel 5 (The Action)**: Clear conversion panel with promotional pricing and a CTA button.

## Generation Execution
1. Gemini generates a 5-part storyboard sequence containing specific visual descriptions for each frame.
2. The Image Creator loops 5 times to generate individual S3 keys.
3. The result is linked under parent-child dependencies using `parent_ad_id` in Supabase.
