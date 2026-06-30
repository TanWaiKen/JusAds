/**
 * TaskDetailPanel — Slide-in panel from the right showing task execution details.
 * Displays execution log, metadata tags, and task info.
 */

import { useRef, useEffect } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { X } from "lucide-react";
import type { TaskExecution } from "./types";

gsap.registerPlugin(useGSAP);

interface TaskDetailPanelProps {
  task: TaskExecution | null;
  onClose: () => void;
}

export function TaskDetailPanel({ task, onClose }: TaskDetailPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  const { contextSafe } = useGSAP(() => {}, { scope: panelRef });

  useEffect(() => {
    if (!panelRef.current) return;

    if (task) {
      gsap.to(panelRef.current, {
        x: 0,
        duration: 0.3,
        ease: "power2.out",
      });
    } else {
      gsap.to(panelRef.current, {
        x: "100%",
        duration: 0.25,
        ease: "power2.inOut",
      });
    }
  }, [task]);

  const handleClose = contextSafe(() => {
    if (!panelRef.current) return;
    gsap.to(panelRef.current, {
      x: "100%",
      duration: 0.25,
      ease: "power2.inOut",
      onComplete: onClose,
    });
  });

  return (
    <div
      ref={panelRef}
      className="fixed right-0 top-0 h-full w-96 bg-surface-card shadow-2xl border-l border-border-default z-[60] translate-x-full flex flex-col"
      role="dialog"
      aria-label="Task details"
      aria-hidden={!task}
    >
      {/* Header */}
      <div className="p-6 border-b border-border-subtle flex justify-between items-center">
        <h3 className="text-lg font-bold text-text-heading">Task Details</h3>
        <button
          onClick={handleClose}
          className="p-2 hover:bg-surface-inset rounded-full transition-colors"
          aria-label="Close panel"
        >
          <X size={18} className="text-text-body" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {task && (
          <>
            {/* Task ID */}
            <div>
              <label className="text-[11px] font-bold uppercase text-text-caption tracking-widest">
                Task ID
              </label>
              <p className="mt-1 font-jetbrains text-code-sm font-bold text-accent-blue">
                {task.id}
              </p>
            </div>

            {/* Execution Log */}
            <div>
              <label className="text-[11px] font-bold uppercase text-text-caption tracking-widest">
                Execution Log
              </label>
              <div className="mt-2 p-3 bg-[#0a0a0f] rounded-lg font-jetbrains text-code-xs text-white/70 leading-relaxed">
                <p>[{task.date}] Initializing pipeline...</p>
                <p>[{task.date}] Processing {task.mediaType} asset...</p>
                <p>[{task.date}] Running {task.type} checks...</p>
                <p>[{task.date}] {task.status === "completed" ? "Finalizing output..." : task.status === "failed" ? "Error encountered" : "Still processing..."}</p>
              </div>
            </div>

            {/* Metadata Tags */}
            {task.tags.length > 0 && (
              <div>
                <label className="text-[11px] font-bold uppercase text-text-caption tracking-widest">
                  Metadata
                </label>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {task.tags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex px-2 py-1 rounded bg-surface-inset text-[11px] font-medium text-text-body"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Info */}
            <div className="space-y-3">
              <label className="text-[11px] font-bold uppercase text-text-caption tracking-widest">
                Info
              </label>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-text-caption">Type</span>
                  <span className="text-text-body font-medium capitalize">{task.type}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-caption">Media</span>
                  <span className="text-text-body font-medium capitalize">{task.mediaType}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-caption">Status</span>
                  <span className="text-text-body font-medium capitalize">{task.status}</span>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
