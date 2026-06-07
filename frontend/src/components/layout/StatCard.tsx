import { useRef, useEffect, type ReactNode } from "react";
import gsap from "gsap";

interface StatCardProps {
  icon: ReactNode;
  value: number;
  label: string;
  sublabel?: string;
}

/**
 * Stat display card using bg-surface-card with icon, animated number value, and label.
 * GSAP animates the number from 0 to the target value on mount.
 */
export function StatCard({ icon, value, label, sublabel }: StatCardProps) {
  const valueRef = useRef<HTMLSpanElement>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (!valueRef.current || hasAnimated.current) return;
    hasAnimated.current = true;

    const obj = { val: 0 };
    gsap.to(obj, {
      val: value,
      duration: 1.2,
      ease: "power2.out",
      onUpdate() {
        if (valueRef.current) {
          valueRef.current.textContent = Math.round(obj.val).toLocaleString();
        }
      },
    });
  }, [value]);

  return (
    <div className="flex items-center gap-4 rounded-2xl border border-border-default bg-surface-card p-5 card-shadow">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface-inset text-text-heading">
        {icon}
      </div>
      <div className="flex flex-col">
        <span
          ref={valueRef}
          className="text-2xl font-semibold tracking-tight text-text-heading"
        >
          0
        </span>
        <span className="text-sm text-text-body">{label}</span>
        {sublabel && (
          <span className="text-xs text-text-caption">{sublabel}</span>
        )}
      </div>
    </div>
  );
}
