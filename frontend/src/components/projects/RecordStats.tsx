/**
 * RecordStats — Bento-style stats grid for the Project Records page.
 * Displays Total Tasks, Successful Generations, and Compliance Passes
 * with animated number count-up via GSAP.
 */

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { BarChart3, Sparkles, ShieldCheck } from "lucide-react";
import type { ProjectStats } from "./types";

gsap.registerPlugin(useGSAP);

interface RecordStatsProps {
  stats: ProjectStats;
}

function AnimatedValue({ value }: { value: number }) {
  const ref = useRef<HTMLHeadingElement>(null);

  useGSAP(() => {
    if (!ref.current) return;
    const obj = { val: 0 };
    gsap.to(obj, {
      val: value,
      duration: 1.2,
      ease: "power2.out",
      onUpdate() {
        if (ref.current) {
          ref.current.textContent = Math.round(obj.val).toLocaleString();
        }
      },
    });
  }, { scope: ref, dependencies: [value] });

  return (
    <h3 ref={ref} className="text-2xl font-semibold tracking-tight text-text-heading">
      0
    </h3>
  );
}

export function RecordStats({ stats }: RecordStatsProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    gsap.from(".stat-card", {
      y: 30,
      autoAlpha: 0,
      stagger: 0.08,
      duration: 0.4,
      ease: "power2.out",
    });
  }, { scope: containerRef });

  return (
    <div ref={containerRef} className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {/* Total Tasks */}
      <div className="stat-card rounded-2xl border border-border-default bg-surface-card p-6 card-shadow transition-all hover:shadow-lg">
        <div className="flex justify-between items-start mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-inset text-text-heading">
            <BarChart3 size={20} />
          </div>
          <span className="font-jetbrains text-code-xs text-accent-emerald bg-accent-emerald/10 px-2 py-1 rounded">
            {stats.totalTasksDelta}
          </span>
        </div>
        <p className="text-code-xs font-semibold uppercase tracking-wider text-text-caption mb-1">
          Total Tasks
        </p>
        <AnimatedValue value={stats.totalTasks} />
      </div>

      {/* Successful Generations */}
      <div className="stat-card rounded-2xl border border-border-default bg-surface-card p-6 card-shadow transition-all hover:shadow-lg">
        <div className="flex justify-between items-start mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-inset text-accent-blue">
            <Sparkles size={20} />
          </div>
          <span className="font-jetbrains text-code-xs text-accent-blue bg-accent-blue/10 px-2 py-1 rounded">
            {stats.successfulGenerationsLabel}
          </span>
        </div>
        <p className="text-code-xs font-semibold uppercase tracking-wider text-text-caption mb-1">
          Successful Generations
        </p>
        <AnimatedValue value={stats.successfulGenerations} />
      </div>

      {/* Compliance Passes */}
      <div className="stat-card rounded-2xl border border-border-default bg-surface-card p-6 card-shadow transition-all hover:shadow-lg">
        <div className="flex justify-between items-start mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-inset text-accent-pink">
            <ShieldCheck size={20} />
          </div>
          <span className="font-jetbrains text-code-xs text-accent-pink bg-accent-pink/10 px-2 py-1 rounded">
            {stats.compliancePassRate}
          </span>
        </div>
        <p className="text-code-xs font-semibold uppercase tracking-wider text-text-caption mb-1">
          Compliance Passes
        </p>
        <AnimatedValue value={stats.compliancePasses} />
      </div>
    </div>
  );
}
