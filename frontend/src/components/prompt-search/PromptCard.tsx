/**
 * PromptCard — A visual card for a prompt template suggestion.
 *
 * Matches the reference: preview image (from sourceMedia) + structured prompt
 * content + "Try it now" action button + share/bookmark icons.
 */

import React, { useState } from "react";
import { Zap, Share2, Bookmark, ChevronDown, ChevronUp } from "lucide-react";
import type { PromptSuggestion } from "./PromptSearchBox";
import { PromptTemplateForm } from "./PromptTemplateForm";

interface PromptCardProps {
  suggestion: PromptSuggestion;
  onUse: (content: string) => void;
}

function parseSourceMedia(raw: string): string | null {
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.length > 0) return parsed[0];
    if (typeof parsed === "string") return parsed;
  } catch {
    if (raw.startsWith("http")) return raw;
  }
  return null;
}

export function PromptCard({ suggestion, onUse }: PromptCardProps): React.ReactElement {
  const [expanded, setExpanded] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const imageUrl = parseSourceMedia(suggestion.sourceMedia);

  return (
    <div className="prompt-card flex flex-col overflow-hidden rounded-xl border bg-card shadow-sm hover:shadow-md transition-shadow">
      {/* Preview image */}
      {imageUrl && (
        <div className="relative h-40 w-full overflow-hidden bg-muted">
          <img
            src={imageUrl}
            alt={suggestion.title}
            className="h-full w-full object-cover"
            loading="lazy"
          />
          {/* Score badge */}
          <span className="absolute left-2 top-2 rounded bg-yellow-400 px-1.5 py-0.5 text-[10px] font-bold text-black">
            {Math.round(suggestion.score * 100)}% match
          </span>
        </div>
      )}

      {/* Content */}
      <div className="flex flex-col gap-2 p-3">
        {/* Title */}
        <h4 className="text-xs font-bold text-foreground line-clamp-2">
          {suggestion.title}
        </h4>

        {/* Description */}
        {suggestion.description && (
          <p className="text-[10px] text-muted-foreground line-clamp-2">
            {suggestion.description}
          </p>
        )}

        {/* Prompt content (expandable) */}
        {suggestion.content && (
          <div className="mt-1">
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="flex items-center gap-1 text-[10px] font-semibold text-primary hover:underline cursor-pointer"
            >
              {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
              {expanded ? "Hide prompt" : "View full prompt →"}
            </button>
            {expanded && (
              <pre className="mt-1.5 max-h-32 overflow-y-auto rounded bg-[#1a1a1a] p-2.5 text-[10px] text-[#e2e8f0] whitespace-pre-wrap font-mono leading-relaxed">
                {suggestion.content}
              </pre>
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-2 mt-2 pt-2 border-t border-border">
          <button
            type="button"
            onClick={() => {
              // If the prompt has template fields, show the form; otherwise use directly.
              const hasFields = /\{argument\s+name=|^\s*\{[\s\S]*"[^"]+"\s*:/.test(suggestion.content || "");
              if (hasFields) {
                setShowForm(true);
              } else {
                onUse(suggestion.content || suggestion.description);
              }
            }}
            className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-[#171717] px-3 py-2 text-[11px] font-bold text-white hover:bg-[#333] transition-colors cursor-pointer"
          >
            <Zap size={12} />
            Try it now
          </button>
          <button
            type="button"
            onClick={() => navigator.clipboard.writeText(suggestion.content || suggestion.description)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border hover:bg-muted transition-colors cursor-pointer"
            title="Share / Copy link"
          >
            <Share2 size={12} className="text-muted-foreground" />
          </button>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border hover:bg-muted transition-colors cursor-pointer"
            title="Bookmark"
          >
            <Bookmark size={12} className="text-muted-foreground" />
          </button>
        </div>

        {/* Template form (shown when prompt has fillable fields) */}
        {showForm && (
          <div className="mt-2 pt-2 border-t border-border">
            <PromptTemplateForm
              content={suggestion.content}
              title="Customize this prompt"
              onGenerate={(composed) => {
                onUse(composed);
                setShowForm(false);
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default PromptCard;
