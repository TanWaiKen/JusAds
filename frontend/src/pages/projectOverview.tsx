/**
 * ProjectOverviewPage — Project Records / Audit trail view.
 *
 * Displays project stats, filterable execution history table, task detail panel,
 * and active processing status. Matches the Figma task.html design.
 */

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { useParams, useNavigate } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Filter, Download, Pencil, Check, X, Plus, ShieldCheck, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { listTasks, updateProjectName, deleteTask } from "@/services/taskApi";
import type { TaskSummary } from "@/services/taskApi";
import { API_BASE } from "@/services/taskApi";
import { useAuth } from "@/hooks/useAuth";
import {
  RecordStats,
  TaskTable,
} from "@/components/projects";
import type {
  TaskExecution,
  ProjectStats,
  TaskFilters,
} from "@/components/projects";

gsap.registerPlugin(useGSAP);

interface ProjectMeta {
  id: string;
  name: string;
  owner_email: string;
  description: string | null;
  created_at: string;
}

/** Maps a TaskSummary from the API to the UI's TaskExecution shape. */
function mapTaskToExecution(task: TaskSummary): TaskExecution {
  const statusMap: Record<string, TaskExecution["status"]> = {
    completed: "completed",
    checked: "completed",
    reviewed: "completed",
    remixed: "completed",
    failed: "failed",
    error: "failed",
    created: "processing",
    processing: "processing",
  };

  // Use media_type from compliance metadata, or derive from summary
  let mediaType: TaskExecution["mediaType"] = "video";
  if (task.media_type) {
    mediaType = task.media_type as TaskExecution["mediaType"];
  } else {
    const lower = (task.summary ?? "").toLowerCase();
    if (lower.includes("image") || lower.includes("photo")) mediaType = "image";
    else if (lower.includes("audio") || lower.includes("sound")) mediaType = "audio";
    else if (lower.includes("text") || lower.includes("copy")) mediaType = "text";
  }

  // Build tags from real compliance metadata fields
  const tags: string[] = [];
  if (task.market) tags.push(task.market);
  if (task.ethnicity) tags.push(task.ethnicity);
  if (task.age_group) tags.push(task.age_group);
  if (task.platform && task.platform !== "general") tags.push(task.platform);

  return {
    id: `TX-${task.id.slice(0, 4).toUpperCase()}`,
    realId: task.id,
    type: task.type === "compliance" ? "compliance" : "generation",
    mediaType,
    status: statusMap[task.status] ?? "completed",
    tags,
    date: new Date(task.created_at).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }),
  };
}

export default function ProjectOverviewPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [project, setProject] = useState<ProjectMeta | null>(null);
  const [tasks, setTasks] = useState<TaskExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Inline edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState("");

  const [filters, setFilters] = useState<TaskFilters>({
    type: "all",
    status: "all",
    search: "",
  });
  const [currentPage, setCurrentPage] = useState(1);

  const containerRef = useRef<HTMLDivElement>(null);

  // Compute stats from tasks
  const stats: ProjectStats = useMemo(() => {
    const total = tasks.length;
    const generations = tasks.filter((t) => t.type === "generation" && t.status === "completed").length;
    const passes = tasks.filter((t) => t.type === "compliance" && t.status === "completed").length;
    const passRate = total > 0 ? ((passes / total) * 100).toFixed(1) : "0";

    return {
      totalTasks: total,
      totalTasksDelta: total > 0 ? `${total} total` : "No tasks yet",
      successfulGenerations: generations,
      successfulGenerationsLabel: generations > 0 ? "High Quality" : "—",
      compliancePasses: passes,
      compliancePassRate: total > 0 ? `${passRate}% Pass Rate` : "—",
    };
  }, [tasks]);

  const fetchData = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);

    try {
      const email = user?.profile?.email ?? "demo_user";

      // Fetch project metadata
      const projectRes = await fetch(
        `${API_BASE}/api/projects?username=${encodeURIComponent(email)}`
      );
      if (!projectRes.ok) throw new Error("Failed to fetch projects");
      const projects: ProjectMeta[] = await projectRes.json();
      const proj = projects.find((p) => p.id === projectId);

      if (!proj) {
        toast.error("Project not found");
        navigate("/not-found", {
          replace: true,
          state: { type: "not_found", message: "This project doesn't exist or has been deleted." },
        });
        return;
      }

      if (proj.owner_email && proj.owner_email !== email) {
        navigate("/not-found", {
          replace: true,
          state: { type: "unauthorized", message: "This project belongs to another account." },
        });
        return;
      }

      setProject(proj);
      setEditName(proj.name);

      // Fetch tasks
      try {
        const taskList = await listTasks(projectId, email);
        setTasks(taskList.map(mapTaskToExecution));
      } catch (err) {
        if (err instanceof Error && err.message.includes("403")) {
          navigate("/not-found", {
            replace: true,
            state: { type: "unauthorized", message: "Access denied." },
          });
          return;
        }
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

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [filters]);

  // Page entrance animation
  useGSAP(() => {
    if (!loading) {
      gsap.from(".page-header", {
        y: 20,
        autoAlpha: 0,
        duration: 0.5,
        ease: "power2.out",
      });
    }
  }, { scope: containerRef, dependencies: [loading] });

  const handleFilterChange = useCallback((updated: Partial<TaskFilters>) => {
    setFilters((prev) => ({ ...prev, ...updated }));
  }, []);

  const handleSelectTask = useCallback((taskId: string) => {
    // Find the task with this display ID and navigate using its real ID
    const task = tasks.find((t) => t.id === taskId);
    if (task && projectId) {
      navigate(`/dashboard/project/${projectId}/${task.realId}`);
    }
  }, [tasks, projectId, navigate]);

  const handleDeleteTask = useCallback(async (taskId: string) => {
    const task = tasks.find((t) => t.id === taskId);
    if (!task || !projectId) return;
    if (!confirm(`Delete task ${task.id} and its generated media? This cannot be undone.`)) return;

    try {
      await deleteTask(projectId, task.realId);
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
      toast.success("Task deleted");
    } catch {
      toast.error("Failed to delete task");
    }
  }, [tasks, projectId]);

  const handleNameSubmit = async () => {
    if (!projectId || !editName.trim()) return;
    const originalName = project?.name ?? "";
    if (project) setProject({ ...project, name: editName.trim() });
    setIsEditing(false);

    try {
      await updateProjectName(projectId, editName.trim());
    } catch {
      if (project) setProject({ ...project, name: originalName });
      toast.error("Failed to update project name");
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-text-caption">Loading project...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3">
        <p className="text-sm text-accent-error">{error}</p>
        <button
          className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground"
          onClick={fetchData}
        >
          Retry
        </button>
      </div>
    );
  }

  if (!project) return null;

  return (
      <div ref={containerRef} className="flex-1 p-8 max-w-[1200px] mx-auto w-full">
        {/* Page Header */}
        <div className="page-header mb-10">
          <div className="flex justify-between items-end mb-8">
            <div>
              {/* Editable project name */}
              <div className="flex items-center gap-2 mb-1">
                {isEditing ? (
                  <div className="flex items-center gap-2">
                    <input
                      className="rounded-lg border border-border-default bg-surface-card px-3 py-1.5 text-2xl font-semibold tracking-tight text-text-heading focus:outline-none focus:ring-2 focus:ring-accent-blue"
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
                      className="rounded p-1 hover:bg-surface-inset"
                      onClick={handleNameSubmit}
                      aria-label="Confirm name"
                    >
                      <Check size={16} className="text-accent-emerald" />
                    </button>
                    <button
                      className="rounded p-1 hover:bg-surface-inset"
                      onClick={() => { setIsEditing(false); setEditName(project.name); }}
                      aria-label="Cancel edit"
                    >
                      <X size={16} className="text-text-caption" />
                    </button>
                  </div>
                ) : (
                  <button
                    className="group flex items-center gap-2"
                    onClick={() => setIsEditing(true)}
                  >
                    <h2 className="text-2xl font-semibold tracking-tight text-text-heading">
                      {project.name}
                    </h2>
                    <Pencil size={14} className="text-text-caption opacity-0 group-hover:opacity-100 transition-opacity" />
                  </button>
                )}
              </div>
              <p className="text-sm text-text-body">
                Audit trail for{" "}
                <code className="font-jetbrains text-code-sm bg-surface-inset px-2 py-0.5 rounded text-text-heading">
                  {project.id.slice(0, 8).toUpperCase()}
                </code>
                {" • "}
                <span className="text-text-body">
                  Created {new Date(project.created_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </span>
              </p>
            </div>
            <div className="flex gap-2">
              <div className="relative group">
                <button
                  className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-label-ui font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  <Plus size={16} />
                  New Task
                </button>
                <div className="absolute right-0 top-full mt-1 w-48 rounded-lg border border-border-default bg-surface-card shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
                  <button
                    onClick={() => navigate(`/dashboard/project/${projectId}/compliance`)}
                    className="flex items-center gap-2 w-full px-4 py-2.5 text-sm text-text-body hover:bg-surface-inset rounded-t-lg transition-colors"
                  >
                    <ShieldCheck size={14} />
                    Compliance Check
                  </button>
                  <button
                    onClick={() => navigate(`/dashboard/project/${projectId}/generate`)}
                    className="flex items-center gap-2 w-full px-4 py-2.5 text-sm text-text-body hover:bg-surface-inset rounded-b-lg transition-colors"
                  >
                    <Sparkles size={14} />
                    Generate Ad
                  </button>
                </div>
              </div>
              <button className="flex items-center gap-2 rounded-lg border border-border-default bg-surface-card px-4 py-2 text-label-ui font-medium hover:bg-surface-inset transition-colors">
                <Filter size={16} />
                Filter
              </button>
              <button className="flex items-center gap-2 rounded-lg border border-border-default bg-surface-card px-4 py-2 text-label-ui font-medium hover:bg-surface-inset transition-colors">
                <Download size={16} />
                Export
              </button>
            </div>
          </div>

          {/* Stats Grid */}
          <RecordStats stats={stats} />
        </div>

        {/* Execution History Table */}
        <TaskTable
          tasks={tasks}
          filters={filters}
          onFilterChange={handleFilterChange}
          currentPage={currentPage}
          onPageChange={setCurrentPage}
          onSelectTask={handleSelectTask}
          onDeleteTask={handleDeleteTask}
        />
      </div>
  );
}
