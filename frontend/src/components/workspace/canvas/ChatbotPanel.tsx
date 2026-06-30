import { useState, useRef, useEffect } from "react";
import { toast } from "sonner";
import { sendChatWithAgent } from "@/services/taskApi";
import type { PipelineState } from "@/components/workspace/canvas/graphModel";
import { Send, Sparkles, BookOpen, Bot, User } from "lucide-react";

interface Message {
  sender: "user" | "agent";
  text: string;
  timestamp: Date;
}

interface ChatbotPanelProps {
  projectId: string;
  taskId: string;
  onStateUpdate: (pipeline: PipelineState) => void;
}

export function ChatbotPanel({ projectId, taskId, onStateUpdate }: ChatbotPanelProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "agent",
      text: "Hello! I am your AI Ad Generation Agent chatbot. 🤖\n\nI can generate text copy, image banners, voiceover audio, or video ads for you! Just tell me what you want to create (e.g. *'Generate a Facebook image and text caption ad for a sports watch'*), and I will build the node pipeline on the canvas and run the local generator tools for you.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showGuides, setShowGuides] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userText = input;
    setInput("");
    setMessages((prev) => [...prev, { sender: "user", text: userText, timestamp: new Date() }]);
    setLoading(true);

    try {
      const response = await sendChatWithAgent(projectId, taskId, userText);
      setMessages((prev) => [
        ...prev,
        { sender: "agent", text: response.reply, timestamp: new Date() },
      ]);
      // Update the ComfyUI canvas node graph dynamically!
      onStateUpdate(response.pipeline_state);
      toast.success("Ad assets generated successfully!");
    } catch (err) {
      console.error(err);
      toast.error("Failed to generate ad assets");
      setMessages((prev) => [
        ...prev,
        {
          sender: "agent",
          text: "⚠️ Sorry, I encountered an error while processing your request. Please check your credentials or try again.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col bg-card text-foreground">
      {/* Guides Button */}
      <div className="border-b p-2">
        <button
          onClick={() => setShowGuides(!showGuides)}
          className="flex w-full items-center justify-center gap-1.5 rounded-md bg-secondary/80 px-3 py-1.5 text-xs font-semibold text-secondary-foreground hover:bg-secondary transition-colors"
        >
          <BookOpen size={14} />
          {showGuides ? "Hide Ad Creation Guides" : "Show Ad Creation Guides"}
        </button>
      </div>

      {/* Guides Panel */}
      {showGuides && (
        <div className="max-h-48 overflow-y-auto border-b bg-muted/30 p-3 text-xs space-y-3">
          <h4 className="font-semibold text-primary flex items-center gap-1">
            <Sparkles size={12} />
            Ad Generation Tools Intro
          </h4>
          <div className="space-y-2">
            <details className="cursor-pointer">
              <summary className="font-medium text-foreground hover:underline">1. Text Copy Agent</summary>
              <p className="mt-1 pl-3 text-muted-foreground">
                Generates high-conversion compliance-checked copy, headings, and hashtags using Google Gemini models.
              </p>
            </details>
            <details className="cursor-pointer">
              <summary className="font-medium text-foreground hover:underline">2. Image Creator Agent</summary>
              <p className="mt-1 pl-3 text-muted-foreground">
                Creates premium ad banners using Imagen 4.0. Falls back to local Pillow graphic overlays if quota is exceeded.
              </p>
            </details>
            <details className="cursor-pointer">
              <summary className="font-medium text-foreground hover:underline">3. Audio / Voice Agent</summary>
              <p className="mt-1 pl-3 text-muted-foreground">
                Generates natural voiceovers for your ad copy script using ElevenLabs or localized speech synthesizers.
              </p>
            </details>
            <details className="cursor-pointer">
              <summary className="font-medium text-foreground hover:underline">4. Video Assembler Agent</summary>
              <p className="mt-1 pl-3 text-muted-foreground">
                Stitches generated image frames and audio voiceover voice clips into a final MP4 video ad using local FFMPEG.
              </p>
            </details>
          </div>
        </div>
      )}

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex items-start gap-2.5 ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.sender === "agent" && (
              <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-primary/10 text-primary">
                <Bot size={16} />
              </div>
            )}
            <div
              className={`rounded-lg px-3 py-2 text-sm shadow-sm max-w-[85%] whitespace-pre-wrap leading-relaxed ${
                msg.sender === "user"
                  ? "bg-primary text-primary-foreground font-medium"
                  : "bg-muted text-foreground border border-border"
              }`}
            >
              {msg.text}
            </div>
            {msg.sender === "user" && (
              <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-secondary/80 text-foreground border">
                <User size={16} />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-start gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary animate-bounce">
              <Bot size={16} />
            </div>
            <div className="rounded-lg bg-muted border px-4 py-2.5 text-xs text-muted-foreground flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-ping" />
              <span>Agent is running generation tools locally...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <form onSubmit={handleSend} className="border-t p-3 bg-card flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask AI to generate image, video, audio or copy..."
          disabled={loading}
          className="flex-1 rounded-md border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground hover:bg-primary/95 disabled:opacity-50 transition-colors"
        >
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}

export default ChatbotPanel;
