/**
 * TaskTable — Execution history table with filters, search, and pagination.
 * Columns: Task ID, Type, Metadata, Media, Status, Date.
 */

import { useRef, useMemo } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { TaskTableFilters } from "./TaskTableFilters";
import { TaskRow } from "./TaskRow";
import type { TaskExecution, TaskFilters } from "./types";

gsap.registerPlugin(useGSAP);

const PAGE_SIZE = 5;

interface TaskTableProps {
  tasks: TaskExecution[];
  filters: TaskFilters;
  onFilterChange: (updated: Partial<TaskFilters>) => void;
  currentPage: number;
  onPageChange: (page: number) => void;
  onSelectTask: (taskId: string) => void;
  onDeleteTask: (taskId: string) => void;
}

export function TaskTable({
  tasks,
  filters,
  onFilterChange,
  currentPage,
  onPageChange,
  onSelectTask,
  onDeleteTask,
}: TaskTableProps) {
  const tableRef = useRef<HTMLDivElement>(null);

  const filteredTasks = useMemo(() => {
    return tasks.filter((task) => {
      if (filters.type !== "all" && task.type !== filters.type) return false;
      if (filters.status !== "all" && task.status !== filters.status) return false;
      if (filters.search && !task.id.toLowerCase().includes(filters.search.toLowerCase())) {
        return false;
      }
      return true;
    });
  }, [tasks, filters]);

  const totalPages = Math.max(1, Math.ceil(filteredTasks.length / PAGE_SIZE));
  const paginatedTasks = filteredTasks.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  );

  useGSAP(() => {
    if (paginatedTasks.length > 0) {
      gsap.from(".task-row", {
        y: 12,
        autoAlpha: 0,
        stagger: 0.05,
        duration: 0.3,
        ease: "power2.out",
      });
    }
  }, { scope: tableRef, dependencies: [currentPage, filters.type, filters.status, filters.search] });

  return (
    <div ref={tableRef} className="rounded-2xl border border-border-default bg-surface-card overflow-hidden card-shadow">
      {/* Filters */}
      <TaskTableFilters filters={filters} onFilterChange={onFilterChange} />

      {/* Table Header Label */}
      <div className="px-6 py-4 border-b border-border-subtle flex justify-between items-center bg-surface-panel">
        <h4 className="text-label-ui font-bold text-text-heading">Execution History</h4>
        <span className="text-code-xs text-text-caption">
          {filteredTasks.length} total
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead className="bg-surface-inset/50">
            <tr>
              <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-text-caption">
                Task ID
              </th>
              <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-text-caption">
                Type
              </th>
              <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-text-caption">
                Metadata
              </th>
              <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-text-caption">
                Media
              </th>
              <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-text-caption">
                Status
              </th>
              <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-text-caption">
                Date
              </th>
              <th className="px-6 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {paginatedTasks.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-text-caption text-sm">
                  No tasks match your filters.
                </td>
              </tr>
            ) : (
              paginatedTasks.map((task) => (
                <TaskRow key={task.id} task={task} onSelect={onSelectTask} onDelete={onDeleteTask} />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="px-6 py-4 border-t border-border-subtle flex items-center justify-between bg-surface-panel">
        <p className="text-code-xs text-text-caption">
          Showing {paginatedTasks.length} of {filteredTasks.length} executions
        </p>
        <div className="flex gap-1">
          <button
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage <= 1}
            className="w-8 h-8 flex items-center justify-center rounded border border-border-default hover:bg-surface-inset transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="Previous page"
          >
            <ChevronLeft size={16} />
          </button>
          {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map((page) => (
            <button
              key={page}
              onClick={() => onPageChange(page)}
              className={
                page === currentPage
                  ? "w-8 h-8 flex items-center justify-center rounded bg-primary text-primary-foreground font-jetbrains text-code-xs font-bold"
                  : "w-8 h-8 flex items-center justify-center rounded border border-border-default hover:bg-surface-inset transition-colors font-jetbrains text-code-xs"
              }
              aria-label={`Page ${page}`}
              aria-current={page === currentPage ? "page" : undefined}
            >
              {page}
            </button>
          ))}
          <button
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
            className="w-8 h-8 flex items-center justify-center rounded border border-border-default hover:bg-surface-inset transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="Next page"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
