/**
 * TaskTableFilters — Inline filter row above the execution history table.
 * Provides type, status, and search filtering with accessible select inputs.
 */

import { Search } from "lucide-react";
import type { TaskFilters, TaskType, TaskStatus } from "./types";

interface TaskTableFiltersProps {
  filters: TaskFilters;
  onFilterChange: (updated: Partial<TaskFilters>) => void;
}

const TYPE_OPTIONS: { label: string; value: TaskType | "all" }[] = [
  { label: "All Types", value: "all" },
  { label: "Generation", value: "generation" },
  { label: "Compliance", value: "compliance" },
  { label: "Remix", value: "remix" },
];

const STATUS_OPTIONS: { label: string; value: TaskStatus | "all" }[] = [
  { label: "All Status", value: "all" },
  { label: "Completed", value: "completed" },
  { label: "Failed", value: "failed" },
  { label: "Processing", value: "processing" },
];

export function TaskTableFilters({ filters, onFilterChange }: TaskTableFiltersProps) {
  return (
    <div className="px-6 py-4 border-b border-border-subtle flex flex-wrap gap-4 items-center">
      {/* Type filter */}
      <div className="flex items-center gap-2">
        <span className="text-code-xs font-bold uppercase text-text-caption tracking-wider">
          Type:
        </span>
        <select
          value={filters.type}
          onChange={(e) => onFilterChange({ type: e.target.value as TaskType | "all" })}
          className="bg-surface-inset border-none rounded-lg text-code-sm font-medium py-1.5 px-3 focus:ring-1 focus:ring-accent-blue text-text-body"
          aria-label="Filter by task type"
        >
          {TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Status filter */}
      <div className="flex items-center gap-2">
        <span className="text-code-xs font-bold uppercase text-text-caption tracking-wider">
          Status:
        </span>
        <select
          value={filters.status}
          onChange={(e) => onFilterChange({ status: e.target.value as TaskStatus | "all" })}
          className="bg-surface-inset border-none rounded-lg text-code-sm font-medium py-1.5 px-3 focus:ring-1 focus:ring-accent-blue text-text-body"
          aria-label="Filter by task status"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Search */}
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-caption" />
        <input
          type="text"
          value={filters.search}
          onChange={(e) => onFilterChange({ search: e.target.value })}
          placeholder="Search Task ID..."
          className="pl-9 pr-4 py-1.5 bg-transparent border-none focus:ring-0 text-label-ui w-48 text-text-body placeholder:text-text-caption"
          aria-label="Search tasks by ID"
        />
      </div>
    </div>
  );
}
