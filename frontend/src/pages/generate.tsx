/**
 * Generate — Creative Agent Pipeline canvas.
 * Embeds the interactive draw.io-style pipeline builder
 * where agents are on the side and generated content appears in the open canvas space.
 *
 * Uses an iframe to load the standalone HTML prototype from /creative-pipeline.html.
 * This approach preserves all interactive behavior (drag-and-drop, zoom, connections)
 * without requiring a full vanilla-JS-to-React conversion yet.
 */

export default function Generate() {
  return (
    <div className="w-full h-full" style={{ minHeight: "calc(100vh - 64px)" }}>
      <iframe
        src="/creative-pipeline.html"
        title="Creative Agent Pipeline"
        className="w-full h-full border-0"
        style={{ minHeight: "calc(100vh - 64px)" }}
        allow="clipboard-write"
      />
    </div>
  );
}
