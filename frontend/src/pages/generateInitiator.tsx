/**
 * GenerateInitiator — creates a new generation task and redirects to the canvas.
 * Route: /dashboard/project/:projectId/generate
 */

import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router";
import { toast } from "sonner";
import { createGenerationTask } from "@/services/taskApi";

export default function GenerateInitiator() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;

    let cancelled = false;

    async function initiate() {
      try {
        const task = await createGenerationTask(projectId!);
        if (!cancelled) {
          navigate(`/dashboard/project/${projectId}/${task.id}`, { replace: true });
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : "Failed to create generation task";
          setError(message);
          toast.error(message);
        }
      }
    }

    initiate();

    return () => {
      cancelled = true;
    };
  }, [projectId, navigate]);

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3">
        <p className="text-sm text-red-500">{error}</p>
        <button
          className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          onClick={() => navigate(`/dashboard/project/${projectId}`)}
        >
          Back to Project
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full items-center justify-center">
      <p className="text-sm text-muted-foreground">Creating generation task...</p>
    </div>
  );
}
