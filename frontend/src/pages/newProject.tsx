/**
 * NewProject — Project creation page.
 * Step 1: User enters a project title.
 * Step 2: User picks a mode (Compliance Check / Generate from Scratch).
 * Project is created lazily — only when the user picks a mode.
 */

import { useRef, useState } from "react";
import { useNavigate } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ShieldCheck, Sparkles, Loader2, ArrowLeft } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { API_BASE } from "@/services/complianceApi";

gsap.registerPlugin(useGSAP);

export default function NewProject() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);

  const [step, setStep] = useState<1 | 2>(1);
  const [projectName, setProjectName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useGSAP(
    () => {
      gsap.from(".step-content", {
        y: 20,
        autoAlpha: 0,
        duration: 0.4,
        ease: "power2.out",
      });
    },
    { scope: containerRef, dependencies: [step] }
  );

  function handleContinue() {
    if (projectName.trim()) {
      setStep(2);
    }
  }

  async function handleCreate(mediaType: "compliance" | "generation") {
    const email = user?.profile?.email ?? "user";
    setIsCreating(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: projectName.trim(),
          username: email,
        }),
      });

      if (!res.ok) {
        const body = await res.text();
        console.error("[NewProject] Error body:", body);
        throw new Error(`Failed to create project (${res.status})`);
      }

      const data = await res.json();

      // Notify sidebar to refresh its project list
      window.dispatchEvent(new CustomEvent("jusads:project-created"));

      // Navigate to the appropriate workspace
      if (mediaType === "compliance") {
        navigate(`/dashboard/project/${data.id}/compliance`);
      } else {
        navigate(`/dashboard/project/${data.id}/generate`);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Could not create project";
      setError(message);
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div ref={containerRef} className="flex flex-col items-center justify-center min-h-[70vh] px-6">
      {/* Error message */}
      {error && (
        <div className="w-full max-w-xl mb-4 rounded-lg bg-accent-error/10 border border-accent-error/30 px-4 py-3 text-code-sm text-accent-error">
          {error}
        </div>
      )}

      {/* Step 1: Name the project */}
      {step === 1 && (
        <div className="step-content w-full max-w-md space-y-6 text-center">
          <div>
            <h2 className="text-xl font-bold text-text-heading mb-1">
              Create new project
            </h2>
            <p className="text-label-ui text-text-caption">
              Give your project a name to get started.
            </p>
          </div>

          <input
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleContinue();
            }}
            placeholder="My Ad Campaign"
            className="w-full rounded-lg border border-border-default bg-surface-card px-4 py-3 text-body-md text-text-heading placeholder:text-text-caption focus:outline-none focus:ring-2 focus:ring-accent-blue"
            autoFocus
          />

          <button
            type="button"
            onClick={handleContinue}
            disabled={!projectName.trim()}
            className="w-full rounded-lg bg-primary px-4 py-3 text-label-ui font-semibold text-primary-foreground disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary/90 transition-colors"
          >
            Continue
          </button>
        </div>
      )}

      {/* Step 2: Choose mode */}
      {step === 2 && (
        <div className="step-content w-full max-w-xl space-y-6 text-center">
          <div>
            <h2 className="text-xl font-bold text-text-heading mb-1">
              {projectName.trim()}
            </h2>
            <p className="text-label-ui text-text-caption">
              Choose how you'd like to start
            </p>
          </div>

          {/* Mode Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {/* Compliance Check */}
            <button
              type="button"
              onClick={() => handleCreate("compliance")}
              disabled={isCreating}
              className="flex flex-col items-start gap-3 rounded-xl border border-border-default bg-surface-card p-6 text-left card-shadow transition-all duration-200 hover:border-accent-blue hover:shadow-md focus:outline-none focus:ring-2 focus:ring-accent-blue disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isCreating ? (
                <Loader2 size={28} className="text-accent-blue animate-spin" />
              ) : (
                <ShieldCheck size={28} className="text-accent-blue" />
              )}
              <span className="font-bold text-body-md text-text-heading">
                Compliance Check
              </span>
              <span className="text-code-sm text-text-caption leading-relaxed">
                Upload existing content and run compliance analysis against regulatory guidelines.
              </span>
            </button>

            {/* Generation from Scratch */}
            <button
              type="button"
              onClick={() => handleCreate("generation")}
              disabled={isCreating}
              className="flex flex-col items-start gap-3 rounded-xl border border-border-default bg-surface-card p-6 text-left card-shadow transition-all duration-200 hover:border-accent-amber hover:shadow-md focus:outline-none focus:ring-2 focus:ring-accent-amber disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isCreating ? (
                <Loader2 size={28} className="text-accent-amber animate-spin" />
              ) : (
                <Sparkles size={28} className="text-accent-amber" />
              )}
              <span className="font-bold text-body-md text-text-heading">
                Generate from Scratch
              </span>
              <span className="text-code-sm text-text-caption leading-relaxed">
                Create new ad content from scratch using AI generation tools.
              </span>
            </button>
          </div>

          {/* Back button */}
          <button
            type="button"
            onClick={() => setStep(1)}
            className="inline-flex items-center gap-1.5 text-label-ui text-text-caption hover:text-text-heading transition-colors"
          >
            <ArrowLeft size={14} />
            Back
          </button>
        </div>
      )}
    </div>
  );
}
