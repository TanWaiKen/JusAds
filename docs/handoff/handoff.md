# JusAds Generation Canvas Handoff Documentation

This document outlines the features built for the AI Ad Generation pipeline, details what was implemented correctly, analyzes limitations (what was "done wrong"), and provides concrete implementation blueprints for future enhancements (interactive canvas edits and a fixed-pipeline workflow).

---

## 1. What Has Been Done

*   **Multi-Agentic Generation Pipeline**: Integrated specialized local agents inside [generation_agent.py](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/backend/agent/generation_agent.py):
    *   **Text Agent**: Generates compliance-checked headlines, body copy, and hashtags.
    *   **Image Agent**: Calls Imagen 4.0 (with a custom PIL gradient generator fallback).
    *   **Audio Agent**: Generates voiceover audio via ElevenLabs.
    *   **Video Agent**: Stitches image and audio files into MP4 commercials via local `ffmpeg`.
*   **Real-time SSE Chat Stream**: Replaced synchronous polling with a Server-Sent Events (SSE) stream in [generation.py](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/backend/routes/generation.py). The agent streams reasoning text to the user first, executes generation tools in the background, and pushes status updates and the final canvas graph.
*   **Conversational Memory**: The orchestrator saves and retrieves `chat_history` from the task's `pipeline_state` in Supabase. It automatically trims history to the last 10 turns to avoid database overflow.
*   **Multimodal Reference Uploads**: Added a paperclip upload mechanism in [ChatbotPanel.tsx](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/frontend/src/components/workspace/canvas/ChatbotPanel.tsx) that uploads reference assets to S3 and passes them to Gemini as image/video context parts.
*   **Stitch-style Zoomable Dot Grid**: Integrated an infinite CSS-based dot grid on the canvas background inside [CanvasViewport.tsx](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/frontend/src/components/workspace/canvas/CanvasViewport.tsx) that automatically pans and scales with the viewport zoom level.
*   **Mandatory Onboarding Gate**: Configured [dashboard.tsx](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/frontend/src/pages/dashboard.tsx) to query the user's business profile status. If onboarding is incomplete, the user is redirected to a premium-styled [onboarding.tsx](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/frontend/src/pages/onboarding.tsx) form.

---

## 2. What Has Been Done Correctly (Strengths)

1.  **Coordinate Math Fix**: Canvas node dragging calculates offsets in scale-invariant canvas space using `screenToCanvas`. Dragging remains perfectly aligned with the mouse cursor at any zoom or pan setting.
2.  **Stateless SSE & Memory**: History memory is persisted in PostgreSQL JSONB (`pipeline_state.chat_history`) on task completion. This keeps the backend server completely stateless and prevents memory leakage across sessions.
3.  **High-Fidelity Audio**: Switched ElevenLabs synthesis to `eleven_multilingual_v3`, which supports expressive text indicators like `[laugh]` or `[excited]`.
4.  **Aesthetic Cohesion**: Styled the onboarding screen to match the landing page using dark headers (H2), rounded card styling, gradient borders, and brutalist-styled buttons.

---

## 3. What Has Been Done Wrong (Limitations / Areas for Improvement)

1.  **Agent Dependency on Mock Fallbacks**:
    *   If Vertex AI credentials or ElevenLabs API keys are not supplied, the agents fall back to generating dummy files.
    *   If the local system lacks `ffmpeg`, the video agent writes a mock MP4 file.
2.  **Overlap of Static Node Placements**:
    *   Coordinates are mapped to static positions (e.g. `text` node is always at `(300, 50)`).
    *   If the user runs multiple generation cycles, nodes of the same category will stack directly on top of each other.
3.  **Read-Only Canvas Properties**:
    *   The canvas is currently unidirectional: the AI creates the nodes, but the user cannot edit node properties or delete nodes directly on the canvas without asking the chatbot.

---

## 4. Future Implementation Plan

### A. How to Add Canvas Node Deletion & Property Updates

To make the canvas fully interactive, we can implement direct modifications:

#### 1. Node Deletion Blueprint
1.  **UI Trigger**: Add a delete button (trash icon) to the header bar of [CanvasNode.tsx](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/frontend/src/components/workspace/canvas/CanvasNode.tsx):
    ```tsx
    <button 
      onClick={(e) => { e.stopPropagation(); onDelete(node.id); }}
      className="p-1 rounded text-muted-foreground hover:text-error hover:bg-muted"
    >
      <Trash2 size={12} />
    </button>
    ```
2.  **Action Dispatcher**: Wire the `onDelete` handler to dispatch a new action:
    ```typescript
    dispatch({ type: "DELETE_NODE", nodeId });
    ```
3.  **State Reducer**: Add the `DELETE_NODE` case to `useCanvasGraph.ts`:
    *   Filter out the target node from `nodes`.
    *   Filter out any connected edges in `edges` where `from === nodeId` or `to === nodeId`.
    *   If `selectedNodeId === nodeId`, set it to `null`.

#### 2. Node Property Updates Blueprint
1.  **Inspector Inputs**: Update [InspectorPanel.tsx](file:///c:/Users/tanwa/OneDrive/TWK%20developer/Documents/Langhub-main/frontend/src/components/workspace/canvas/InspectorPanel.tsx). When a node is selected, render editable text fields or sliders:
    ```tsx
    <input 
      type="text" 
      value={node.label} 
      onChange={(e) => onUpdateProps(node.id, { label: e.target.value })} 
    />
    ```
2.  **State Reducer**: Dispatch an update action:
    ```typescript
    dispatch({ type: "UPDATE_NODE_PROPS", nodeId, props: { ... } });
    ```
    And update the target node's `props` or `label` inside the graph state array.

---

### B. How to Create a Fixed Video Pipeline Workflow

If a user prefers a deterministic pipeline over agentic decision-making, we can build a "Fixed Pipeline" mode:

#### 1. Workflow Template Definitions
Define a static pipeline schema on the backend (e.g. `video_pipeline_workflow.json`):
```json
{
  "steps": [
    { "id": "step-1", "name": "Text Generation", "agent": "text" },
    { "id": "step-2", "name": "Voiceover Generation", "agent": "audio", "requires": "step-1" },
    { "id": "step-3", "name": "Image Asset Generation", "agent": "image" },
    { "id": "step-4", "name": "Video Compiling", "agent": "video", "requires": ["step-2", "step-3"] }
  ]
}
```

#### 2. Pre-built Canvas initialization
When the user clicks "Start Predefined Workflow":
1.  Initialize the canvas immediately with all five skeleton nodes (Input, Text, Audio, Image, Video, Output) in their correct positions.
2.  Set their statuses to `"idle"`.
3.  Add all necessary edge connections beforehand so the user sees the full blueprint layout from the start.

#### 3. Predefined Sequential Execution Runner
Instead of calling the chatbot agent, execute a linear script `run_fixed_pipeline(task_id)`:
1.  **Step 1**: Execute `generate_text_ad_content` -> set Text node status to `"done"`.
2.  **Step 2**: Trigger `generate_audio_ad_content` feeding in the generated copy -> set Audio node status to `"done"`.
3.  **Step 3**: Trigger `generate_image_ad_content` -> set Image node status to `"done"`.
4.  **Step 4**: Trigger `generate_video_ad_content` passing the completed S3 image and audio URLs -> set Video node status to `"done"`.
5.  **Final**: Populate the output node and mark the task status as `"completed"`.
6.  This ensures a 100% predictable output structure every time, skipping orchestrator parsing errors.
