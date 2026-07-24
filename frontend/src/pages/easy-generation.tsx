/**
 * EasyGenerationPage — Step-by-step easy generation page.
 *
 * Step 2: Design Type Picker (5 design type cards with preview images & presets)
 *   - Clicking a card opens a Guide & Preset Preview Modal showing the design guide markdown content.
 * Step 3: Dynamic Form (fields based on selected design type schema, with prefilled defaults)
 *   - Reference image slot guides (Product, Logo, Vibe) with guide preview buttons & modals.
 *
 * Route: /dashboard/project/:projectId/easy/:taskId
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
  ShieldCheck,
  Bot,
  Send,
  Lightbulb,
  ArrowRight,
  ChevronDown,
} from "lucide-react";
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
import { useAuth } from "@/hooks/useAuth";
import { uploadFileToS3 } from "@/services/fileService";
import { API_BASE, getApiError } from "@/lib/apiConfig";
import {
  fetchDailyCreativeIdea,
  type DailyCreativeIdea,
} from "@/services/trendsApi";

gsap.registerPlugin(useGSAP);

// ─── Constants ───────────────────────────────────────────────────────────────

const PLATFORMS = ["Instagram", "TikTok", "Shopee"] as const;
const FORMAT_COPY: Record<string, { label: string; description: string }> = {
  image_poster: { label: "Poster", description: "One image for social media." },
  carousel: { label: "Carousel", description: "A set of swipeable images." },
  video_ad: { label: "Video", description: "A short social-media video." },
  text_copy: { label: "Caption", description: "A caption or ad message." },
  audio_ad: { label: "Audio", description: "A spoken ad with optional music." },
};
const FORMAT_DETAILS: Record<string, { bestFor: string; example: string }> = {
  image_poster: {
    bestFor: "Sales, new products, events, and simple announcements.",
    example: "A product photo with a short offer and a clear Shop Now button.",
  },
  carousel: {
    bestFor: "Showing several products, benefits, or steps.",
    example: "Four swipeable images that explain a product from problem to purchase.",
  },
  video_ad: {
    bestFor: "Product demonstrations, stories, and short social videos.",
    example: "A quick product demo with captions for TikTok or Instagram.",
  },
  text_copy: {
    bestFor: "Writing captions, promotions, and product messages.",
    example: "A ready-to-post caption with a headline, offer, and call to action.",
  },
  audio_ad: {
    bestFor: "Voiceovers, spoken promotions, and short audio messages.",
    example: "A friendly product introduction with optional background music.",
  },
};
const ESSENTIAL_FIELDS = new Set([
  "product_name",
  "key_message",
  "platform",
  "target_audience",
  "call_to_action",
  "language",
  "creative_mode",
  "opening_hook",
]);
const ESSENTIAL_ORDER = [
  "product_name",
  "platform",
  "target_audience",
  "key_message",
  "call_to_action",
  "language",
  "creative_mode",
  "opening_hook",
];

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

type FormErrors = Record<string, string>;

interface AutofillResponse {
  selected_design_type: string;
  form_values: FormState;
  assistant_message: string;
  missing_fields?: string[];
  reference_recommendations?: string[];
  used_fallback?: boolean;
}

interface SetupAssistantMessage {
  role: "user" | "assistant";
  text: string;
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
    // A row of social-post panels communicates the multi-slide format more
    // clearly than a generic business photo.
    previewImage: "https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=800&h=520&fit=crop&q=85",
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
      brand_tone: "Bold and eye-catching",
      visual_style: "Product-first photography",
      video_duration: "15s",
      call_to_action: "Learn More",
      language: "English",
      creative_mode: "voiceover",
      opening_hook: "Sudden action → product reveal",
      code_switching: "No",
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
      platform: "instagram",
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
      platform: "tiktok",
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
  key_message: { label: "Key message", type: "textarea", placeholder: "What should customers know about your product or offer?", required: true },
  brand_tone: { label: "Brand Tone", type: "text", placeholder: "e.g. Playful and trendy" },
  visual_style: { label: "Visual Style", type: "text", placeholder: "e.g. Japanese minimalist" },
  color_palette: { label: "Color Palette", type: "text", placeholder: "e.g. Brown, gold, white" },
  reference_images: { label: "Reference Images", type: "file", placeholder: "Upload reference images" },
  video_duration: { label: "Video Duration", type: "text", placeholder: "e.g. 15s, 30s, 60s" },
  slide_count: { label: "Number of Slides", type: "text", placeholder: "e.g. 3-5" },
  copy_length: { label: "Copy Length", type: "text", placeholder: "e.g. Short (1-2 lines), Medium, Long" },
  call_to_action: { label: "Approved call to action", type: "text", placeholder: "e.g. Shop Now, Learn More", required: true },
  language: { label: "Output language", type: "text", placeholder: "e.g. English, Bahasa Melayu", required: true },
  audio_duration: { label: "Audio Duration", type: "text", placeholder: "e.g. 15s, 30s, 60s" },
  voice_tone: { label: "Voice Tone", type: "text", placeholder: "e.g. Warm and conversational" },
  audio_emotion: { label: "Voice Emotion (ElevenLabs v3)", type: "select", placeholder: "Choose emotion tone" },
  background_music_style: { label: "Background Music Style", type: "text", placeholder: "e.g. Lo-fi chill, Upbeat pop" },
  creative_mode: { label: "How should the video speak?", type: "select", placeholder: "Select a video style", required: true },
  opening_hook: { label: "Opening hook", type: "select", placeholder: "Choose how the video stops the scroll", required: true },
  code_switching: { label: "Allow code-switching?", type: "select", placeholder: "Choose a language policy" },
  forbidden_claims: { label: "Claims or themes to avoid", type: "textarea", placeholder: "e.g. No medical claims, discounts, guarantees, or competitor comparisons" },
  brand_rules: { label: "Brand rules", type: "textarea", placeholder: "e.g. Always show the logo; avoid slang; use approved product photography only" },
  compliance_constraints: { label: "Legal or compliance notes", type: "textarea", placeholder: "Add required disclaimers, category restrictions, or review notes" },
};

// Easy Mode should favour a confident choice over a blank input. Advanced Mode
// remains available when a user needs a custom value outside these options.
const EASY_FIELD_CHOICES: Record<string, string[]> = {
  target_audience: ["Gen Z", "Young professionals", "Families", "General audience"],
  brand_tone: ["Bold and eye-catching", "Friendly and conversational", "Premium and polished", "Warm and trustworthy"],
  visual_style: ["Modern minimalist flat design", "Product-first photography", "Clean editorial layout", "Playful illustration"],
  color_palette: ["Vibrant gradient tones", "Warm neutral tones", "Bold high contrast", "Soft pastel tones"],
  slide_count: ["3", "4", "5"],
  video_duration: ["15s", "30s", "60s"],
  copy_length: ["Short (1-2 sentences)", "Medium (3-5 sentences)", "Long (6-8 sentences)"],
  call_to_action: ["Shop Now", "Learn More", "Get Started", "Send Message"],
  language: ["English", "Bahasa Melayu", "Chinese", "Tamil"],
  audio_duration: ["15s", "30s", "60s"],
  voice_tone: ["Conversational and friendly", "Warm and professional", "Energetic and playful", "Calm and reassuring"],
  audio_emotion: ["Excited", "Warm", "Authoritative", "Urgent", "Playful", "Conversational"],
  background_music_style: ["Lo-fi chill beats", "Upbeat pop", "Soft acoustic", "No background music"],
  creative_mode: ["speaker_led", "voiceover", "music_first"],
  opening_hook: [
    "Sudden action → product reveal",
    "Shock impact → instant product snap",
    "Unexpected visual transformation",
    "Problem first → product solution",
    "Immediate product demonstration",
  ],
  code_switching: ["No", "Yes"],
};

function normalizeEasyChoice(fieldName: string, value: string): string {
  const choices = EASY_FIELD_CHOICES[fieldName];
  if (!choices || !value) return value;
  const normalized = value.trim().toLocaleLowerCase();
  return choices.find((choice) => choice.toLocaleLowerCase() === normalized) ?? value;
}

const CREATIVE_MODE_LABELS: Record<string, { label: string; description: string }> = {
  speaker_led: {
    label: "Speaker on camera",
    description: "A visible person speaks. Includes narration, captions, and lip-sync review.",
  },
  voiceover: {
    label: "Voiceover",
    description: "Narration plays over product or lifestyle visuals. No face-sync requirement.",
  },
  music_first: {
    label: "Music + on-screen text",
    description: "No spoken script. The story relies on visuals, captions, pacing, and music.",
  },
};

const OPENING_HOOK_LABELS: Record<string, { label: string; description: string }> = {
  "Sudden action → product reveal": {
    label: "Action → product reveal",
    description: "A safe, high-energy clash or stunt interrupts the scroll, then match-cuts into the product.",
  },
  "Shock impact → instant product snap": {
    label: "Shock cut → product",
    description: "A sharp one-shot impact, speed ramp, and hard snap reveal the product without a slow animated transition.",
  },
  "Unexpected visual transformation": {
    label: "Visual transformation",
    description: "Begin with an unexpected change in setting, object, or scale that resolves into the product.",
  },
  "Problem first → product solution": {
    label: "Problem → solution",
    description: "Open on a relatable frustration, then reveal the product as the clear next step.",
  },
  "Immediate product demonstration": {
    label: "Product demonstration",
    description: "Show the product working immediately with a bold camera move or satisfying close-up.",
  },
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
  {
    id: "location_ref",
    label: "Shop / Location",
    exampleImage: "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&h=400&fit=crop&q=80",
    description: "Your shopfront, stall, interior, or campaign location.",
    guideText: "💡 Best location reference:\n1. Capture the full shopfront or stall signage straight-on.\n2. Include enough surrounding detail to establish the setting.\n3. Avoid covering the storefront with people or vehicles.\n4. Add verified address and opening hours in the brief; the image alone is not treated as proof.",
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
      common: ["product_name", "key_message", "call_to_action", "language", "target_audience", "platform", "brand_tone"],
      specific: ["opening_hook", "creative_mode", "video_duration", "visual_style", "code_switching", "reference_images"],
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
      specific: ["audio_duration", "voice_tone", "audio_emotion", "background_music_style"],
    },
  },
];

// ─── Component ───────────────────────────────────────────────────────────────

export default function EasyGenerationPage() {
  const { projectId, taskId } = useParams<{ projectId: string; taskId?: string }>();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const assistantInputRef = useRef<HTMLTextAreaElement>(null);
  const { user } = useAuth();

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
    location_ref: useRef<HTMLInputElement>(null),
  };

  // Modal state for Slot guidance
  const [activeSlotGuidance, setActiveSlotGuidance] = useState<RefImageSlot | null>(null);
  const [safetyDetailsOpen, setSafetyDetailsOpen] = useState(false);
  const [briefConfirmed, setBriefConfirmed] = useState(false);
  const [assistantInput, setAssistantInput] = useState("");
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantMessages, setAssistantMessages] = useState<SetupAssistantMessage[]>([
    {
      role: "assistant",
      text: "Tell me about your product and the ad you want. I will ask for anything missing, then fill the form for you.",
    },
  ]);
  const [referenceRecommendations, setReferenceRecommendations] = useState<string[]>([]);
  const [dailyIdea, setDailyIdea] = useState<DailyCreativeIdea | null>(null);
  const [dailyIdeaLoading, setDailyIdeaLoading] = useState(true);

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

  useEffect(() => {
    let cancelled = false;
    setDailyIdeaLoading(true);
    fetchDailyCreativeIdea("malaysia")
      .then((idea) => {
        if (!cancelled) setDailyIdea(idea);
      })
      .catch((error) => {
        console.warn("Today's creative idea is unavailable:", error);
      })
      .finally(() => {
        if (!cancelled) setDailyIdeaLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
    if (taskId) {
      navigate(`/dashboard/project/${projectId}/advance/${taskId}`);
      return;
    }
    const loadingToast = toast.loading("Creating an Advanced Mode task...");
    try {
      // The unscoped Easy page means "new generation". Never select a prior
      // project task here; users can deliberately reopen one from its task row.
      const newTask = await createGenerationTask(projectId);
      toast.dismiss(loadingToast);
      navigate(`/dashboard/project/${projectId}/advance/${newTask.id}`);
    } catch (err) {
      toast.dismiss(loadingToast);
      toast.error("Failed to create an Advanced Mode task");
    }
  }

  // Template guides remain available as optional help.
  function handleCardClick(designType: DesignTypeSchema) {
    setPreviewingType(designType);
    setGuideModalOpen(true);
  }

  // Select a format, apply safe defaults, and continue immediately.
  function handleApplyTemplate(designType: DesignTypeSchema) {
    setSelectedType(designType);
    
    // Apply preset defaults
    const preset = DESIGN_PRESETS[designType.id];
    setFormState(preset ? { ...preset.defaults } : {});
    setFormErrors({});
    setTouched({});
    setSlotFiles({});
    setSafetyDetailsOpen(false);
    setBriefConfirmed(false);
    setStep(3);
    setGuideModalOpen(false);
    setPreviewingType(null);
    requestAnimationFrame(() => containerRef.current?.scrollIntoView({ block: "start" }));
  }

  function handleBackToDesignType() {
    setStep(2);
    requestAnimationFrame(() => containerRef.current?.scrollIntoView({ block: "start" }));
  }

  function handleFieldChange(fieldName: string, value: string) {
    setFormState((prev) => ({ ...prev, [fieldName]: value }));
    setBriefConfirmed(false);
    // Clear error on change if field becomes valid
    if (fieldName === "product_name" || fieldName === "key_message" || fieldName === "call_to_action" || fieldName === "language" || fieldName === "creative_mode" || fieldName === "opening_hook") {
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
    if (selectedType?.id === "video_ad" && !formState[fieldName]?.trim() && ["call_to_action", "language", "creative_mode", "opening_hook"].includes(fieldName)) {
      setFormErrors((prev) => ({ ...prev, [fieldName]: `${FIELD_META[fieldName]?.label ?? fieldName} is required` }));
    }
  }

  async function handleAssistantSubmit() {
    const message = assistantInput.trim();
    if (!message || assistantLoading) return;

    setAssistantMessages((current) => [...current, { role: "user", text: message }]);
    setAssistantInput("");
    setAssistantLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/generation/autofill`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_prompt: message,
          current_design_type: selectedType?.id ?? null,
          current_values: formState,
        }),
      });
      if (!response.ok) {
        throw new Error(await getApiError(response, "The setup assistant could not update the form"));
      }

      const result = (await response.json()) as AutofillResponse;
      const availableSchema = schema.length > 0 ? schema : FALLBACK_SCHEMA;
      const suggestedType = availableSchema.find(
        (designType) => designType.id === result.selected_design_type,
      );
      if (!suggestedType) {
        throw new Error("The assistant selected an unsupported ad format.");
      }

      const presetValues = DESIGN_PRESETS[suggestedType.id]?.defaults ?? {};
      const mergedValues = {
        ...presetValues,
        ...(selectedType?.id === suggestedType.id ? formState : {}),
        ...result.form_values,
      };
      const nextValues = Object.fromEntries(
        Object.entries(mergedValues).map(([fieldName, value]) => [
          fieldName,
          normalizeEasyChoice(fieldName, value),
        ]),
      );
      setSelectedType(suggestedType);
      setFormState(nextValues);
      setFormErrors({});
      setTouched({});
      setBriefConfirmed(false);
      setGuideModalOpen(false);
      setPreviewingType(null);
      setSafetyDetailsOpen(Boolean(
        nextValues.forbidden_claims
        || nextValues.brand_rules
        || nextValues.compliance_constraints,
      ));
      setReferenceRecommendations(result.reference_recommendations ?? []);
      setStep(3);

      const missingNote = result.missing_fields?.length
        ? ` Still needed: ${result.missing_fields.map((field) => FIELD_META[field]?.label ?? field).join(", ")}.`
        : "";
      const fallbackNote = result.used_fallback
        ? " AI extraction was temporarily unavailable, so I used the safest matching preset."
        : "";
      setAssistantMessages((current) => [
        ...current,
        {
          role: "assistant",
          text: `${result.assistant_message}${missingNote}${fallbackNote}`,
        },
      ]);
      toast.success(`${suggestedType.label} selected and form updated`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "The setup assistant failed";
      setAssistantMessages((current) => [
        ...current,
        { role: "assistant", text: errorMessage },
      ]);
      toast.error(errorMessage);
    } finally {
      setAssistantLoading(false);
    }
  }

  function handleUseDailyIdea() {
    if (!dailyIdea) return;
    const prompt = [
      `Adapt today's creative idea for my product: ${dailyIdea.title}.`,
      dailyIdea.idea,
      `Opening hook: ${dailyIdea.hook}`,
      `Recommended format: ${dailyIdea.format}.`,
      "Ask me for any important product detail that is still missing before finalising the form.",
    ].join(" ");
    setAssistantInput(prompt);
    setAssistantMessages((current) => [
      ...current,
      {
        role: "assistant",
        text: `I added "${dailyIdea.title}" to the chat. Add your product or offer, then send it.`,
      },
    ]);
    window.setTimeout(() => assistantInputRef.current?.focus(), 50);
  }

  function isFormValid(): boolean {
    const baseValid = !!(formState.product_name?.trim() && formState.key_message?.trim());
    if (selectedType?.id !== "video_ad") return baseValid && briefConfirmed;
    return !!(
      baseValid
      && formState.call_to_action?.trim()
      && formState.language?.trim()
      && formState.creative_mode?.trim()
      && formState.opening_hook?.trim()
      && briefConfirmed
    );
  }

  // Handle file addition for a specific slot
  function handleSlotFileChange(slotId: string, files: FileList | null) {
    if (!files || files.length === 0) return;
    const file = files[0];
    setBriefConfirmed(false);
    
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
    setBriefConfirmed(false);
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
    const uploadToast = Object.keys(slotFiles).length > 0
      ? toast.loading("Uploading reference assets to S3...")
      : null;

    try {
      // 1. Upload files to S3
      const uploadedUrls: string[] = [];
      const email = user?.profile?.email;
      if (!email) {
        throw new Error("Your authenticated email is required to upload assets.");
      }

      for (const [slotId, info] of Object.entries(slotFiles)) {
        try {
          const res = await uploadFileToS3(info.file, {
            filename: info.file.name,
            contentType: info.file.type || "application/octet-stream",
            fileSize: info.file.size,
            username: email,
            projectId,
            assetType: "reference",
          });
          uploadedUrls.push(res.public_url);
        } catch (uploadErr) {
          console.error(`Failed to upload ${slotId} reference:`, uploadErr);
          throw new Error(`Failed to upload reference image "${info.file.name}"`);
        }
      }

      if (uploadToast) {
        toast.dismiss(uploadToast);
      }

      // 2. Create the generation task
      const task = taskId ? { id: taskId } : await createGenerationTask(projectId);

      // 3. Stay in the guided flow: results and feedback are handled by the
      // Easy Results gallery. Advanced canvas remains an explicit opt-in.
      navigate(`/dashboard/project/${projectId}/easy/${task.id}/results`, {
        state: {
          guidedMode: true,
          designType: selectedType.id,
          guidedInputs: formState,
          guidedReferences: uploadedUrls,
        },
      });
    } catch (err) {
      if (uploadToast) {
        toast.dismiss(uploadToast);
      }
      const message = err instanceof Error ? err.message : "Failed to create generation task";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  // ─── Render ──────────────────────────────────────────────────────────────

  return (
    <div ref={containerRef} className="flex min-h-full flex-col bg-gradient-to-b from-surface-inset/35 via-background to-background px-4 py-4 sm:px-6">
      <div className="mx-auto mb-4 grid w-full max-w-6xl grid-cols-[1fr_auto_1fr] items-center gap-3">
        <div>
          <button
            type="button"
            onClick={() => navigate(`/dashboard/project/${projectId}`)}
            className="inline-flex min-h-11 items-center gap-2 rounded-lg px-2 text-sm font-medium text-text-muted hover:bg-surface-inset hover:text-text-heading"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Project
          </button>
        </div>
        <div className="flex w-[360px] max-w-full rounded-lg border border-border-default bg-surface-card p-1 shadow-sm">
          <span className="flex-1 rounded-md bg-primary py-2 text-center text-sm font-semibold text-primary-foreground shadow-sm">
            Easy Mode
          </span>
          <button
            type="button"
            onClick={handleToggleToAdvanced}
            className="flex-1 rounded-md py-2 text-center text-sm font-semibold text-text-muted transition-colors hover:bg-surface-inset hover:text-text-heading"
          >
            Advanced Mode
          </button>
        </div>
        <div className="flex justify-end">
          {taskId && (
            <Button variant="outline" size="sm" onClick={() => navigate(`/dashboard/project/${projectId}/easy/${taskId}/results`)}>
              Results
            </Button>
          )}
        </div>
      </div>

      <section
        aria-label="Today's creative idea"
        className="mx-auto mb-5 w-full max-w-6xl overflow-hidden rounded-2xl border border-amber-200/80 bg-gradient-to-r from-amber-50/90 via-surface-card to-surface-card shadow-sm dark:border-amber-900/60 dark:from-amber-950/25"
      >
        {dailyIdeaLoading ? (
          <div className="flex min-h-24 items-center gap-3 px-5 text-sm text-text-muted">
            <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
            Finding today&apos;s idea
          </div>
        ) : dailyIdea ? (
          <>
            <div className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center">
              <div className="flex min-w-0 flex-1 items-start gap-3">
                <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
                  <Lightbulb className="h-5 w-5" aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-700 dark:text-amber-300">
                      Today&apos;s idea
                    </p>
                    <span className="rounded-full bg-surface-card/80 px-2 py-0.5 text-[11px] font-medium text-text-muted">
                      Malaysia
                    </span>
                  </div>
                  <h3 className="mt-1 line-clamp-2 text-[15px] font-semibold leading-5 text-text-heading">{dailyIdea.title}</h3>
                  <p className="mt-1 line-clamp-1 text-sm leading-5 text-text-muted">
                    {dailyIdea.why_today}
                  </p>
                </div>
              </div>
              <Button type="button" size="sm" onClick={handleUseDailyIdea} className="shrink-0">
                Add to chat
                <ArrowRight className="ml-1.5 h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
            <details className="border-t border-amber-200/70 bg-surface-card/55 dark:border-amber-900/50">
              <summary className="flex cursor-pointer list-none items-center gap-1.5 px-5 py-2.5 text-xs font-semibold text-text-body marker:hidden">
                Preview idea
                <ChevronDown className="h-3.5 w-3.5 text-text-muted" aria-hidden="true" />
              </summary>
              <div className="grid gap-3 border-t border-border-default/60 px-5 py-4 text-sm text-text-muted sm:grid-cols-[1fr_auto]">
                <p className="leading-6">{dailyIdea.idea}</p>
                <div className="flex flex-wrap items-start gap-2 sm:max-w-64">
                  <span className="rounded-full bg-surface-inset px-2.5 py-1 text-xs">Hook: {dailyIdea.hook}</span>
                  <span className="rounded-full bg-surface-inset px-2.5 py-1 text-xs">Format: {dailyIdea.format}</span>
                </div>
              </div>
            </details>
          </>
        ) : (
          <p className="px-5 py-4 text-sm text-text-muted">Today&apos;s idea is temporarily unavailable.</p>
        )}
      </section>

      <div className="mx-auto grid w-full max-w-6xl items-start gap-7 lg:grid-cols-[340px_minmax(0,1fr)]">
      <section aria-label="Fill the form by chat" className="w-full overflow-hidden rounded-2xl border border-border-default/80 bg-surface-card shadow-[0_10px_35px_rgba(15,23,42,0.06)] lg:sticky lg:top-4">
        <div className="flex items-center gap-3 border-b border-border-default px-4 py-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <Bot className="h-5 w-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h3 className="text-[15px] font-semibold leading-5 text-text-heading">Fill with chat</h3>
            <p className="mt-0.5 text-[13px] leading-5 text-text-muted">Describe your ad. I will fill the form.</p>
          </div>
        </div>
        <div className="max-h-72 min-h-40 space-y-3 overflow-y-auto bg-surface-inset/40 px-4 py-3">
          {assistantMessages.slice(-4).map((message, index) => (
            <div key={`${message.role}-${index}-${message.text.slice(0, 16)}`} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
              <p className={`max-w-[78%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
                message.role === "user"
                  ? "rounded-br-md bg-primary text-primary-foreground"
                  : "rounded-bl-md border border-border-default bg-surface-card text-text-body"
              }`}>
                {message.text}
              </p>
            </div>
          ))}
          {assistantLoading && (
            <div className="flex items-center gap-2 text-sm text-text-muted">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              Filling your form
            </div>
          )}
        </div>
        <div className="border-t border-border-default p-3">
          {assistantMessages.length === 1 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {["TikTok product video", "Instagram sale poster", "Shopee product ad"].map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => setAssistantInput(suggestion)}
                  className="rounded-full border border-border-default px-3 py-1.5 text-xs font-medium text-text-body hover:border-primary hover:text-primary"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <Textarea
              ref={assistantInputRef}
              value={assistantInput}
              onChange={(event) => setAssistantInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void handleAssistantSubmit();
                }
              }}
              placeholder="Tell JusAds what you want to advertise"
              aria-label="Describe the ad you want"
              rows={1}
              className="min-h-11 resize-none"
            />
            <Button
              type="button"
              onClick={() => void handleAssistantSubmit()}
              disabled={!assistantInput.trim() || assistantLoading}
              className="min-w-11 self-stretch px-3"
              aria-label="Send message"
            >
              {assistantLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
          {referenceRecommendations.length > 0 && (
            <p className="mt-3 text-xs text-text-muted">
              Suggested photos: {referenceRecommendations.join(", ")}
            </p>
          )}
        </div>
      </section>

      {/* Step 2: Design Type Picker */}
      {step === 2 && (
        <div className="step-content flex w-full min-w-0 flex-col gap-5">
          <div className="border-b border-border-default/70 pb-5">
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-primary">Step 1 of 2</p>
            <h3 className="text-[18px] font-semibold leading-6 tracking-[-0.01em] text-text-heading">Choose an ad format</h3>
            <p className="mt-2 text-[15px] leading-6 text-text-muted">Pick the result you want to create. You can change it later.</p>
          </div>

          {schemaLoading ? (
            <div className="flex items-center justify-center gap-3 py-16 text-sm text-text-muted">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              Loading formats
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {schema.map((designType) => {
                const IconComponent = ICON_MAP[designType.icon] || Image;
                const preset = DESIGN_PRESETS[designType.id];
                const display = FORMAT_COPY[designType.id] ?? {
                  label: designType.label,
                  description: designType.description,
                };
                return (
                  <button
                    key={designType.id}
                    type="button"
                    onClick={() => handleCardClick(designType)}
                    className="group overflow-hidden rounded-xl border border-border-default bg-surface-card text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                  >
                    <span className="relative block h-28 overflow-hidden bg-surface-inset">
                      {preset?.previewImage && (
                        <img src={preset.previewImage} alt="" className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" />
                      )}
                      <span className="absolute bottom-2 left-2 flex h-8 w-8 items-center justify-center rounded-lg bg-black/65 text-white backdrop-blur-sm">
                        <IconComponent className="h-4 w-4" aria-hidden="true" />
                      </span>
                    </span>
                    <span className="block p-4">
                      <span className="block text-base font-semibold text-text-heading">{display.label}</span>
                      <span className="mt-1 block text-sm leading-relaxed text-text-muted">{display.description}</span>
                      <span className="mt-3 block text-sm font-semibold text-primary">View details</span>
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Guide & Preset Preview Modal (Step 2.5) */}
      {guideModalOpen && previewingType && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div role="dialog" aria-modal="true" aria-labelledby="format-guide-title" className="bg-surface-card border border-border-default w-full max-w-3xl rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-border-default flex items-center justify-between bg-muted/30">
              <div className="flex items-center gap-2">
                <Info className="h-5 w-5 text-primary" />
                <h2 id="format-guide-title" className="text-lg font-bold text-text-heading">
                  {FORMAT_COPY[previewingType.id]?.label ?? previewingType.label}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => {
                  setGuideModalOpen(false);
                  setPreviewingType(null);
                }}
                className="text-text-muted hover:text-text-heading rounded p-1 hover:bg-muted/80 cursor-pointer"
                aria-label="Close format guide"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto grid gap-6 md:grid-cols-[1.15fr_1fr]">
              <div className="rounded-xl overflow-hidden border border-border-default bg-muted/20">
                <img
                  src={DESIGN_PRESETS[previewingType.id]?.previewImage}
                  alt={`${FORMAT_COPY[previewingType.id]?.label ?? previewingType.label} example`}
                  className="w-full h-full min-h-64 object-cover"
                />
              </div>

              <div className="space-y-6">
                <div>
                  <p className="text-sm font-semibold text-text-heading">Best for</p>
                  <p className="mt-1 text-sm leading-6 text-text-muted">
                    {FORMAT_DETAILS[previewingType.id]?.bestFor}
                  </p>
                </div>
                <div>
                  <p className="text-sm font-semibold text-text-heading">Example</p>
                  <p className="mt-1 text-sm leading-6 text-text-muted">
                    {FORMAT_DETAILS[previewingType.id]?.example}
                  </p>
                </div>

                <div className="rounded-lg overflow-hidden border border-border-default bg-muted/20">
                  <h3 className="border-b border-border-default px-3 py-2 text-sm font-semibold text-text-heading">
                    Starting settings
                  </h3>
                  <div className="space-y-1 p-2">
                    {Object.entries(DESIGN_PRESETS[previewingType.id]?.defaults || {}).map(([key, val]) => (
                      <div key={key} className="flex justify-between gap-4 rounded-md px-2 py-1.5 text-xs">
                        <span className="text-text-muted capitalize">
                          {key.replace("_", " ")}
                        </span>
                        <span className="font-medium text-primary truncate max-w-[150px]">
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
                {step === 2 ? "Cancel" : "Close"}
              </Button>
              {step === 2 && (
                <Button onClick={() => handleApplyTemplate(previewingType)}>
                  Use this format
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Dynamic Form */}
      {step === 3 && selectedType && (
        <div className="step-content flex w-full min-w-0 flex-col gap-5">
          <div className="border-b border-border-default/70 pb-5">
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-primary">Step 2 of 2</p>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-[18px] font-semibold leading-6 tracking-[-0.01em] text-text-heading">Add your ad details</h3>
                <p className="mt-2 text-[15px] text-text-muted">{FORMAT_COPY[selectedType.id]?.label ?? selectedType.label}</p>
              </div>
              <button
                type="button"
                onClick={() => handleCardClick(selectedType)}
                className="min-h-11 rounded-lg px-3 text-sm font-medium text-primary hover:bg-primary/5"
              >
                Format guide
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-lg bg-primary/5 px-3 py-2.5 text-sm text-text-body">
            <ShieldCheck className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
            JusAds uses only the product facts you provide.
          </div>

          <div className="flex flex-col gap-4 rounded-xl border border-border-default bg-surface-card p-4 sm:p-5">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {[...selectedType.fields.common, ...selectedType.fields.specific]
              .filter((fieldName) => ESSENTIAL_FIELDS.has(fieldName))
              .sort((a, b) => ESSENTIAL_ORDER.indexOf(a) - ESSENTIAL_ORDER.indexOf(b))
              .map((fieldName) => (
                <div
                  key={fieldName}
                  className={["target_audience", "key_message", "creative_mode", "opening_hook"].includes(fieldName) ? "lg:col-span-2" : ""}
                >
                  {renderField(fieldName)}
                </div>
              ))}
            </div>

            <details className="rounded-xl border border-border-default">
              <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 text-sm font-semibold text-text-heading marker:hidden">
                More options
                <span className="text-xs font-normal text-text-muted">Optional</span>
              </summary>
              <div className="flex flex-col gap-4 border-t border-border-default p-4">
                {[...selectedType.fields.common, ...selectedType.fields.specific]
                  .filter((fieldName) => !ESSENTIAL_FIELDS.has(fieldName))
                  .map((fieldName) => renderField(fieldName))}
              </div>
            </details>

            <div className="rounded-xl border border-border-default">
              <button
                type="button"
                onClick={() => setSafetyDetailsOpen((open) => !open)}
                aria-expanded={safetyDetailsOpen}
                className="flex min-h-12 w-full items-center justify-between gap-3 px-4 text-left"
              >
                <span className="text-sm font-semibold text-text-heading">Brand and safety rules</span>
                <span className="text-xs font-normal text-text-muted">Optional</span>
              </button>
              {safetyDetailsOpen && (
                <div className="flex flex-col gap-4 border-t border-border-default p-4">
                  {renderField("forbidden_claims")}
                  {renderField("brand_rules")}
                  {renderField("compliance_constraints")}
                </div>
              )}
            </div>
          </div>

          <label className="flex min-h-12 cursor-pointer items-start gap-3 rounded-lg border border-border-default bg-surface-card p-3 text-sm leading-relaxed text-text-body">
            <input
              type="checkbox"
              checked={briefConfirmed}
              onChange={(event) => setBriefConfirmed(event.target.checked)}
              className="mt-0.5 h-5 w-5 shrink-0 rounded accent-primary"
            />
            <span>
              <span className="block font-semibold text-text-heading">I have checked these details</span>
              <span className="mt-1 block text-text-muted">The product facts, offer, and wording are correct.</span>
            </span>
          </label>

          {/* Actions */}
          <div className="flex flex-col-reverse gap-3 border-t border-border-default pt-5 sm:flex-row sm:items-center sm:justify-between">
            <Button variant="ghost" onClick={handleBackToDesignType}>
              Change format
            </Button>

            <Button
              onClick={handleSubmit}
              disabled={!isFormValid() || submitting}
              className="min-h-12 bg-primary px-6 text-base font-semibold text-white hover:bg-primary/95"
            >
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {selectedType.id === "video_ad" ? "Create storyboard" : "Create my ad"}
            </Button>
          </div>
        </div>
      )}
      </div>

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
    const fieldId = `easy-${fieldName}`;

    // ── Reference Images — guided slots ──────────────────────────────────
    if (fieldName === "reference_images") {
      if (selectedType && ["text_copy", "audio_ad"].includes(selectedType.id)) {
        return null;
      }
      return (
        <div key={fieldName} className="rounded-xl bg-surface-inset/30 p-4">
          <div className="flex items-center justify-between gap-4 text-sm font-medium text-text-heading">
            <span>Optional visual references</span>
            <span className="text-xs font-normal text-text-muted">Photos, logo, or inspiration</span>
          </div>
          <div className="mt-4 flex flex-col gap-3">
            <p className="text-[11px] text-text-muted">
              Add only what you have. Product, character/logo, style, and shop/location references are optional.
            </p>

          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
            {REF_IMAGE_SLOTS.map((slot) => {
              const fileInfo = slotFiles[slot.id];
              return (
                <div key={slot.id} className="relative flex flex-col justify-between gap-2 rounded-lg border border-border-default bg-surface-card p-3 shadow-xs">
                  
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
        </div>
      );
    }

    // ── Platform select with aspect ratio hints ─────────────────────────
    if (meta.type === "select" && fieldName === "platform") {
      return (
        <div key={fieldName} className="flex flex-col gap-1.5">
          <label htmlFor={fieldId} className="text-sm font-semibold text-text-heading">{meta.label}</label>
          <Select
            value={value || undefined}
            onValueChange={(val) => handleFieldChange(fieldName, val || "")}
          >
            <SelectTrigger id={fieldId} className="min-h-11 w-full bg-surface-card border-border-default">
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
            <p className="text-xs text-text-muted mt-1">
              Recommended size: {
                value === "instagram" ? "1:1 (Square) or 4:5 (Vertical) or 9:16 (Reels)" :
                value === "tiktok" ? "9:16 (Vertical)" :
                value === "shopee" ? "1:1 (Square)" : ""
              }
            </p>
          )}
        </div>
      );
    }

    // ── Textarea ────────────────────────────────────────────────────────
    const choices = EASY_FIELD_CHOICES[fieldName];
    if (choices) {
      return (
        <fieldset key={fieldName} className="flex flex-col gap-2">
          <legend className="text-sm font-semibold text-text-heading">
            {meta.label}
          </legend>
          <div className={`grid gap-2 ${
            fieldName === "creative_mode"
              ? "grid-cols-1 sm:grid-cols-3"
              : fieldName === "opening_hook"
                ? "grid-cols-1 sm:grid-cols-2"
                : "grid-cols-2 sm:grid-cols-4"
          }`}>
            {choices.map((choice) => {
              const selected = value === choice;
              const creativeMode = fieldName === "creative_mode" ? CREATIVE_MODE_LABELS[choice] : undefined;
              const openingHook = fieldName === "opening_hook" ? OPENING_HOOK_LABELS[choice] : undefined;
              const choiceDetails = creativeMode ?? openingHook;
              return (
                <button
                  key={choice}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => handleFieldChange(fieldName, choice)}
                  className={`min-h-10 rounded-lg border px-3 py-2 text-left text-xs transition-colors ${
                    selected
                      ? "border-primary bg-primary text-primary-foreground shadow-sm"
                      : "border-border-default bg-surface-card text-text-body hover:border-primary/50 hover:bg-primary/5"
                  }`}
                >
                  <span className="block font-semibold">{choiceDetails?.label ?? choice}</span>
                  {choiceDetails && (
                    <span className={`mt-1 block text-[11px] leading-relaxed ${selected ? "text-primary-foreground/80" : "text-text-muted"}`}>
                      {choiceDetails.description}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
          {isTouched && error && <p className="text-xs text-destructive">{error}</p>}
        </fieldset>
      );
    }

    if (meta.type === "textarea") {
      return (
        <div key={fieldName} className="flex flex-col gap-1.5">
          <label htmlFor={fieldId} className="text-sm font-semibold text-text-heading">
            {meta.label}
            {meta.required && <span className="text-destructive"> *</span>}
          </label>
          <Textarea
            id={fieldId}
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
        <label htmlFor={fieldId} className="text-sm font-semibold text-text-heading">
          {meta.label}
          {meta.required && <span className="text-destructive"> *</span>}
        </label>
        <Input
          id={fieldId}
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
