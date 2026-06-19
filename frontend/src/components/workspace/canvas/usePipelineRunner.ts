/**
 * usePipelineRunner — React hook driving the pure pipeline run logic.
 * Updates node statuses and persists pipeline state via taskApi.
 */

import { useState, useCallback } from "react";
import type { PipelineState, CanvasNode } from "@/components/workspace/canvas/graphModel";
import { runPipeline } from "@/components/workspace/canvas/pipelineRunner";
import { savePipeline } from "@/services/taskApi";

interface UsePipelineRunnerOptions {
  projectId: string;
  taskId: string;
  onStateUpdate: (pipeline: PipelineState) => void;
}

export function usePipelineRunner({ projectId, taskId, onStateUpdate }: UsePipelineRunnerOptions) {
  const [isRunning, setIsRunning] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const defaultExecutor = useCallback(async (node: CanvasNode): Promise<string> => {
    // Stub executor — simulates processing time
    await new Promise((resolve) => setTimeout(resolve, 1000 + Math.random() * 1000));
    return `Output from ${node.label} (${node.type})`;
  }, []);

  const run = useCallback(
    async (pipeline: PipelineState) => {
      setIsRunning(true);
      try {
        const result = await runPipeline(pipeline, defaultExecutor);
        onStateUpdate(result);
        // Persist after run
        try {
          await savePipeline(projectId, taskId, result);
        } catch (saveErr) {
          console.error("Failed to persist pipeline after run:", saveErr);
        }
      } finally {
        setIsRunning(false);
      }
    },
    [defaultExecutor, onStateUpdate, projectId, taskId]
  );

  const save = useCallback(
    async (pipeline: PipelineState) => {
      setIsSaving(true);
      try {
        await savePipeline(projectId, taskId, pipeline);
      } finally {
        setIsSaving(false);
      }
    },
    [projectId, taskId]
  );

  return { run, save, isRunning, isSaving };
}

export default usePipelineRunner;
