/**
 * EasyGenerationPage — Step-by-step easy generation page.
 *
 * Step 2: Design Type Picker (5 design type cards with preview images & presets)
 *   - Clicking a card opens a Guide & Preset Preview Modal showing the design guide markdown content.
 * Step 3: Dynamic Form (fields based on selected design type schema, with prefilled defaults)
 *   - Reference image slot guides (Product, Logo, Vibe) with guide preview buttons & modals.
 *
 * Route: /dashboard/project/:projectId/easy
 */

import { useRef, useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router";
import { toast } from "sonner";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import {
  Image,
  GalleryHorizontalEnd,
  Video,
  Type,
  AudioLines,
  ArrowLeft,
  Loader2,
  X,
  Camera,
  Eye,
  Info,
  CheckCircle2,
  Sparkles,
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

// ─── Design Presets — default field values & preview images per design type ──

interface DesignPreset {
  previewImage: string;
  defaults: Record<string, string>;
  markdownGuide: string;
}

const DESIGN_PRESETS: Record<string, DesignPreset> = {
  image_poster: {
    previewImage: "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=400&h=260&fit=crop&q=80",
    defaults: {
      platform: "instagram",
      brand_tone: "Bold and eye-catching",
      visual_style: "Modern minimalist flat design",
      color_palette: "Vibrant gradient tones",
    },
    markdownGuide: `### 🖼️ Poster Ad Design Guide

#### 1. Introduction
The Poster Ad tool is designed for static posters, banners, and single-frame visual creatives. It converts your brand message into a single visual composition with strong, focused copywriting.

#### 2. Structured Copywriting Framework
* **Attention**: A catchy hook or bold headline centered at the top.
* **Interest**: Address a relatable pain point or opportunity.
* **Desire**: Highlight your product's key advantages and features.
* **Action**: Direct CTA ("Shop Now", "Learn More").

#### 3. Visual Layout Guidelines
* Keep a high contrast between text and background.
* Leave sufficient negative space around the product.
* Display the product prominently in the center or lower third.`,
  },
  carousel: {
    previewImage: "https://images.unsplash.com/photo-1563986768609-322da13575f2?w=400&h=260&fit=crop&q=80",
    defaults: {
      platform: "instagram",
      brand_tone: "Informative, educational and engaging",
      visual_style: "Clean modern editorial layout",
      color_palette: "Beige, charcoal, soft terracotta",
      slide_count: "4",
    },
    markdownGuide: `### 📑 Carousel Ad Design Guide

#### 1. Introduction
The Carousel Ad tool creates a sequence of related visual panels (typically 3 to 5 images) that a user swipes through. This format is ideal for storytelling, product features, or step-by-step guides.

#### 2. Panel Sequence Structure
* **Panel 1 (The Hook)**: Arresting image + bold question or statement.
* **Panel 2 (The Detail/Value)**: Showcases a primary feature or benefit.
* **Panel 3 (The Proof/Demo)**: Demonstration or comparative highlight.
* **Panel 4 (The Secondary Benefit)**: Additional value proposition or testimonial.
* **Panel 5 (The Action)**: Clear conversion panel with promotional pricing and a CTA button.

#### 3. Visual Continuity
* Use consistent font sizes, backgrounds, and borders across all slides.
* Maintain a cohesive color palette so the swipe flow feels connected.`,
  },
  video_ad: {
    previewImage: "https://images.unsplash.com/photo-1574717024653-61fd2cf4d44d?w=400&h=260&fit=crop&q=80",
    defaults: {
      platform: "tiktok",
      brand_tone: "Energetic, authentic and trendy",
      visual_style: "Dynamic cuts and quick text overlays",
      video_duration: "15s",
    },
    markdownGuide: `### 🎬 Video Ad Design Guide

#### 1. Introduction
The Video Ad tool stitches visual elements with auditory elements (voiceover, sound effects, or background music) to compile a high-impact short-form video advertisement.

#### 2. Storytelling Pacing & Scripting
* **0 - 3s (The Hook)**: Fast visual change, trending question, or immediate product demo.
* **3 - 7s (The Core Value)**: Address the pain point and present the solution.
* **7 - 15s (CTA & Logo)**: Clear closing with brand logo and action details.

#### 3. Production Best Practices
* Optimize for vertical viewing (9:16) on TikTok/Reels.
* Add dynamic text captions for users browsing with sound off.`,
  },
  text_copy: {
    previewImage: "https://images.unsplash.com/photo-1455390582262-044cdead277a?w=400&h=260&fit=crop&q=80",
    defaults: {
      platform: "facebook",
      brand_tone: "Conversational, friendly and persuasive",
      copy_length: "Medium (3-5 sentences)",
      call_to_action: "Shop Now",
      language: "English",
    },
    markdownGuide: `### ✍️ Text Copy Writing Guide

#### 1. Introduction
The Text Copy tool generates platform-optimized ad copy using proven advertising frameworks.

#### 2. Frameworks Used
* **PAS (Problem, Agitate, Solution)**: Identify problem, elaborate on the frustration, and resolve it with your product.
* **AIDA (Attention, Interest, Desire, Action)**: Grab attention, build interest, evoke desire, call to action.

#### 3. Best Practices
* Use 2-3 contextual emojis to break up text visually.
* Keep sentences punchy and short.
* Direct the reader to a single, clear link or button.`,
  },
  audio_ad: {
    previewImage: "https://images.unsplash.com/photo-1478737270239-2f02b77fc618?w=400&h=260&fit=crop&q=80",
    defaults: {
      platform: "youtube",
      brand_tone: "Warm, professional and trust-building",
      voice_tone: "Conversational and friendly",
      audio_duration: "30s",
      background_music_style: "Lo-fi chill beats",
    },
    markdownGuide: `### 🎙️ Audio Ad Production Guide

#### 1. Introduction
The Audio Ad tool creates script copy and voiceover direction for short-form audio spots (e.g. Spotify, YouTube Ads).

#### 2. Voice & Tone
* Maintain a steady, warm pace (around 130-150 words per minute).
* Choose a background music style that matches the product category.

#### 3. Script Flow
* **0 - 5s**: Instant brand callout and hook.
* **5 - 25s**: Narrative story or quick features highlight.
* **25 - 30s**: Clear sonic call-to-action (e.g. "Search Tiger Sugar on your app").`,
  },
};

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

// ─── Reference Image slot definitions ────────────────────────────────────────

interface RefImageSlot {
  id: string;
  label: string;
  exampleImage: string;
  description: string;
  guideText: string;
}

const REF_IMAGE_SLOTS: RefImageSlot[] = [
  {
    id: "product_photo",
    label: "Product Photo",
    exampleImage: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&h=400&fit=crop&q=80",
    description: "Photograph your product clearly on a solid background.",
    guideText: "💡 How to shoot:\n1. Place your product under bright, natural light.\n2. Use a clean, uncluttered background (white wall, desk, or solid sheet).\n3. Keep the entire product in the frame at eye-level.\n4. Avoid strong shadows or reflections.",
  },
  {
    id: "brand_logo",
    label: "Brand Logo",
    exampleImage: "https://images.unsplash.com/photo-1626785774573-4b799315345d?w=600&h=400&fit=crop&q=80",
    description: "High-resolution transparent logo or packaging asset.",
    guideText: "💡 Best logo practices:\n1. Use a transparent background (PNG format).\n2. Ensure high contrast against light or dark backgrounds.\n3. Make sure borders are clean, high-resolution, and not pixelated.",
  },
  {
    id: "style_ref",
    label: "Style Reference",
    exampleImage: "https://images.unsplash.com/photo-1513542789411-b6a5d4f31634?w=600&h=400&fit=crop&q=80",
    description: "An ad layout, color palette, or vibe you want to copy.",
    guideText: "💡 How to choose style references:\n1. Find an ad or graphic you really like on social media.\n2. Choose one that shares your target color palette.\n3. Antigravity AI will mimic its lighting, color grading, and composition style.",
  },
];

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

// ─── Component ───────────────────────────────────────────────────────────────

export default function EasyGenerationPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);

  // Step management: 2 = design type picker, 3 = form
  const [step, setStep] = useState<2 | 3>(2);
  const [selectedType, setSelectedType] = useState<DesignTypeSchema | null>(null);
  const [schema, setSchema] = useState<DesignTypeSchema[]>([]);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [formState, setFormState] = useState<FormState>({});
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);

  // Preview & Guide Modal state for selected Design Type
  const [guideModalOpen, setGuideModalOpen] = useState(false);
  const [previewingType, setPreviewingType] = useState<DesignTypeSchema | null>(null);

  // Reference Image Slot Files & Previews
  const [slotFiles, setSlotFiles] = useState<Record<string, { file: File; preview: string }>>({});
  const fileInputRefs = {
    product_photo: useRef<HTMLInputElement>(null),
    brand_logo: useRef<HTMLInputElement>(null),
    style_ref: useRef<HTMLInputElement>(null),
  };

  // Modal state for Slot guidance
  const [activeSlotGuidance, setActiveSlotGuidance] = useState<RefImageSlot | null>(null);

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
          setSchema(FALLBACK_SCHEMA);
          toast.error("Could not load form schema — using defaults");
        })
        .finally(() => setSchemaLoading(false));
    }
  }, [step, schema.length]);

  // Cleanup reference image previews on unmount
  useEffect(() => {
    return () => {
      Object.values(slotFiles).forEach((slot) => {
        URL.revokeObjectURL(slot.preview);
      });
    };
  }, [slotFiles]);

  // ─── Handlers ────────────────────────────────────────────────────────────

  async function handleToggleToAdvanced() {
    if (!projectId) return;
    const loadingToast = toast.loading("Loading Advanced Mode...");
    try {
      const res = await fetch(`${API_BASE}/api/projects/${projectId}/tasks`);
      if (res.ok) {
        const tasks = await res.json();
        const genTask = tasks.find((t: any) => t.type === "generation");
        if (genTask) {
          toast.dismiss(loadingToast);
          navigate(`/dashboard/project/${projectId}/${genTask.id}`);
          return;
        }
      }
      // If no task exists, create a new one
      const newTask = await createGenerationTask(projectId);
      toast.dismiss(loadingToast);
      navigate(`/dashboard/project/${projectId}/${newTask.id}`);
    } catch (err) {
      toast.dismiss(loadingToast);
      toast.error("Failed to load Advanced Mode");
    }
  }

  // User clicks a card in Step 2 -> Open Guide Modal
  function handleCardClick(designType: DesignTypeSchema) {
    setPreviewingType(designType);
    setGuideModalOpen(true);
  }

  // User accepts template in Guide Modal -> Pre-fill defaults & go to step 3
  function handleApplyTemplate() {
    if (!previewingType) return;
    setSelectedType(previewingType);
    
    // Apply preset defaults
    const preset = DESIGN_PRESETS[previewingType.id];
    setFormState(preset ? { ...preset.defaults } : {});
    setFormErrors({});
    setTouched({});
    setSlotFiles({});
    setStep(3);
    setGuideModalOpen(false);
    setPreviewingType(null);
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

  // Handle file addition for a specific slot
  function handleSlotFileChange(slotId: string, files: FileList | null) {
    if (!files || files.length === 0) return;
    const file = files[0];
    
    // Revoke old object URL if exists
    if (slotFiles[slotId]) {
      URL.revokeObjectURL(slotFiles[slotId].preview);
    }

    setSlotFiles((prev) => ({
      ...prev,
      [slotId]: {
        file,
        preview: URL.createObjectURL(file),
      },
    }));
  }

  // Remove file from slot
  function handleRemoveSlotFile(slotId: string) {
    setSlotFiles((prev) => {
      const copy = { ...prev };
      if (copy[slotId]) {
        URL.revokeObjectURL(copy[slotId].preview);
        delete copy[slotId];
      }
      return copy;
    });
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
          // Extract file names / URLs if backend supports receiving references
          guidedReferences: Object.entries(slotFiles).map(([slotId, info]) => ({
            slot: slotId,
            name: info.file.name,
          })),
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
    <div ref={containerRef} className="flex h-full flex-col overflow-y-auto p-6 bg-surface-inset/10">
      
      {/* Mode Toggle Tabs */}
      <div className="mx-auto w-full max-w-4xl mb-6">
        <div className="flex rounded-lg bg-surface-card p-1 border border-border-default max-w-xs mx-auto shadow-sm">
          <span className="flex-1 text-center py-1.5 text-xs font-semibold rounded-md bg-primary text-primary-foreground shadow-sm">
            Easy Mode
          </span>
          <button
            onClick={handleToggleToAdvanced}
            className="flex-1 text-center py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer text-muted-foreground hover:text-foreground hover:bg-muted/50"
          >
            Advanced Mode
          </button>
        </div>
      </div>

      {/* Step 2: Design Type Picker */}
      {step === 2 && (
        <div className="step-content mx-auto flex w-full max-w-4xl flex-col gap-6 pt-6">
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-bold tracking-tight text-text-heading">What would you like to create?</h1>
            <p className="text-text-muted text-sm max-w-lg mx-auto">
              Select a design template below. You'll view its official guide and smart default fields before customizing.
            </p>
          </div>

          {schemaLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {schema.map((designType) => {
                const IconComponent = ICON_MAP[designType.icon] || Image;
                const preset = DESIGN_PRESETS[designType.id];
                return (
                  <Card
                    key={designType.id}
                    className="cursor-pointer transition-all duration-300 hover:-translate-y-1 hover:shadow-lg border-border-default bg-surface-card group overflow-hidden flex flex-col"
                    onClick={() => handleCardClick(designType)}
                  >
                    {preset?.previewImage && (
                      <div className="relative h-40 w-full overflow-hidden bg-muted">
                        <img
                          src={preset.previewImage}
                          alt={designType.label}
                          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                          loading="lazy"
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-transparent" />
                        <div className="absolute bottom-3 left-3 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-0.5 text-[10px] font-semibold text-white backdrop-blur-sm border border-white/15">
                          <IconComponent className="h-3 w-3" />
                          {designType.label}
                        </div>
                      </div>
                    )}
                    <CardHeader className="p-4 flex-1 flex flex-col justify-between">
                      <div className="space-y-1.5">
                        <CardTitle className="text-base font-semibold group-hover:text-primary transition-colors">
                          {designType.label}
                        </CardTitle>
                        <CardDescription className="text-xs text-text-muted leading-relaxed">
                          {designType.description}
                        </CardDescription>
                      </div>
                      
                      {preset && (
                        <div className="mt-4 pt-3 border-t border-border-default/60 flex flex-wrap gap-1">
                          {Object.entries(preset.defaults).slice(0, 3).map(([key, val]) => (
                            <span key={key} className="inline-flex rounded-full bg-primary/8 px-2 py-0.5 text-[10px] font-semibold text-primary">
                              {val}
                            </span>
                          ))}
                        </div>
                      )}
                    </CardHeader>
                  </Card>
                );
              })}
            </div>
          )}

          <Button
            variant="ghost"
            className="self-start text-xs text-text-muted hover:text-text-heading"
            onClick={() => navigate(`/dashboard/project/${projectId}`)}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Project
          </Button>
        </div>
      )}

      {/* Guide & Preset Preview Modal (Step 2.5) */}
      {guideModalOpen && previewingType && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-surface-card border border-border-default w-full max-w-3xl rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-border-default flex items-center justify-between bg-muted/30">
              <div className="flex items-center gap-2">
                <Info className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-bold text-text-heading">
                  Template Guide: {previewingType.label}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => {
                  setGuideModalOpen(false);
                  setPreviewingType(null);
                }}
                className="text-text-muted hover:text-text-heading rounded p-1 hover:bg-muted/80 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto flex flex-col md:flex-row gap-6">
              {/* Left Column: Markdown Guide */}
              <div className="flex-1 space-y-4 pr-0 md:pr-4 md:border-r border-border-default/60">
                <div className="prose prose-sm dark:prose-invert max-w-none text-xs text-text-muted leading-relaxed space-y-3">
                  {/* Clean custom styling for embedded markdown */}
                  {DESIGN_PRESETS[previewingType.id]?.markdownGuide.split("\n\n").map((para, i) => {
                    if (para.startsWith("###")) {
                      return <h3 key={i} className="text-sm font-bold text-text-heading pt-2 border-b border-border-default pb-1">{para.replace("### ", "")}</h3>;
                    }
                    if (para.startsWith("####")) {
                      return <h4 key={i} className="text-xs font-semibold text-text-heading pt-1">{para.replace("#### ", "")}</h4>;
                    }
                    if (para.startsWith("*")) {
                      return (
                        <ul key={i} className="list-disc pl-4 space-y-1">
                          {para.split("\n").map((li, j) => (
                            <li key={j}>{li.replace("* ", "")}</li>
                          ))}
                        </ul>
                      );
                    }
                    return <p key={i}>{para}</p>;
                  })}
                </div>
              </div>

              {/* Right Column: Defaults & Preview Image */}
              <div className="w-full md:w-72 shrink-0 space-y-4">
                <div className="rounded-lg overflow-hidden border border-border-default bg-muted/20">
                  <img
                    src={DESIGN_PRESETS[previewingType.id]?.previewImage}
                    alt={previewingType.label}
                    className="w-full h-36 object-cover"
                  />
                </div>

                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-text-heading uppercase tracking-wider">
                    Smart Preset Values
                  </h4>
                  <div className="space-y-2">
                    {Object.entries(DESIGN_PRESETS[previewingType.id]?.defaults || {}).map(([key, val]) => (
                      <div key={key} className="flex justify-between items-center rounded-md bg-surface-inset px-3 py-2 text-xs">
                        <span className="text-text-muted capitalize">
                          {key.replace("_", " ")}
                        </span>
                        <span className="font-semibold text-primary truncate max-w-[150px]">
                          {val}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-border-default flex justify-end gap-3 bg-muted/30">
              <Button
                variant="ghost"
                onClick={() => {
                  setGuideModalOpen(false);
                  setPreviewingType(null);
                }}
              >
                Cancel
              </Button>
              <Button
                onClick={handleApplyTemplate}
                className="bg-primary hover:bg-primary/95 text-white"
              >
                Apply &amp; Continue
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Dynamic Form */}
      {step === 3 && selectedType && (
        <div className="step-content mx-auto flex w-full max-w-2xl flex-col gap-6 pt-6 bg-surface-card border border-border-default rounded-xl p-8 shadow-sm">
          <div>
            <div className="flex items-center justify-between">
              <h1 className="text-2xl font-bold tracking-tight text-text-heading">
                Configure {selectedType.label}
              </h1>
              <span className="text-xs text-text-muted bg-primary/5 border border-primary/20 rounded-full px-3 py-1 font-medium flex items-center gap-1">
                <Sparkles size={12} className="text-primary" />
                Easy Mode Form
              </span>
            </div>
            <p className="mt-2 text-text-muted text-xs">
              {selectedType.description}
            </p>
          </div>

          <div className="flex flex-col gap-5">
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
          <div className="flex items-center justify-between border-t border-border-default pt-6 mt-4">
            <Button variant="ghost" onClick={handleBackToDesignType} className="text-xs">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Change Template
            </Button>

            <Button
              onClick={handleSubmit}
              disabled={!isFormValid() || submitting}
              className="bg-primary hover:bg-primary/95 text-white font-semibold"
            >
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Generate Ad
            </Button>
          </div>
        </div>
      )}

      {/* Reference Image Guidance Modal */}
      {activeSlotGuidance && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-surface-card border border-border-default w-full max-w-md rounded-xl shadow-2xl overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-200">
            <div className="px-5 py-4 border-b border-border-default flex items-center justify-between bg-muted/30">
              <h3 className="font-bold text-text-heading text-sm">
                How to shoot/select: {activeSlotGuidance.label}
              </h3>
              <button
                type="button"
                onClick={() => setActiveSlotGuidance(null)}
                className="text-text-muted hover:text-text-heading rounded p-1 cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div className="rounded-lg overflow-hidden border border-border-default">
                <img
                  src={activeSlotGuidance.exampleImage}
                  alt={activeSlotGuidance.label}
                  className="w-full h-48 object-cover"
                />
              </div>
              <div className="space-y-2">
                <p className="text-xs text-text-heading font-semibold">Example &amp; Shooting Guidelines</p>
                <p className="text-xs text-text-muted leading-relaxed whitespace-pre-line">
                  {activeSlotGuidance.guideText}
                </p>
              </div>
            </div>
            <div className="px-5 py-3 border-t border-border-default bg-muted/30 flex justify-end">
              <Button onClick={() => setActiveSlotGuidance(null)} size="sm">
                Got it
              </Button>
            </div>
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

    // ── Reference Images — guided slots ──────────────────────────────────
    if (fieldName === "reference_images") {
      if (selectedType && ["text_copy", "audio_ad"].includes(selectedType.id)) {
        return null;
      }
      return (
        <div key={fieldName} className="flex flex-col gap-3 pt-2">
          <div>
            <label className="text-xs font-semibold text-text-heading uppercase tracking-wider">
              {meta.label}
            </label>
            <p className="text-[11px] text-text-muted mt-0.5">
              Upload visuals below. Click the guidance button to see shooting examples.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {REF_IMAGE_SLOTS.map((slot) => {
              const fileInfo = slotFiles[slot.id];
              return (
                <div key={slot.id} className="rounded-xl border border-border-default bg-surface-card p-4 flex flex-col justify-between gap-3 relative shadow-xs">
                  
                  {/* Slot Title + Info Icon */}
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-text-heading">{slot.label}</span>
                    <button
                      type="button"
                      onClick={() => setActiveSlotGuidance(slot)}
                      className="text-primary hover:text-primary/80 hover:bg-primary/5 rounded p-1 transition-colors flex items-center gap-1 text-[10px] font-medium cursor-pointer"
                      title="View Photo Guidelines"
                    >
                      <Eye size={12} />
                      Guide
                    </button>
                  </div>

                  {/* Thumbnail / Upload target area */}
                  <div className="flex-1 min-h-[90px] flex items-center justify-center border border-dashed border-border-default/80 rounded-lg bg-surface-inset relative overflow-hidden group">
                    {fileInfo ? (
                      <div className="absolute inset-0 w-full h-full">
                        <img
                          src={fileInfo.preview}
                          alt={slot.label}
                          className="w-full h-full object-cover"
                        />
                        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                          <button
                            type="button"
                            onClick={() => handleRemoveSlotFile(slot.id)}
                            className="bg-destructive hover:bg-destructive/90 text-white rounded-full p-1.5 shadow-md cursor-pointer"
                            title="Remove Photo"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => fileInputRefs[slot.id as keyof typeof fileInputRefs].current?.click()}
                        className="flex flex-col items-center justify-center p-3 text-center gap-1.5 w-full h-full text-text-muted hover:text-primary transition-colors cursor-pointer"
                      >
                        <Camera size={18} className="text-text-muted/60" />
                        <span className="text-[10px] font-semibold">Upload Photo</span>
                      </button>
                    )}

                    <input
                      ref={fileInputRefs[slot.id as keyof typeof fileInputRefs]}
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => handleSlotFileChange(slot.id, e.target.files)}
                    />
                  </div>

                  <p className="text-[10px] text-text-muted leading-relaxed">
                    {slot.description}
                  </p>

                  {/* Upload Completed indicator */}
                  {fileInfo && (
                    <div className="absolute -top-1.5 -right-1.5 bg-emerald-500 text-white rounded-full p-0.5 shadow-sm">
                      <CheckCircle2 size={12} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      );
    }

    // ── Platform select with aspect ratio hints ─────────────────────────
    if (meta.type === "select" && fieldName === "platform") {
      return (
        <div key={fieldName} className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-text-heading uppercase tracking-wider">{meta.label}</label>
          <Select
            value={value || undefined}
            onValueChange={(val) => handleFieldChange(fieldName, val || "")}
          >
            <SelectTrigger className="w-full bg-surface-card border-border-default">
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
          {value && (
            <p className="text-[11px] text-accent-blue font-medium mt-1 pl-1">
              Aspect ratios: {
                value === "instagram" ? "1:1 (Square) or 4:5 (Vertical) or 9:16 (Reels)" :
                value === "tiktok" ? "9:16 (Vertical)" :
                value === "youtube" ? "16:9 (Landscape) or 9:16 (Shorts)" :
                value === "facebook" ? "1:1 (Square) or 4:5 (Vertical)" :
                value === "linkedin" ? "1:1 (Square) or 16:9 (Landscape)" : ""
              }
            </p>
          )}
        </div>
      );
    }

    // ── Textarea ────────────────────────────────────────────────────────
    if (meta.type === "textarea") {
      return (
        <div key={fieldName} className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-text-heading uppercase tracking-wider">
            {meta.label}
            {meta.required && <span className="text-destructive"> *</span>}
          </label>
          <Textarea
            placeholder={meta.placeholder}
            value={value}
            onChange={(e) => handleFieldChange(fieldName, e.target.value)}
            onBlur={() => handleFieldBlur(fieldName)}
            maxLength={500}
            className="bg-surface-card border-border-default min-h-[100px]"
          />
          {isTouched && error && (
            <p className="text-xs text-destructive">{error}</p>
          )}
        </div>
      );
    }

    // ── Default: text input ─────────────────────────────────────────────
    return (
      <div key={fieldName} className="flex flex-col gap-1.5">
        <label className="text-xs font-semibold text-text-heading uppercase tracking-wider">
          {meta.label}
          {meta.required && <span className="text-destructive"> *</span>}
        </label>
        <Input
          placeholder={meta.placeholder}
          value={value}
          onChange={(e) => handleFieldChange(fieldName, e.target.value)}
          onBlur={() => handleFieldBlur(fieldName)}
          maxLength={500}
          className="bg-surface-card border-border-default"
        />
        {isTouched && error && (
          <p className="text-xs text-destructive">{error}</p>
        )}
      </div>
    );
  }
}
