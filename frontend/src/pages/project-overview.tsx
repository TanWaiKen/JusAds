/**
 * ProjectOverviewPage — displays project metadata and unified task history.
 */

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ShieldCheck, Sparkles, Clock, Pencil, Check, X, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { listTasks, updateProjectName, deleteTask } from "@/services/taskApi";
import type { TaskSummary, ProjectResponse } from "@/services/taskApi";
import { API_BASE } from "@/services/taskApi";
import { useAuth } from "@/hooks/useAuth";

interface ProjectMeta {
  id: string;
  name: string;
  media_type: string;
  created_at: string;
}

export default function ProjectOverviewPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [project, setProject] = useState<ProjectMeta | null>(null);
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Inline edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState("");

  const containerRef = useRef<HTMLDivElement>(null);

  const fetchData = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);

    try {
      // Fetch project metadata using the authenticated user's email
      const email = user?.profile?.email ?? "demo_user";
      const projectRes = await fetch(`${API_BASE}/api/projects?username=${encodeURIComponent(email)}`);
      if (!projectRes.ok) throw new Error("Failed to fetch projects");
      const projects: ProjectMeta[] = await projectRes.json();
      const proj = projects.find((p) => p.id === projectId);

      if (!proj) {
        toast.error("Project not found");
        navigate("/dashboard", { replace: true });
        return;
      }

      setProject(proj);
      setEditName(proj.name);

      // Fetch tasks — gracefully handle if tasks table doesn't exist yet
      try {
        const taskList = await listTasks(projectId);
        setTasks(taskList);
      } catch {
        // Tasks API may fail if migration hasn't been applied — show empty list
        setTasks([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load project");
    } finally {
      setLoading(false);
    }
  }, [projectId, navigate, user]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // GSAP staggered entrance for task rows
  useGSAP(
    () => {
      if (!loading && tasks.length > 0) {
        gsap.from(".task-row", {
          opacity: 0,
          y: 20,
          duration: 0.3,
          stagger: 0.05,
          ease: "power2.out",
        });
      }
    },
    { scope: containerRef, dependencies: [loading, tasks.length] }
  );

  const handleNameSubmit = async () => {
    if (!projectId || !editName.trim()) return;

    const originalName = project?.name ?? "";
    // Optimistic update
    if (project) setProject({ ...project, name: editName.trim() });
    setIsEditing(false);

    try {
      await updateProjectName(projectId, editName.trim());
    } catch {
      // Revert on failure
      if (project) setProject({ ...project, name: originalName });
      toast.error("Failed to update project name");
    }
  };

  const handleTaskClick = (taskId: string) => {
    navigate(`/dashboard/project/${projectId}/${taskId}`);
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading project...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3">
        <p className="text-sm text-red-500">{error}</p>
        <button
          className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          onClick={fetchData}
        >
          Retry
        </button>
      </div>
    );
  }

  if (!project) return null;

  return (
    <div ref={containerRef} className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Project header */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          {isEditing ? (
            <div className="flex items-center gap-2">
              <input
                className="rounded-md border bg-background px-2 py-1 text-2xl font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleNameSubmit();
                  if (e.key === "Escape") {
                    setIsEditing(false);
                    setEditName(project.name);
                  }
                }}
                autoFocus
              />
              <button
                className="rounded p-1 hover:bg-accent"
                onClick={handleNameSubmit}
                aria-label="Confirm"
              >
                <Check className="h-4 w-4 text-green-500" />
              </button>
              <button
                className="rounded p-1 hover:bg-accent"
                onClick={() => {
                  setIsEditing(false);
                  setEditName(project.name);
                }}
                aria-label="Cancel"
              >
                <X className="h-4 w-4 text-muted-foreground" />
              </button>
            </div>
          ) : (
            <button
              className="group flex items-center gap-2"
              onClick={() => setIsEditing(true)}
            >
              <p className="text-2xl font-bold text-foreground">{project.name}</p>
              <Pencil className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
            </button>
          )}
        </div>
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span className="flex items-center gap-1 capitalize">
            {project.media_type === "compliance" ? (
              <ShieldCheck className="h-4 w-4" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {project.media_type}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="h-4 w-4" />
            {new Date(project.created_at).toLocaleDateString()}
          </span>
        </div>
      </div>

      {/* Task history */}
      <div className="space-y-3">
        <p className="text-lg font-semibold text-foreground">Task History</p>

        {tasks.length === 0 ? (
          <div className="rounded-lg border border-dashed p-8 text-center space-y-4">
            <p className="text-sm text-muted-foreground">No tasks yet</p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={() => navigate(`/dashboard/project/${projectId}/compliance`)}
                className="flex items-center gap-2 rounded-lg bg-blue-500/10 border border-blue-500/30 px-4 py-2.5 text-sm font-semibold text-blue-600 dark:text-blue-400 hover:bg-blue-500/20 transition-colors"
              >
                <ShieldCheck className="h-4 w-4" />
                Start Compliance Check
              </button>
              <button
                onClick={() => navigate(`/dashboard/project/${projectId}/generate`)}
                className="flex items-center gap-2 rounded-lg bg-amber-500/10 border border-amber-500/30 px-4 py-2.5 text-sm font-semibold text-amber-600 dark:text-amber-400 hover:bg-amber-500/20 transition-colors"
              >
                <Sparkles className="h-4 w-4" />
                Generate from Scratch
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            {tasks.map((task) => (
              <div
                key={task.id}
                className="task-row flex w-full items-center gap-3 rounded-lg border bg-card p-4 transition-colors hover:bg-accent group"
              >
                <button
                  className="flex items-center gap-3 flex-1 min-w-0 text-left"
                  onClick={() => handleTaskClick(task.id)}
                >
                  {task.type === "compliance" ? (
                    <ShieldCheck className="h-5 w-5 shrink-0 text-blue-500" />
                  ) : (
                    <Sparkles className="h-5 w-5 shrink-0 text-purple-500" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {task.summary}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(task.created_at).toLocaleString()}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground capitalize">
                    {task.status}
                  </span>
                </button>
                <button
                  className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded hover:bg-red-500/10"
                  title="Delete task"
                  onClick={async (e) => {
                    e.stopPropagation();
                    if (!projectId) return;
                    if (!confirm("Delete this task?")) return;
                    try {
                      await deleteTask(projectId, task.id);
                      setTasks((prev) => prev.filter((t) => t.id !== task.id));
                      toast.success("Task deleted");
                    } catch {
                      toast.error("Failed to delete task");
                    }
                  }}
                >
                  <Trash2 className="h-4 w-4 text-muted-foreground hover:text-red-500" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
