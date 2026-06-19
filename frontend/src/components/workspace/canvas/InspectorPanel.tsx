/**
 * InspectorPanel — right panel showing the selected node's properties and output.
 */

import type { CanvasNode } from "@/components/workspace/canvas/graphModel";

interface InspectorPanelProps {
  node: CanvasNode | null;
}

export function InspectorPanel({ node }: InspectorPanelProps) {
  if (!node) {
    return (
      <div className="w-64 shrink-0 border-l bg-background p-4">
        <p className="text-sm text-muted-foreground">Select a node to inspect its properties</p>
      </div>
    );
  }

  return (
    <div className="w-64 shrink-0 overflow-y-auto border-l bg-background p-4">
      <h3 className="mb-4 text-sm font-semibold text-foreground">Inspector</h3>

      {/* Node info */}
      <div className="mb-4 space-y-2">
        <div>
          <label className="text-xs text-muted-foreground">Label</label>
          <p className="text-sm font-medium text-foreground">{node.label}</p>
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

      {/* Properties */}
      {Object.keys(node.props).length > 0 && (
        <div className="mb-4">
          <h4 className="mb-2 text-xs font-medium text-muted-foreground">Properties</h4>
          <div className="space-y-1.5">
            {Object.entries(node.props).map(([key, value]) => (
              <div key={key}>
                <label className="text-xs text-muted-foreground">{key}</label>
                <p className="text-sm text-foreground">{value}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Output */}
      {node.output && (
        <div className="mb-4">
          <h4 className="mb-1 text-xs font-medium text-muted-foreground">Output</h4>
          <div className="rounded-md bg-muted/50 p-2">
            <p className="text-xs text-foreground whitespace-pre-wrap">{node.output}</p>
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
