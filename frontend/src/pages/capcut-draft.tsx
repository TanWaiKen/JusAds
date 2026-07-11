import { useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Download, FileVideo, Image, Loader2, CheckCircle2, Info, FolderOpen } from "lucide-react";

gsap.registerPlugin(useGSAP);

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

interface DraftResult {
  success: boolean;
  draft_name: string;
  download_url: string;
  instructions: {
    title: string;
    steps: string[];
    tips: string[];
    note: string;
    auto_install_available: boolean;
  };
  video_duration_sec: number | null;
  image_duration_sec: number;
  image_start_sec: number;
  transition: string;
  canvas: string;
}

export default function CapcutDraftPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DraftResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"local" | "upload">("local");
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  // Upload form state
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [draftName, setDraftName] = useState("tiger_sugar_promo");
  const [transitionType, setTransitionType] = useState("fade");
  const [imageDuration, setImageDuration] = useState(3.0);
  const [imageStart, setImageStart] = useState(0.0);

  useGSAP(() => {
    gsap.from(".page-header", {
      y: 20,
      autoAlpha: 0,
      duration: 0.5,
      ease: "power2.out",
    });
    gsap.from(".form-section", {
      y: 30,
      autoAlpha: 0,
      duration: 0.5,
      delay: 0.15,
      ease: "power2.out",
    });
  }, { scope: containerRef });

  const handleGenerateLocal = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setSaveMessage(null);

    try {
      const formData = new FormData();
      formData.append("draft_name", draftName);
      formData.append("transition_type", transitionType);
      formData.append("image_duration_sec", imageDuration.toString());
      formData.append("image_start_sec", imageStart.toString());

      const res = await fetch(`${API_BASE}/api/capcut/generate-draft-local`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Generation failed");
      }

      const data: DraftResult = await res.json();
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateUpload = async () => {
    if (!videoFile || !imageFile) {
      setError("Please select both a video and an image file.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setSaveMessage(null);

    try {
      const formData = new FormData();
      formData.append("video", videoFile);
      formData.append("image", imageFile);
      formData.append("draft_name", draftName);
      formData.append("transition_type", transitionType);
      formData.append("image_duration_sec", imageDuration.toString());
      formData.append("image_start_sec", imageStart.toString());

      const res = await fetch(`${API_BASE}/api/capcut/generate-draft`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Generation failed");
      }

      const data: DraftResult = await res.json();
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadZip = () => {
    if (!result) return;
    window.open(`${API_BASE}${result.download_url}`, "_blank");
  };

  return (
    <div ref={containerRef} className="min-h-screen bg-background p-6 md:p-10">
      {/* Header */}
      <div className="page-header max-w-3xl mx-auto mb-8">
        <h1 className="text-3xl font-bold text-foreground mb-2">
          CapCut Draft Generator
        </h1>
        <p className="text-muted-foreground">
          Generate a CapCut-compatible project draft with video + image overlay + transition.
          Save it directly into your CapCut Drafts folder — no manual file extraction needed.
        </p>
      </div>

      {/* Form */}
      <div className="form-section max-w-3xl mx-auto space-y-6">
        {/* Mode Toggle */}
        <div className="flex gap-2 p-1 bg-muted rounded-lg w-fit">
          <button
            onClick={() => setMode("local")}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              mode === "local"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Use Test Assets
          </button>
          <button
            onClick={() => setMode("upload")}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              mode === "upload"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Upload Files
          </button>
        </div>

        {/* Upload inputs (only when mode is upload) */}
        {mode === "upload" && (
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-foreground flex items-center gap-1.5">
                <FileVideo className="w-4 h-4" /> Video File
              </span>
              <input
                type="file"
                accept="video/*"
                onChange={(e) => setVideoFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary file:text-primary-foreground hover:file:bg-primary/90 cursor-pointer"
              />
            </label>
            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-foreground flex items-center gap-1.5">
                <Image className="w-4 h-4" /> Image Overlay
              </span>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setImageFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary file:text-primary-foreground hover:file:bg-primary/90 cursor-pointer"
              />
            </label>
          </div>
        )}

        {mode === "local" && (
          <div className="rounded-lg border border-border bg-muted/50 p-4 text-sm text-muted-foreground">
            <p className="font-medium text-foreground mb-1">Using local test assets:</p>
            <ul className="list-disc list-inside space-y-1">
              <li>Video: <code className="text-xs bg-muted px-1 rounded">backend/assets/Test Video.mp4</code></li>
              <li>Image: <code className="text-xs bg-muted px-1 rounded">backend/assets/images/Tiger Sugar Boba/Boba Infographic.jpg</code></li>
            </ul>
          </div>
        )}

        {/* Settings */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">Draft Name</span>
            <input
              type="text"
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">Transition</span>
            <select
              value={transitionType}
              onChange={(e) => setTransitionType(e.target.value)}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="fade">Fade</option>
              <option value="dissolve">Dissolve</option>
              <option value="wipeleft">Wipe Left</option>
              <option value="wiperight">Wipe Right</option>
              <option value="slide">Slide</option>
              <option value="zoom">Zoom</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">Image Duration (s)</span>
            <input
              type="number"
              step="0.5"
              min="0.5"
              max="30"
              value={imageDuration}
              onChange={(e) => setImageDuration(parseFloat(e.target.value))}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">Image Start (s)</span>
            <input
              type="number"
              step="0.5"
              min="0"
              value={imageStart}
              onChange={(e) => setImageStart(parseFloat(e.target.value))}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </label>
        </div>

        {/* Generate Button */}
        <button
          onClick={mode === "local" ? handleGenerateLocal : handleGenerateUpload}
          disabled={loading}
          className="w-full md:w-auto px-6 py-3 rounded-lg bg-primary text-primary-foreground font-medium text-sm hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Generating Draft...
            </>
          ) : (
            <>
              <FileVideo className="w-4 h-4" />
              Generate CapCut Draft
            </>
          )}
        </button>

        {/* Error */}
        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="space-y-4">
            {/* Success Card */}
            <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-4">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="w-5 h-5 text-green-600" />
                <h3 className="font-semibold text-foreground">Draft Generated Successfully!</h3>
              </div>
              <dl className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                <div>
                  <dt className="text-muted-foreground">Draft</dt>
                  <dd className="font-medium">{result.draft_name}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Canvas</dt>
                  <dd className="font-medium">{result.canvas}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Video Duration</dt>
                  <dd className="font-medium">{result.video_duration_sec?.toFixed(1)}s</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Transition</dt>
                  <dd className="font-medium capitalize">{result.transition}</dd>
                </div>
              </dl>

              {/* Primary action: Download + copy path */}
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  onClick={handleDownloadZip}
                  className="px-5 py-2.5 rounded-lg bg-green-600 text-white font-medium text-sm hover:bg-green-700 flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  Download Draft
                </button>

                <button
                  onClick={() => {
                    const path = String.raw`%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`;
                    navigator.clipboard.writeText(path);
                    setSaveMessage("📋 Path copied! Paste in File Explorer address bar, then extract the ZIP there.");
                  }}
                  className="px-5 py-2.5 rounded-lg bg-muted text-foreground border border-border font-medium text-sm hover:bg-muted/80 flex items-center gap-2"
                >
                  <FolderOpen className="w-4 h-4" />
                  Copy CapCut Drafts Path
                </button>
              </div>

              {saveMessage && (
                <p className="mt-3 text-sm font-medium">{saveMessage}</p>
              )}
            </div>

            {/* Instructions */}
            <div className="rounded-lg border border-border bg-card p-5">
              <div className="flex items-center gap-2 mb-3">
                <Info className="w-5 h-5 text-blue-500" />
                <h3 className="font-semibold text-foreground">How to Import into CapCut</h3>
              </div>

              <div className="p-3 rounded-md bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800">
                <ol className="text-sm text-blue-800 dark:text-blue-300 space-y-2">
                  <li><strong>1.</strong> Click <strong>"Download Draft"</strong> above</li>
                  <li><strong>2.</strong> Click <strong>"Copy CapCut Drafts Path"</strong> → paste it into File Explorer address bar → press Enter</li>
                  <li><strong>3.</strong> Extract the downloaded ZIP into that folder (you should see a folder named <code className="text-xs bg-blue-100 dark:bg-blue-900 px-1 rounded">{result.draft_name}</code> with JSON files inside)</li>
                  <li><strong>4.</strong> Open CapCut → your draft appears in the project list. Done!</li>
                </ol>
              </div>

              <div className="mt-4 border-t border-border pt-3">
                <p className="text-xs font-medium text-foreground mb-2">Tips:</p>
                <ul className="space-y-1 text-xs text-muted-foreground">
                  <li>• If the draft doesn't appear, close CapCut completely and reopen it.</li>
                  <li>• The image overlay is on a separate layer — you can move, resize, or adjust opacity inside CapCut.</li>
                  <li>• The transition is at the midpoint of the video — drag it to reposition in CapCut's timeline.</li>
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
