/**
 * NodeLibraryPanel — left panel listing draggable Agent_Node templates.
 * Grouped by category: Agents, Inputs, Outputs.
 */

import type { NodeType } from "@/components/workspace/canvas/graphModel";

interface NodeTemplate {
  type: NodeType;
  label: string;
  description: string;
}

interface NodeCategory {
  name: string;
  nodes: NodeTemplate[];
}

const NODE_CATEGORIES: NodeCategory[] = [
  {
    name: "Agents",
    nodes: [
      { type: "orchestrator", label: "Orchestrator", description: "Coordinates pipeline flow" },
      { type: "text", label: "Text Agent", description: "Generates text content" },
      { type: "image", label: "Image Agent", description: "Generates images" },
      { type: "audio", label: "Audio Agent", description: "Generates audio" },
      { type: "video", label: "Video Agent", description: "Generates video" },
      { type: "critic", label: "Critic", description: "Evaluates output quality" },
    ],
  },
  {
    name: "Inputs",
    nodes: [
      { type: "input", label: "Company Brief", description: "Brand and campaign input" },
    ],
  },
  {
    name: "Outputs",
    nodes: [
      { type: "output", label: "Creative Pack", description: "Final deliverable bundle" },
    ],
  },
];

const TYPE_COLORS: Record<string, string> = {
  orchestrator: "bg-purple-500/10 text-purple-500 border-purple-500/20",
  text: "bg-blue-500/10 text-blue-500 border-blue-500/20",
  image: "bg-green-500/10 text-green-500 border-green-500/20",
  audio: "bg-orange-500/10 text-orange-500 border-orange-500/20",
  video: "bg-red-500/10 text-red-500 border-red-500/20",
  critic: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
  input: "bg-slate-500/10 text-slate-500 border-slate-500/20",
  output: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
};

export function NodeLibraryPanel() {
  const handleDragStart = (e: React.DragEvent, nodeType: NodeType) => {
    e.dataTransfer.setData("application/canvas-node-type", nodeType);
    e.dataTransfer.effectAllowed = "copy";
  };

  return (
    <div className="w-56 shrink-0 overflow-y-auto border-r bg-background p-3">
      <h3 className="mb-3 text-sm font-semibold text-foreground">Node Library</h3>
      {NODE_CATEGORIES.map((category) => (
        <div key={category.name} className="mb-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {category.name}
          </p>
          <div className="space-y-1.5">
            {category.nodes.map((node) => (
              <div
                key={node.type}
                draggable
                onDragStart={(e) => handleDragStart(e, node.type)}
                className={`cursor-grab rounded-md border px-3 py-2 transition-colors hover:shadow-sm active:cursor-grabbing ${TYPE_COLORS[node.type] ?? ""}`}
              >
                <p className="text-xs font-medium">{node.label}</p>
                <p className="text-[10px] opacity-70">{node.description}</p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default NodeLibraryPanel;
