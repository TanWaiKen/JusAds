/**
 * PromptTemplateForm — Fill-in-the-blank form for structured prompt templates.
 *
 * Parses prompt content for `{argument name="..." default="..."}` placeholders
 * and renders input fields for each. The user fills in their values and clicks
 * "Generate" to compose the final prompt with their inputs substituted in.
 *
 * Also handles JSON-structured prompts (like `{"subject": "...", "style": "..."}`)
 * by showing one field per key.
 */

import React, { useState, useMemo } from "react";
import { Zap } from "lucide-react";

interface PromptTemplateFormProps {
  /** Raw prompt content (may contain placeholders or JSON structure). */
  content: string;
  /** Title shown above the form. */
  title: string;
  /** Called with the composed prompt when user clicks Generate. */
  onGenerate: (composedPrompt: string) => void;
}

interface TemplateField {
  name: string;
  defaultValue: string;
}

/**
 * Parse `{argument name="..." default="..."}` patterns from a prompt string.
 * Falls back to parsing top-level JSON keys if the content is JSON.
 */
function parseFields(content: string): TemplateField[] {
  const fields: TemplateField[] = [];
  const seen = new Set<string>();

  // Pattern 1: {argument name="fieldName" default="value"}
  const argRegex = /\{argument\s+name="([^"]+)"\s+default="([^"]*)"\}/gi;
  let match;
  while ((match = argRegex.exec(content)) !== null) {
    const name = match[1];
    if (!seen.has(name)) {
      fields.push({ name, defaultValue: match[2] });
      seen.add(name);
    }
  }

  if (fields.length > 0) return fields;

  // Pattern 2: JSON object with string values as editable fields.
  try {
    const parsed = JSON.parse(content);
    if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
      for (const [key, value] of Object.entries(parsed)) {
        if (typeof value === "string" && !seen.has(key)) {
          fields.push({ name: key, defaultValue: value });
          seen.add(key);
        }
      }
    }
  } catch {
    // Not JSON — no fields to extract.
  }

  return fields;
}

/**
 * Compose the final prompt by substituting field values into the template.
 */
function composePrompt(content: string, fields: TemplateField[], values: Record<string, string>): string {
  let result = content;

  // Replace {argument name="..." default="..."} with the user's value.
  for (const field of fields) {
    const regex = new RegExp(
      `\\{argument\\s+name="${field.name}"\\s+default="[^"]*"\\}`,
      "gi"
    );
    result = result.replace(regex, values[field.name] || field.defaultValue);
  }

  // If original was JSON, rebuild it with user values.
  try {
    const parsed = JSON.parse(content);
    if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
      const composed = { ...parsed };
      for (const field of fields) {
        if (field.name in composed) {
          composed[field.name] = values[field.name] || field.defaultValue;
        }
      }
      return JSON.stringify(composed, null, 2);
    }
  } catch {
    // Not JSON — use regex-replaced result.
  }

  return result;
}

export function PromptTemplateForm({
  content,
  title,
  onGenerate,
}: PromptTemplateFormProps): React.ReactElement {
  const fields = useMemo(() => parseFields(content), [content]);
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const f of fields) init[f.name] = f.defaultValue;
    return init;
  });

  if (fields.length === 0) {
    // No parseable fields — just show the raw prompt with a Use button.
    return (
      <div className="flex flex-col gap-2 rounded-lg border bg-card p-3">
        <p className="text-[10px] font-semibold text-foreground">{title}</p>
        <pre className="max-h-24 overflow-y-auto rounded bg-muted/50 p-2 text-[10px] whitespace-pre-wrap font-mono">
          {content.slice(0, 400)}
        </pre>
        <button
          type="button"
          onClick={() => onGenerate(content)}
          className="self-start inline-flex items-center gap-1.5 rounded-md bg-[#171717] px-3 py-1.5 text-[10px] font-bold text-white hover:bg-[#333] transition-colors cursor-pointer"
        >
          <Zap size={10} />
          Use as-is
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-card p-4">
      <p className="text-xs font-bold text-foreground">{title}</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {fields.map((field) => (
          <label key={field.name} className="flex flex-col gap-1">
            <span className="text-[10px] font-semibold text-muted-foreground capitalize">
              {field.name.replace(/_/g, " ")}
            </span>
            <input
              type="text"
              value={values[field.name] || ""}
              onChange={(e) => setValues((prev) => ({ ...prev, [field.name]: e.target.value }))}
              placeholder={field.defaultValue || field.name}
              className="rounded-md border bg-background px-2.5 py-1.5 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary placeholder:text-muted-foreground/60"
            />
          </label>
        ))}
      </div>

      <button
        type="button"
        onClick={() => onGenerate(composePrompt(content, fields, values))}
        className="self-start inline-flex items-center gap-1.5 rounded-md bg-[#171717] px-4 py-2 text-xs font-bold text-white hover:bg-[#333] transition-colors cursor-pointer"
      >
        <Zap size={12} />
        Generate with these settings
      </button>
    </div>
  );
}

export default PromptTemplateForm;
