/**
 * InspectorPanel — right panel showing the selected node's editable properties and output.
 * Label and custom props can be edited inline and dispatch UPDATE_NODE_PROPS.
 */

import { useState, useEffect } from "react";
import type { CanvasNode } from "@/components/workspace/canvas/graphModel";

interface InspectorPanelProps {
  node: CanvasNode | null;
  onUpdateProps?: (nodeId: string, updates: { label?: string; props?: Record<string, string> }) => void;
  onDelete?: (nodeId: string) => void;
  onSendRevision?: (node: CanvasNode, comment: string) => void;
}

interface ParsedScene {
  index: string;
  duration: string;
  visual: string;
  voiceover: string;
  subtitle: string;
}

function parseDirectorPrompt(prompt: string): ParsedScene[] {
  const blocks = prompt.split("\n\n").filter(Boolean);
  return blocks.map((block) => {
    const lines = block.split("\n").map((l) => l.trim());
    const header = lines[0] || ""; // e.g. "Scene 1 — 5s"
    const matchHeader = header.match(/Scene\s+(\d+)\s*(?:—\s*(.*))?/i);
    const index = matchHeader ? matchHeader[1] : "?";
    const duration = matchHeader && matchHeader[2] ? matchHeader[2] : "";

    const visual = lines.find((l) => l.startsWith("Visual:"))?.replace("Visual:", "").trim() || "";
    const voiceover = lines.find((l) => l.startsWith("Voice-over:"))?.replace("Voice-over:", "").trim() || "";
    const subtitle = lines.find((l) => l.startsWith("On-screen text:"))?.replace("On-screen text:", "").trim() || "";

    return { index, duration, visual, voiceover, subtitle };
  });
}

export function InspectorPanel({ node, onUpdateProps, onDelete, onSendRevision }: InspectorPanelProps) {
  const [editLabel, setEditLabel] = useState("");
  const [editProps, setEditProps] = useState<Record<string, string>>({});
  const [revisionComment, setRevisionComment] = useState("");
  const [showRawPrompt, setShowRawPrompt] = useState(false);

  const handleSendRevision = () => {
    if (onSendRevision && node && revisionComment.trim()) {
      onSendRevision(node, revisionComment.trim());
      setRevisionComment("");
    }
  };

  // Sync local state when node changes
  useEffect(() => {
    if (node) {
      setEditLabel(node.label);
      setEditProps({ ...node.props });
      setShowRawPrompt(false);
    }
  }, [node]);

  if (!node) {
    return (
      <div className="w-full p-4">
        <p className="text-sm text-muted-foreground">Select a node to inspect its properties</p>
      </div>
    );
  }

  function handleLabelBlur() {
    if (node && editLabel !== node.label && onUpdateProps) {
      onUpdateProps(node.id, { label: editLabel });
    }
  }

  function handlePropChange(key: string, value: string) {
    setEditProps((prev) => ({ ...prev, [key]: value }));
  }

  function handlePropBlur(key: string) {
    if (node && editProps[key] !== node.props[key] && onUpdateProps) {
      onUpdateProps(node.id, { props: { [key]: editProps[key] } });
    }
  }

  return (
    <div className="w-full h-full overflow-y-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-foreground">Inspector</h3>
        {onDelete && (
          <button
            onClick={() => onDelete(node.id)}
            className="text-xs text-muted-foreground hover:text-destructive transition-colors"
          >
            Delete
          </button>
        )}
      </div>

      {/* Node info — editable label */}
      <div className="mb-4 space-y-3">
        <div>
          <label className="text-xs text-muted-foreground block mb-1">Label</label>
          <input
            type="text"
            value={editLabel}
            onChange={(e) => setEditLabel(e.target.value)}
            onBlur={handleLabelBlur}
            onKeyDown={(e) => { if (e.key === "Enter") handleLabelBlur(); }}
            className="w-full rounded-md border bg-background px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">Type</label>
          <p className="text-sm text-foreground capitalize">{node.type}</p>
        </div>
        <div>
          <label className="text-xs text-muted-foreground">Status</label>
          <p className="text-sm text-foreground capitalize">{node.status}</p>
        </div>
        <div>
          <label className="text-xs text-muted-foreground">Position</label>
          <p className="text-sm text-foreground">
            ({Math.round(node.x)}, {Math.round(node.y)})
          </p>
        </div>
      </div>

      {/* Properties — editable */}
      {Object.keys(editProps).length > 0 && (
        <div className="mb-4">
          <h4 className="mb-2 text-xs font-medium text-muted-foreground">Properties</h4>
          <div className="space-y-3">
            {Object.entries(editProps).map(([key, value]) => {
              if (key === "prompt_used" && node.type === "orchestrator") {
                const parsedScenes = parseDirectorPrompt(value || "");
                return (
                  <div key={key} className="flex flex-col gap-2 border-t pt-3 mt-3 border-border">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Script Details</span>
                      <button
                        type="button"
                        onClick={() => setShowRawPrompt(!showRawPrompt)}
                        className="text-[10px] font-semibold text-primary hover:underline cursor-pointer"
                      >
                        {showRawPrompt ? "View Beautiful Table" : "Edit Raw Script Text"}
                      </button>
                    </div>
                    {showRawPrompt ? (
                      <textarea
                        value={value}
                        onChange={(e) => handlePropChange(key, e.target.value)}
                        onBlur={() => handlePropBlur(key)}
                        className="w-full text-xs font-mono p-2.5 rounded-md border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary min-h-[260px] leading-normal"
                        placeholder="Scene 1 — 5s&#10;Visual: ...&#10;Voice-over: ...&#10;On-screen text: ..."
                      />
                    ) : (
                      <div className="overflow-x-auto border border-border rounded-lg bg-card shadow-sm max-w-full">
                        <table className="min-w-full divide-y divide-border text-[11px]">
                          <thead className="bg-muted/65">
                            <tr>
                              <th className="px-2.5 py-2 text-left font-bold text-muted-foreground w-12">Scene</th>
                              <th className="px-2.5 py-2 text-left font-bold text-muted-foreground min-w-[130px]">Visual Description</th>
                              <th className="px-2.5 py-2 text-left font-bold text-muted-foreground min-w-[110px]">Voiceover (TTS)</th>
                              <th className="px-2.5 py-2 text-left font-bold text-muted-foreground min-w-[100px]">On-Screen Text</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border bg-background">
                            {parsedScenes.map((s, idx) => (
                              <tr key={idx} className="hover:bg-muted/10 transition-colors">
                                <td className="px-2.5 py-2 font-bold text-primary align-top">
                                  {s.index}
                                  {s.duration && <span className="block text-[9px] font-normal text-muted-foreground mt-0.5">{s.duration}</span>}
                                </td>
                                <td className="px-2.5 py-2 text-foreground leading-relaxed align-top whitespace-pre-wrap">{s.visual}</td>
                                <td className="px-2.5 py-2 text-foreground leading-relaxed align-top whitespace-pre-wrap">{s.voiceover}</td>
                                <td className="px-2.5 py-2 text-foreground leading-relaxed align-top whitespace-pre-wrap">{s.subtitle}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              }

              return (
                <div key={key}>
                  <label className="text-xs text-muted-foreground block mb-0.5">{key}</label>
                  <input
                    type="text"
                    value={value}
                    onChange={(e) => handlePropChange(key, e.target.value)}
                    onBlur={() => handlePropBlur(key)}
                    onKeyDown={(e) => { if (e.key === "Enter") handlePropBlur(key); }}
                    className="w-full rounded-md border bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Output (with media preview) */}
      {node.output && (
        <div className="mb-4">
          <h4 className="mb-1 text-xs font-medium text-muted-foreground">Output Preview</h4>
          <div className="rounded-md bg-muted/50 p-2">
            {node.type === "image" && (node.output.startsWith("/") || node.output.startsWith("http")) ? (
              <img src={node.output} className="w-full max-h-[200px] object-contain rounded border bg-black/10 dark:bg-white/5" alt={node.label} />
            ) : node.type === "audio" && (node.output.startsWith("/") || node.output.startsWith("http")) ? (
              <audio src={node.output} controls className="w-full" />
            ) : node.type === "video" && (node.output.startsWith("/") || node.output.startsWith("http")) ? (
              <video src={node.output} controls className="w-full max-h-[200px] rounded border" />
            ) : (
              <p className="text-xs text-foreground whitespace-pre-wrap break-all">{node.output}</p>
            )}
          </div>
          
          {/* Revision request input */}
          <div className="mt-4 pt-4 border-t border-border">
            <h4 className="mb-2 text-xs font-medium text-muted-foreground">Request Revision / Feedback</h4>
            <textarea
              value={revisionComment}
              onChange={(e) => setRevisionComment(e.target.value)}
              placeholder={`Suggest edits for this ${node.type} node (e.g. "make the background brighter", "use a deeper voice")...`}
              className="w-full text-xs p-2 rounded border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary min-h-[60px]"
            />
            <button
              onClick={handleSendRevision}
              disabled={!revisionComment.trim()}
              className="mt-2 w-full inline-flex items-center justify-center gap-1.5 rounded bg-primary py-1.5 text-xs font-semibold text-primary-foreground disabled:opacity-40 hover:bg-primary/90 transition-colors cursor-pointer"
            >
              Send Revision to Agent
            </button>
          </div>
        </div>
      )}

      {/* Error */}
      {node.error && (
        <div className="mb-4">
          <h4 className="mb-1 text-xs font-medium text-red-500">Error</h4>
          <div className="rounded-md bg-red-500/10 p-2">
            <p className="text-xs text-red-600 dark:text-red-400 whitespace-pre-wrap">{node.error}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default InspectorPanel;
