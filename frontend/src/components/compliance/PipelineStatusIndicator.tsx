import type { NodeStatus } from "@/services/complianceApi";

interface PipelineStatusIndicatorProps {
  nodeStatuses: NodeStatus[];
  currentNode: string | null;
  isStreaming: boolean;
  mediaType: string;
}

/** Material Symbols icon name for each pipeline node */
const NODE_ICONS: Record<string, string> = {
  router: "alt_route",
  text_check: "spellcheck",
  image_check: "image_search",
  video_check: "movie_filter",
  transcribe: "mic",
  parse_violations: "rule",
  extract_clips: "content_cut",
  generate_remediation: "auto_fix_high",
  upload_remediated_asset: "cloud_upload",
};

/** Human-readable labels for each pipeline node */
const NODE_LABELS: Record<string, string> = {
  router: "Router",
  text_check: "Text Check",
  image_check: "Image Check",
  video_check: "Video Check",
  transcribe: "Transcribe",
  parse_violations: "Parse Violations",
  extract_clips: "Extract Clips",
  generate_remediation: "Generate Fix",
  upload_remediated_asset: "Upload Asset",
};

/** Pipeline paths by media type */
const PIPELINE_PATHS: Record<string, string[]> = {
  video: ["generate_remediation", "upload_remediated_asset"],
  image: ["generate_remediation", "upload_remediated_asset"],
  audio: ["generate_remediation", "upload_remediated_asset"],
  text: ["generate_remediation"],
};

type NodeState = "completed" | "active" | "pending";

function getNodeState(
  nodeName: string,
  nodeStatuses: NodeStatus[],
  currentNode: string | null
): NodeState {
  const completedNodes = nodeStatuses
    .filter((ns) => ns.status === "completed")
    .map((ns) => ns.node);

  if (completedNodes.includes(nodeName)) return "completed";
  if (nodeName === currentNode) return "active";
  return "pending";
}

function getNodeStyles(state: NodeState): string {
  switch (state) {
    case "completed":
      return "bg-emerald-glow text-white";
    case "active":
      return "bg-aurora-purple text-white animate-pulse";
    case "pending":
      return "bg-surface-container-high text-text-muted";
  }
}

function getConnectorStyles(state: NodeState): string {
  switch (state) {
    case "completed":
      return "bg-emerald-glow";
    case "active":
      return "bg-aurora-purple";
    case "pending":
      return "bg-surface-container-high";
  }
}

export function PipelineStatusIndicator({
  nodeStatuses,
  currentNode,
  isStreaming,
  mediaType,
}: PipelineStatusIndicatorProps) {
  // Determine which pipeline path to display based on media type
  const normalizedType = mediaType.split("/")[0] || "text";
  const pipelineNodes = PIPELINE_PATHS[normalizedType] ?? PIPELINE_PATHS.text;

  // Find the current node's description for display
  const currentNodeStatus = nodeStatuses.find((ns) => ns.node === currentNode);
  const currentDescription = currentNodeStatus?.description ?? null;

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Pipeline node sequence */}
      <div className="flex items-center gap-0">
        {pipelineNodes.map((nodeName, index) => {
          const state = getNodeState(nodeName, nodeStatuses, currentNode);
          const icon = NODE_ICONS[nodeName] ?? "circle";
          const label = NODE_LABELS[nodeName] ?? nodeName;

          // Determine connector state (between previous node and this one)
          const showConnector = index > 0;
          const connectorState = state === "completed" ? "completed" : state === "active" ? "active" : "pending";

          return (
            <div key={nodeName} className="flex items-center">
              {/* Connector line */}
              {showConnector && (
                <div
                  className={`h-0.5 w-6 sm:w-10 ${getConnectorStyles(connectorState)} transition-colors duration-300`}
                />
              )}

              {/* Node */}
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors duration-300 ${getNodeStyles(state)}`}
                  title={label}
                >
                  <span
                    className="material-symbols-outlined text-[20px]"
                    style={{ fontVariationSettings: "'FILL' 0" }}
                  >
                    {icon}
                  </span>
                </div>
                <span className="text-code-xs font-code-xs text-text-muted text-center whitespace-nowrap max-w-[60px] truncate">
                  {label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Current node description */}
      {isStreaming && currentDescription && (
        <p className="text-body-md font-body-md text-text-muted text-center animate-pulse">
          {currentDescription}
        </p>
      )}
    </div>
  );
}
