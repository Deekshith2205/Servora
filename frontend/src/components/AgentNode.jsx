// [SWARM] "Agent Collaboration Graph": React Flow custom node type.
// Renders exactly the fields the old SwarmGraph's GraphNode button did
// (name, type, status, confidence, duration) plus the agent icon already
// shared with the rest of the app via agentMeta.jsx — no new iconography,
// no new labeling rules invented here.
import { Handle, Position } from "@xyflow/react";
import { agentLabel, AgentIcon, ConfidenceBadge } from "./agentMeta.jsx";

const STATUS_META = {
  idle: { label: "Idle", dotClass: "agent-node-dot-idle" },
  running: { label: "Running", dotClass: "agent-node-dot-running" },
  completed: { label: "Completed", dotClass: "agent-node-dot-completed" },
  escalated: { label: "Escalated", dotClass: "agent-node-dot-escalated" },
  failed: { label: "Failed", dotClass: "agent-node-dot-failed" },
};

function formatDuration(ms) {
  if (ms == null) return null;
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

export default function AgentNode({ data }) {
  const { agentName, agentType, status, confidence, durationMs, active, pending, evidenceCount } = data;

  if (pending) {
    return (
      <div className="agent-node agent-node-pending">
        <Handle type="target" position={Position.Left} />
        <span className="agent-node-pending-dots">
          <span />
          <span />
          <span />
        </span>
      </div>
    );
  }

  const statusMeta = STATUS_META[status] || STATUS_META.idle;
  const duration = formatDuration(durationMs);

  return (
    <div className={`agent-node agent-node-status-${status}${active ? " agent-node-active" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <div className="agent-node-header">
        <AgentIcon agentName={agentName} />
        <div className="agent-node-titles">
          <span className="agent-node-name">{agentLabel(agentName)}</span>
          <span className="agent-node-type">{agentType}</span>
        </div>
      </div>
      <div className="agent-node-status-row">
        <span className={`agent-node-dot ${statusMeta.dotClass}`} />
        <span className="agent-node-status-label">{statusMeta.label}</span>
      </div>
      <div className="agent-node-metrics">
        {confidence != null && <ConfidenceBadge value={confidence} />}
        {duration && <span className="agent-node-duration">{duration}</span>}
      </div>
      {evidenceCount > 0 && <div className="agent-node-evidence">{evidenceCount} evidence item{evidenceCount === 1 ? "" : "s"}</div>}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
