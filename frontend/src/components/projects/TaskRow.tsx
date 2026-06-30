/**
 * TaskRow — A single row in the execution history table.
 * Displays task ID, type, metadata tags, media type, status, and date.
 */

import { ExternalLink } from "lucide-react";
import { TaskTypeBadge } from "./TaskTypeBadge";
import { TaskStatusIndicator } from "./TaskStatusIndicator";
import { MediaIcon } from "./MediaIcon";
import type { TaskExecution } from "./types";

interface TaskRowProps {
  task: TaskExecution;
  onSelect: (taskId: string) => void;
}

export function TaskRow({ task, onSelect }: TaskRowProps) {
  return (
    <tr
      className="task-row hover:bg-surface-inset cursor-pointer transition-colors group"
      onClick={() => onSelect(task.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(task.id);
        }
      }}
      aria-label={`View details for task ${task.id}`}
    >
      {/* Task ID */}
      <td className="px-6 py-4">
        <span className="font-jetbrains text-[12px] font-bold text-accent-blue">
          {task.id}
        </span>
      </td>

      {/* Type */}
      <td className="px-6 py-4">
        <TaskTypeBadge type={task.type} />
      </td>

      {/* Metadata Tags */}
      <td className="px-6 py-4">
        <div className="flex flex-wrap gap-1">
          {task.tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex px-1.5 py-0.5 rounded bg-surface-inset text-[10px] font-medium text-text-body leading-tight"
            >
              {tag}
            </span>
          ))}
        </div>
      </td>

      {/* Media Type */}
      <td className="px-6 py-4">
        <MediaIcon mediaType={task.mediaType} />
      </td>

      {/* Status */}
      <td className="px-6 py-4">
        <TaskStatusIndicator status={task.status} />
      </td>

      {/* Date */}
      <td className="px-6 py-4">
        <span className="text-[12px] text-text-body font-medium">{task.date}</span>
      </td>

      {/* Arrow */}
      <td className="px-6 py-4 text-right">
        <ExternalLink
          size={14}
          className="text-text-caption opacity-0 group-hover:opacity-100 transition-opacity"
        />
      </td>
    </tr>
  );
}
