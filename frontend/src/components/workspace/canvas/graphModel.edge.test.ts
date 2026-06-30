/**
 * Unit tests for canConnect and addEdge — edge connection with validity rules.
 *
 * Tests cover: self-loops, duplicates, missing nodes, cycle detection (DAG invariant),
 * and valid connection scenarios.
 *
 * **Validates: Requirements 3.5, 9.4, 9.5**
 */

import { describe, it, expect } from "vitest";
import {
  canConnect,
  addEdge,
  PipelineState,
  CanvasNode,
  CanvasEdge,
} from "./graphModel";

function makeNode(id: string, x = 0, y = 0): CanvasNode {
  return {
    id,
    type: "text",
    x,
    y,
    label: "Test",
    props: {},
    status: "idle",
    output: null,
    error: null,
  };
}

function makeState(
  nodes: CanvasNode[],
  edges: CanvasEdge[] = []
): PipelineState {
  return {
    nodes,
    edges,
    viewport: { panX: 0, panY: 0, zoom: 1 },
  };
}

describe("canConnect", () => {
  it("returns false when 'from' node does not exist", () => {
    const state = makeState([makeNode("a")]);
    expect(canConnect(state, "missing", "a")).toBe(false);
  });

  it("returns false when 'to' node does not exist", () => {
    const state = makeState([makeNode("a")]);
    expect(canConnect(state, "a", "missing")).toBe(false);
  });

  it("returns false for self-loops", () => {
    const state = makeState([makeNode("a")]);
    expect(canConnect(state, "a", "a")).toBe(false);
  });

  it("returns false for duplicate edges", () => {
    const state = makeState(
      [makeNode("a"), makeNode("b")],
      [{ id: "e1", from: "a", to: "b" }]
    );
    expect(canConnect(state, "a", "b")).toBe(false);
  });

  it("returns true for a valid new connection", () => {
    const state = makeState([makeNode("a"), makeNode("b")]);
    expect(canConnect(state, "a", "b")).toBe(true);
  });

  it("returns false when adding edge would create a direct cycle (A->B, B->A)", () => {
    const state = makeState(
      [makeNode("a"), makeNode("b")],
      [{ id: "e1", from: "a", to: "b" }]
    );
    // B->A would create a cycle: A->B->A
    expect(canConnect(state, "b", "a")).toBe(false);
  });

  it("returns false when adding edge would create an indirect cycle (A->B->C, C->A)", () => {
    const state = makeState(
      [makeNode("a"), makeNode("b"), makeNode("c")],
      [
        { id: "e1", from: "a", to: "b" },
        { id: "e2", from: "b", to: "c" },
      ]
    );
    // C->A would create a cycle: A->B->C->A
    expect(canConnect(state, "c", "a")).toBe(false);
  });

  it("returns true when the reverse edge does not create a cycle in a DAG", () => {
    // A->B, A->C — adding C->B is fine (no cycle)
    const state = makeState(
      [makeNode("a"), makeNode("b"), makeNode("c")],
      [
        { id: "e1", from: "a", to: "b" },
        { id: "e2", from: "a", to: "c" },
      ]
    );
    expect(canConnect(state, "c", "b")).toBe(true);
  });

  it("handles a diamond-shaped DAG without false cycle detection", () => {
    // A->B, A->C, B->D, C->D — adding B->C is fine
    const state = makeState(
      [makeNode("a"), makeNode("b"), makeNode("c"), makeNode("d")],
      [
        { id: "e1", from: "a", to: "b" },
        { id: "e2", from: "a", to: "c" },
        { id: "e3", from: "b", to: "d" },
        { id: "e4", from: "c", to: "d" },
      ]
    );
    expect(canConnect(state, "b", "c")).toBe(true);
  });

  it("detects cycle in diamond with back edge", () => {
    // A->B, A->C, B->D, C->D — adding D->A would create a cycle
    const state = makeState(
      [makeNode("a"), makeNode("b"), makeNode("c"), makeNode("d")],
      [
        { id: "e1", from: "a", to: "b" },
        { id: "e2", from: "a", to: "c" },
        { id: "e3", from: "b", to: "d" },
        { id: "e4", from: "c", to: "d" },
      ]
    );
    expect(canConnect(state, "d", "a")).toBe(false);
  });
});

describe("addEdge", () => {
  it("adds an edge when canConnect returns true", () => {
    const state = makeState([makeNode("a"), makeNode("b")]);
    const result = addEdge(state, "a", "b");
    expect(result.edges).toHaveLength(1);
    expect(result.edges[0].from).toBe("a");
    expect(result.edges[0].to).toBe("b");
    expect(result.edges[0].id).toBeTruthy();
  });

  it("returns state unchanged for self-loop attempt", () => {
    const state = makeState([makeNode("a")]);
    const result = addEdge(state, "a", "a");
    expect(result).toBe(state);
    expect(result.edges).toHaveLength(0);
  });

  it("returns state unchanged for duplicate edge attempt", () => {
    const state = makeState(
      [makeNode("a"), makeNode("b")],
      [{ id: "e1", from: "a", to: "b" }]
    );
    const result = addEdge(state, "a", "b");
    expect(result).toBe(state);
    expect(result.edges).toHaveLength(1);
  });

  it("returns state unchanged for missing node", () => {
    const state = makeState([makeNode("a")]);
    const result = addEdge(state, "a", "nonexistent");
    expect(result).toBe(state);
  });

  it("returns state unchanged for cycle-inducing edge", () => {
    const state = makeState(
      [makeNode("a"), makeNode("b")],
      [{ id: "e1", from: "a", to: "b" }]
    );
    const result = addEdge(state, "b", "a");
    expect(result).toBe(state);
    expect(result.edges).toHaveLength(1);
  });

  it("preserves existing nodes and edges when adding a valid edge", () => {
    const state = makeState(
      [makeNode("a"), makeNode("b"), makeNode("c")],
      [{ id: "e1", from: "a", to: "b" }]
    );
    const result = addEdge(state, "b", "c");
    expect(result.edges).toHaveLength(2);
    expect(result.edges[0]).toEqual({ id: "e1", from: "a", to: "b" });
    expect(result.edges[1].from).toBe("b");
    expect(result.edges[1].to).toBe("c");
    expect(result.nodes).toEqual(state.nodes);
    expect(result.viewport).toEqual(state.viewport);
  });

  it("does not mutate the original state", () => {
    const state = makeState([makeNode("a"), makeNode("b")]);
    const originalEdges = state.edges;
    addEdge(state, "a", "b");
    expect(state.edges).toBe(originalEdges);
    expect(state.edges).toHaveLength(0);
  });
});
