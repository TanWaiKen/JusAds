/**
 * GuidedGenerate — Multi-step guided generation page.
 *
 * Step 1: Mode Selector (Guided vs Agentic)
 * Step 2: Design Type Picker (5 design type cards)
 * Step 3: Dynamic Form (fields based on selected design type schema)
 *
 * Route: /dashboard/project/:projectId/guided-generate
 */

import { useRef, useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router";
import { toast } from "sonner";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import {
  ClipboardList,
  MessageSquare,
  Image,
  GalleryHorizontalEnd,
  Video,
  Type,
  AudioLines,
  ArrowLeft,
  Loader2,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { createGenerationTask } from "@/services/taskApi";

gsap.registerPlugin(useGSAP);

// ─── Constants ───────────────────────────────────────────────────────────────

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const PLATFORMS = ["Instagram", "TikTok", "Facebook", "YouTube", "LinkedIn"] as const;

/** Lucide icon map keyed by the backend icon identifier */
const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  image: Image,
  "gallery-horizontal-end": GalleryHorizontalEnd,
  video: Video,
  type: Type,
  "audio-lines": AudioLines,
};

// ─── Types ───────────────────────────────────────────────────────────────────

interface DesignTypeSchema {
  id: string;
  label: string;
  description: string;
  icon: string;
  fields: {
    common: string[];
    specific: string[];
  };
}

interface FormSchemaResponse {
  design_types: DesignTypeSchema[];
}

type FormState = Record<string, string>;

interface FormErrors {
  product_name?: string;
  key_message?: string;
}

// ─── Field metadata for rendering ────────────────────────────────────────────

const FIELD_META: Record<string, { label: string; type: "text" | "textarea" | "select" | "file"; placeholder: string; required?: boolean }> = {
  product_name: { label: "Product Name", type: "text", placeholder: "e.g. Tiger Sugar Boba", required: true },
  target_audience: { label: "Target Audience", type: "text", placeholder: "e.g. Gen Z bubble tea lovers" },
  platform: { label: "Platform", type: "select", placeholder: "Select platform" },
  key_message: { label: "Key Message", type: "textarea", placeholder: "What's the core message of your ad?", required: true },
  brand_tone: { label: "Brand Tone", type: "text", placeholder: "e.g. Playful and trendy" },
  visual_style: { label: "Visual Style", type: "text", placeholder: "e.g. Japanese minimalist" },
  color_palette: { label: "Color Palette", type: "text", placeholder: "e.g. Brown, gold, white" },
  reference_images: { label: "Reference Images", type: "file", placeholder: "Upload reference images" },
  video_duration: { label: "Video Duration", type: "text", placeholder: "e.g. 15s, 30s, 60s" },
  slide_count: { label: "Number of Slides", type: "text", placeholder: "e.g. 3-5" },
  copy_length: { label: "Copy Length", type: "text", placeholder: "e.g. Short (1-2 lines), Medium, Long" },
  call_to_action: { label: "Call to Action", type: "text", placeholder: "e.g. Shop Now, Learn More" },
  language: { label: "Language", type: "text", placeholder: "e.g. English, Malay, auto" },
  audio_duration: { label: "Audio Duration", type: "text", placeholder: "e.g. 15s, 30s, 60s" },
  voice_tone: { label: "Voice Tone", type: "text", placeholder: "e.g. Warm and conversational" },
  background_music_style: { label: "Background Music Style", type: "text", placeholder: "e.g. Lo-fi chill, Upbeat pop" },
};

// ─── Component ───────────────────────────────────────────────────────────────

export function GuidedGenerate() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);

  // Step management: 1 = mode selector, 2 = design type picker, 3 = form
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [selectedType, setSelectedType] = useState<DesignTypeSchema | null>(null);
  const [schema, setSchema] = useState<DesignTypeSchema[]>([]);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [formState, setFormState] = useState<FormState>({});
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);

  // GSAP entrance animation for each step
  useGSAP(() => {
    gsap.from(".step-content", {
      y: 20,
      autoAlpha: 0,
      duration: 0.5,
      ease: "power2.out",
    });
  }, { scope: containerRef, dependencies: [step] });

  // Fetch schema when moving to step 2
  useEffect(() => {
    if (step === 2 && schema.length === 0) {
      setSchemaLoading(true);
      fetch(`${API_BASE}/api/guided-form-schema`)
        .then((res) => {
          if (!res.ok) throw new Error("Failed to fetch form schema");
          return res.json() as Promise<FormSchemaResponse>;
        })
        .then((data) => {
          setSchema(data.design_types);
        })
        .catch(() => {
          // Fallback hardcoded schema
          setSchema(FALLBACK_SCHEMA);
          toast.error("Could not load form schema — using defaults");
        })
        .finally(() => setSchemaLoading(false));
    }
  }, [step, schema.length]);

  // ─── Handlers ────────────────────────────────────────────────────────────

  function handleAgenticMode() {
    navigate(`/dashboard/project/${projectId}/generate`);
  }

  function handleGuidedMode() {
    setStep(2);
  }

  function handleDesignTypeSelect(designType: DesignTypeSchema) {
    setSelectedType(designType);
    setFormState({});
    setFormErrors({});
    setTouched({});
    setStep(3);
  }

  function handleBackToDesignType() {
    setStep(2);
  }

  function handleFieldChange(fieldName: string, value: string) {
    setFormState((prev) => ({ ...prev, [fieldName]: value }));
    // Clear error on change if field becomes valid
    if (fieldName === "product_name" || fieldName === "key_message") {
      if (value.trim()) {
        setFormErrors((prev) => {
          const next = { ...prev };
          delete next[fieldName as keyof FormErrors];
          return next;
        });
      }
    }
  }

  function handleFieldBlur(fieldName: string) {
    setTouched((prev) => ({ ...prev, [fieldName]: true }));
    // Validate required fields on blur
    if (fieldName === "product_name" && !formState.product_name?.trim()) {
      setFormErrors((prev) => ({ ...prev, product_name: "Product name is required" }));
    }
    if (fieldName === "key_message" && !formState.key_message?.trim()) {
      setFormErrors((prev) => ({ ...prev, key_message: "Key message is required" }));
    }
  }

  function isFormValid(): boolean {
    return !!(formState.product_name?.trim() && formState.key_message?.trim());
  }

  async function handleSubmit() {
    if (!isFormValid() || !projectId || !selectedType) return;

    setSubmitting(true);
    try {
      const task = await createGenerationTask(projectId);
      navigate(`/dashboard/project/${projectId}/${task.id}`, {
        state: {
          guidedMode: true,
          designType: selectedType.id,
          guidedInputs: formState,
        },
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create generation task";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  // ─── Render ──────────────────────────────────────────────────────────────

  return (
    <div ref={containerRef} className="flex h-full flex-col overflow-y-auto p-6">
      {/* Step 1: Mode Selector */}
      {step === 1 && (
        <div className="step-content mx-auto flex w-full max-w-3xl flex-col items-center gap-8 pt-12">
          <div className="text-center">
            <h1 className="text-2xl font-semibold tracking-tight">Create an Ad</h1>
            <p className="mt-2 text-muted-foreground">
              Choose how you'd like to create your advertisement
            </p>
          </div>

          <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2">
            {/* Guided Mode Card */}
            <Card
              className="cursor-pointer transition-all hover:ring-2 hover:ring-primary/50"
              onClick={handleGuidedMode}
            >
              <CardHeader>
                <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <ClipboardList className="h-5 w-5 text-primary" />
                </div>
                <CardTitle>Guided Mode</CardTitle>
                <CardDescription>
                  Step-by-step form for creating professional ads — no prompting skills needed
                </CardDescription>
              </CardHeader>
            </Card>

            {/* Agentic Mode Card */}
            <Card
              className="cursor-pointer transition-all hover:ring-2 hover:ring-primary/50"
              onClick={handleAgenticMode}
            >
              <CardHeader>
                <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <MessageSquare className="h-5 w-5 text-primary" />
                </div>
                <CardTitle>Agentic Mode</CardTitle>
                <CardDescription>
                  Chat with AI directly — for users who know how to prompt
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      )}

      {/* Step 2: Design Type Picker */}
      {step === 2 && (
        <div className="step-content mx-auto flex w-full max-w-4xl flex-col gap-6 pt-8">
          <div className="text-center">
            <h1 className="text-2xl font-semibold tracking-tight">What would you like to create?</h1>
            <p className="mt-2 text-muted-foreground">
              Select the type of ad you want to generate
            </p>
          </div>

          {schemaLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {schema.map((designType) => {
                const IconComponent = ICON_MAP[designType.icon] || Image;
                return (
                  <Card
                    key={designType.id}
                    className="cursor-pointer transition-all hover:ring-2 hover:ring-primary/50"
                    onClick={() => handleDesignTypeSelect(designType)}
                  >
                    <CardHeader>
                      <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                        <IconComponent className="h-5 w-5 text-primary" />
                      </div>
                      <CardTitle>{designType.label}</CardTitle>
                      <CardDescription>{designType.description}</CardDescription>
                    </CardHeader>
                  </Card>
                );
              })}
            </div>
          )}

          <Button
            variant="ghost"
            className="self-start"
            onClick={() => setStep(1)}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to mode selection
          </Button>
        </div>
      )}

      {/* Step 3: Dynamic Form */}
      {step === 3 && selectedType && (
        <div className="step-content mx-auto flex w-full max-w-2xl flex-col gap-6 pt-8">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {selectedType.label}
            </h1>
            <p className="mt-1 text-muted-foreground">
              {selectedType.description}
            </p>
          </div>

          <div className="flex flex-col gap-4">
            {/* Common fields */}
            {selectedType.fields.common.map((fieldName) =>
              renderField(fieldName)
            )}

            {/* Specific fields */}
            {selectedType.fields.specific.map((fieldName) =>
              renderField(fieldName)
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between border-t pt-4">
            <Button variant="ghost" onClick={handleBackToDesignType}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>

            <Button
              onClick={handleSubmit}
              disabled={!isFormValid() || submitting}
            >
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Generate Ad
            </Button>
          </div>
        </div>
      )}
    </div>
  );

  // ─── Field renderer ──────────────────────────────────────────────────────

  function renderField(fieldName: string) {
    const meta = FIELD_META[fieldName];
    if (!meta) return null;

    const value = formState[fieldName] || "";
    const error = (formErrors as Record<string, string | undefined>)[fieldName];
    const isTouched = touched[fieldName];

    // Skip reference_images for text_copy and audio_ad
    if (fieldName === "reference_images") {
      if (selectedType && ["text_copy", "audio_ad"].includes(selectedType.id)) {
        return null;
      }
      return (
        <div key={fieldName} className="flex flex-col gap-1.5">
          <label className="text-sm font-medium">{meta.label}</label>
          <Input
            type="file"
            accept="image/*"
            multiple
            className="cursor-pointer"
          />
          <p className="text-xs text-muted-foreground">Optional — upload reference images for style guidance</p>
        </div>
      );
    }

    if (meta.type === "select" && fieldName === "platform") {
      return (
        <div key={fieldName} className="flex flex-col gap-1.5">
          <label className="text-sm font-medium">{meta.label}</label>
          <Select
            value={value || undefined}
            onValueChange={(val) => handleFieldChange(fieldName, val || "")}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder={meta.placeholder} />
            </SelectTrigger>
            <SelectContent>
              {PLATFORMS.map((platform) => (
                <SelectItem key={platform} value={platform.toLowerCase()}>
                  {platform}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      );
    }

    if (meta.type === "textarea") {
      return (
        <div key={fieldName} className="flex flex-col gap-1.5">
          <label className="text-sm font-medium">
            {meta.label}
            {meta.required && <span className="text-destructive"> *</span>}
          </label>
          <Textarea
            placeholder={meta.placeholder}
            value={value}
            onChange={(e) => handleFieldChange(fieldName, e.target.value)}
            onBlur={() => handleFieldBlur(fieldName)}
            maxLength={500}
          />
          {isTouched && error && (
            <p className="text-xs text-destructive">{error}</p>
          )}
        </div>
      );
    }

    // Default: text input
    return (
      <div key={fieldName} className="flex flex-col gap-1.5">
        <label className="text-sm font-medium">
          {meta.label}
          {meta.required && <span className="text-destructive"> *</span>}
        </label>
        <Input
          placeholder={meta.placeholder}
          value={value}
          onChange={(e) => handleFieldChange(fieldName, e.target.value)}
          onBlur={() => handleFieldBlur(fieldName)}
          maxLength={500}
        />
        {isTouched && error && (
          <p className="text-xs text-destructive">{error}</p>
        )}
      </div>
    );
  }
}

// ─── Fallback schema (used when API is unreachable) ──────────────────────────

const FALLBACK_SCHEMA: DesignTypeSchema[] = [
  {
    id: "image_poster",
    label: "Image Poster",
    description: "Single high-impact visual poster optimized for social feeds and display ads",
    icon: "image",
    fields: {
      common: ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
      specific: ["visual_style", "color_palette", "reference_images"],
    },
  },
  {
    id: "carousel",
    label: "Carousel Ad",
    description: "Multi-slide swipeable narrative with consistent visual style across slides",
    icon: "gallery-horizontal-end",
    fields: {
      common: ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
      specific: ["visual_style", "color_palette", "slide_count", "reference_images"],
    },
  },
  {
    id: "video_ad",
    label: "Video Ad",
    description: "Short-form video ad with hook, pacing, and call-to-action scripting",
    icon: "video",
    fields: {
      common: ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
      specific: ["video_duration", "visual_style", "reference_images"],
    },
  },
  {
    id: "text_copy",
    label: "Text Copy",
    description: "Platform-optimized advertising copy using proven copywriting frameworks",
    icon: "type",
    fields: {
      common: ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
      specific: ["copy_length", "call_to_action", "language"],
    },
  },
  {
    id: "audio_ad",
    label: "Audio Ad",
    description: "Scripted audio spot with voice direction, pacing, and sonic branding",
    icon: "audio-lines",
    fields: {
      common: ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
      specific: ["audio_duration", "voice_tone", "background_music_style"],
    },
  },
];

export default GuidedGenerate;
