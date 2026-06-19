/**
 * NewProject — Default dashboard landing page.
 * Shows an "Untitled" project with two mode options:
 * 1. Compliance Check (creates project, then navigates to compliance workflow)
 * 2. Generation from Scratch (coming soon / placeholder)
 *
 * Project is created lazily — only when the user picks a mode.
 */

import { useRef, useState } from "react";
import { useNavigate } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ShieldCheck, Sparkles, Loader2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { API_BASE } from "@/services/complianceApi";

gsap.registerPlugin(useGSAP);

export default function NewProject() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useGSAP(
    () => {
      gsap.from(".mode-card", {
        y: 20,
        autoAlpha: 0,
        stagger: 0.1,
        duration: 0.4,
        ease: "power2.out",
      });
    },
    { scope: containerRef }
  );

  async function handleComplianceCheck() {
    const email = user?.profile?.email ?? "user";
    setIsCreating(true);
    setError(null);

    try {
      console.log(`[NewProject] POST /api/projects → { name: "Untitled", media_type: "compliance", username: "${email}" }`);
      const res = await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "Untitled",
          media_type: "compliance",
          username: email,
        }),
      });

      console.log(`[NewProject] Response status: ${res.status}`);

      if (!res.ok) {
        const body = await res.text();
        console.error(`[NewProject] Error body:`, body);
        throw new Error(`Failed to create project (${res.status})`);
      }

      const data = await res.json();
      console.log(`[NewProject] Project created:`, data);

      // Notify sidebar to refresh its project list
      window.dispatchEvent(new CustomEvent("jusads:project-created"));

      // Navigate to project overview — user picks workflow from there
      navigate(`/dashboard/project/${data.id}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Could not create project";
      console.error("[NewProject] Project creation failed:", err);
      setError(message);
    } finally {
      setIsCreating(false);
    }
  }

  async function handleGenerateFromScratch() {
    const email = user?.profile?.email ?? "user";
    setIsCreating(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "Untitled",
          media_type: "generation",
          username: email,
        }),
      });

      if (!res.ok) {
        const body = await res.text();
        console.error(`[NewProject] Error body:`, body);
        throw new Error(`Failed to create project (${res.status})`);
      }

      const data = await res.json();
      // Notify sidebar to refresh its project list
      window.dispatchEvent(new CustomEvent("jusads:project-created"));

      // Navigate to project overview — user picks workflow from there
      navigate(`/dashboard/project/${data.id}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Could not create project";
      console.error("[NewProject] Project creation failed:", err);
      setError(message);
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div ref={containerRef} className="flex flex-col items-center justify-center min-h-[70vh] px-6">
      {/* Project Title */}
      <p className="font-bold text-body-lg tracking-tight text-text-primary dark:text-white mb-2">
        Untitled
      </p>
      <p className="text-label-ui text-text-caption mb-10">
        Choose how you'd like to start
      </p>

      {/* Error message */}
      {error && (
        <div className="w-full max-w-xl mb-4 rounded-lg bg-accent-error/10 border border-accent-error/30 px-4 py-3 text-code-sm text-accent-error">
          {error}
        </div>
      )}

      {/* Mode Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 w-full max-w-xl">
        {/* Compliance Check */}
        <button
          type="button"
          onClick={handleComplianceCheck}
          disabled={isCreating}
          className="mode-card flex flex-col items-start gap-3 rounded-xl border border-border-default bg-surface-card p-6 text-left card-shadow transition-all duration-200 hover:border-accent-blue hover:shadow-md focus:outline-none focus:ring-2 focus:ring-accent-blue cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isCreating ? (
            <Loader2 size={28} className="text-accent-blue animate-spin" />
          ) : (
            <ShieldCheck size={28} className="text-accent-blue" />
          )}
          <span className="font-bold text-body-md text-text-primary dark:text-white">
            Compliance Check
          </span>
          <span className="text-code-sm text-text-caption leading-relaxed">
            Upload existing content and run compliance analysis against regulatory guidelines.
          </span>
        </button>

        {/* Generation from Scratch */}
        <button
          type="button"
          onClick={handleGenerateFromScratch}
          disabled={isCreating}
          className="mode-card flex flex-col items-start gap-3 rounded-xl border border-border-default bg-surface-card p-6 text-left card-shadow transition-all duration-200 hover:border-accent-amber hover:shadow-md focus:outline-none focus:ring-2 focus:ring-accent-amber cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isCreating ? (
            <Loader2 size={28} className="text-accent-amber animate-spin" />
          ) : (
            <Sparkles size={28} className="text-accent-amber" />
          )}
          <span className="font-bold text-body-md text-text-primary dark:text-white">
            Generate from Scratch
          </span>
          <span className="text-code-sm text-text-caption leading-relaxed">
            Create new ad content from scratch using AI generation tools.
          </span>
        </button>
      </div>
    </div>
  );
}
