// [SWARM] issue "Agent Collaboration Graph": the mapping layer between
// existing investigation data (GraphNodeOut/GraphEdgeOut from
// GET /api/investigations/{id}, or the equivalent live SSE-built shape
// already assembled in AgentSwarmView.jsx) and React Flow's
// {nodes, edges} shape.
//
// Deliberately reuses, rather than replaces, the exact depth/column
// algorithm the previous hand-drawn SVG graph (issues #81/#88) already
// used to lay out fan-out/fan-in — only the RENDERING technology changes
// here (React Flow instead of hand-drawn SVG connectors), not the
// underlying data or the logic that decides which column a node belongs
// in. No backend change, no new fields: every value read here already
// exists on GraphNodeOut/GraphEdgeOut/InvestigationStepOut.
import { MarkerType } from "@xyflow/react";

const COLUMN_WIDTH = 260;
const ROW_HEIGHT = 150;

const AGENT_TYPE_LABELS = {
  classifier: "Classifier",
  planner: "Planner",
  verification: "Verification",
  escalation: "Escalation",
  memory: "Memory",
  critic: "Critic",
  reconciliation: "Reconciliation",
};

// "Agent type" distinct from "agent name" (agentMeta.jsx's agentLabel(),
// e.g. "Billing Agent") — e.g. type "Specialist" for any *_specialist,
// otherwise a small fixed vocabulary, "Agent" as a last-resort fallback
// for any future agent_name this hasn't been updated for (never throws).
export function agentType(agentName) {
  if (agentName.endsWith("_specialist")) return "Specialist";
  return AGENT_TYPE_LABELS[agentName] || "Agent";
}

// Same fan-out/fan-in depth algorithm AgentSwarmView.jsx's computeLayers()
// already used — step_number order is causal (backend always returns
// `graph.nodes` sorted ascending), so a node's dependencies are always
// already-seen step_numbers when this runs.
function computeDepths(nodes, edges) {
  const parentsOf = {};
  for (const n of nodes) parentsOf[n.step_number] = [];
  for (const e of edges) {
    if (parentsOf[e.to_step]) parentsOf[e.to_step].push(e.from_step);
  }
  const depthOf = {};
  for (const n of nodes) {
    const parents = parentsOf[n.step_number];
    depthOf[n.step_number] = parents.length === 0 ? 0 : 1 + Math.max(...parents.map((p) => depthOf[p] ?? 0));
  }
  return depthOf;
}

// [SWARM] issue #83's status vocabulary, extended with "escalated" (the
// escalation agent's own step reaching that point in the pipeline always
// means the conversation is being handed to a human — a real, existing
// signal, not a new field). "idle"/"running" stay simulated-from-replay-
// timing exactly as before; "completed"/"failed"/"escalated" are real.
function nodeStatus(step, index, revealedCount, total, liveGrowing) {
  if (!liveGrowing) {
    if (index >= revealedCount) return "idle";
    if (index === revealedCount - 1 && revealedCount < total) return "running";
  }
  if (step.agent_name === "escalation") return "escalated";
  return step.status === "failed" ? "failed" : "completed";
}

/**
 * @param graph {{nodes: Array, edges: Array}} — GraphNodeOut/GraphEdgeOut
 *   shape (or the equivalent client-built liveGraph in AgentSwarmView.jsx)
 * @param timeline {Array} — InvestigationStepOut shape (or liveTimeline),
 *   used only for the richer per-edge/per-node details (evidence count)
 *   graph.nodes alone doesn't carry.
 * @param options.revealedCount — replay mode only: how many nodes (in
 *   step_number order) are currently revealed.
 * @param options.liveGrowing — true in live mode: every node in `graph`
 *   has genuinely already arrived; there is no "idle" filler.
 * @param options.activeStep — the step_number currently selected/expanded
 *   elsewhere on the page, so the matching node can highlight.
 * @param options.pendingNext — live mode only: append one dashed "…"
 *   placeholder node/edge after the last real node, since another step
 *   may still be in flight (mirrors the previous implementation's
 *   swarm-node-pending-next).
 */
export function investigationToFlow(graph, timeline, options = {}) {
  const { revealedCount = graph.nodes.length, liveGrowing = false, activeStep = null, pendingNext = false } = options;

  const nodesSrc = graph.nodes;
  const total = nodesSrc.length;
  const depthOf = computeDepths(nodesSrc, graph.edges);

  const byDepth = {};
  for (const n of nodesSrc) {
    const d = depthOf[n.step_number];
    (byDepth[d] ||= []).push(n);
  }

  const timelineByStep = Object.fromEntries((timeline || []).map((s) => [s.step_number, s]));

  const visibleStepNumbers = new Set(
    liveGrowing ? nodesSrc.map((n) => n.step_number) : nodesSrc.slice(0, revealedCount).map((n) => n.step_number)
  );

  const flowNodes = nodesSrc
    .filter((n) => visibleStepNumbers.has(n.step_number))
    .map((n) => {
      const depth = depthOf[n.step_number];
      const columnNodes = byDepth[depth];
      const indexInColumn = columnNodes.findIndex((c) => c.step_number === n.step_number);
      const y = (indexInColumn - (columnNodes.length - 1) / 2) * ROW_HEIGHT;
      const overallIndex = nodesSrc.findIndex((x) => x.step_number === n.step_number);
      const step = timelineByStep[n.step_number] || {};
      return {
        id: String(n.step_number),
        type: "agentNode",
        position: { x: depth * COLUMN_WIDTH, y },
        data: {
          agentName: n.agent_name,
          agentType: agentType(n.agent_name),
          status: nodeStatus(n, overallIndex, revealedCount, total, liveGrowing),
          confidence: n.confidence,
          durationMs: n.duration_ms,
          active: activeStep === n.step_number,
          evidenceCount: (step.evidence || []).length,
        },
      };
    });

  const flowEdges = graph.edges
    .filter((e) => visibleStepNumbers.has(e.from_step) && visibleStepNumbers.has(e.to_step))
    .map((e) => {
      const toStep = timelineByStep[e.to_step];
      const evidenceCount = toStep?.evidence?.length || 0;
      return {
        id: `e${e.from_step}-${e.to_step}`,
        source: String(e.from_step),
        target: String(e.to_step),
        type: "smoothstep",
        animated: true,
        label: evidenceCount > 0 ? `${evidenceCount} evidence` : "handoff",
        markerEnd: { type: MarkerType.ArrowClosed },
      };
    });

  if (pendingNext && flowNodes.length > 0) {
    const last = flowNodes[flowNodes.length - 1];
    flowNodes.push({
      id: "__pending__",
      type: "agentNode",
      position: { x: last.position.x + COLUMN_WIDTH, y: last.position.y },
      data: { agentName: null, agentType: "…", status: "idle", pending: true },
    });
    flowEdges.push({
      id: `e${last.id}-pending`,
      source: last.id,
      target: "__pending__",
      type: "smoothstep",
      animated: false,
      style: { strokeDasharray: "4 4" },
    });
  }

  return { nodes: flowNodes, edges: flowEdges };
}
