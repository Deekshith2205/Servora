// [EXPLAIN] issue #93: shared agent label/icon/confidence-tier helpers,
// extracted out of InvestigationBoard.jsx so every view that needs to
// render "which agent, what confidence" (the Investigation Board, the new
// Agent Swarm view, the new Explainable AI Panel, and the customer-chat
// trace) uses the exact same mapping — no divergent copies.
//
// Real bug fixed while extracting this: InvestigationTimeline.jsx (the
// customer-chat trace view) previously matched agent labels/icons against
// the literal string "specialist", which never equals a real agent_name
// like "billing_specialist" — every specialist step silently fell through
// to the generic fallback. This module's `agentLabel`/`AgentIcon` handle
// any "*_specialist" suffix correctly, matching what InvestigationBoard.jsx
// already got right.

const AGENT_LABELS = {
  classifier: "Classifier Agent",
  planner: "Planner Agent",
  verification: "Verification Agent",
  escalation: "Escalation Agent",
  memory: "Memory Agent",
};

export function agentLabel(agentName) {
  if (!agentName) return "Unknown Agent";
  if (AGENT_LABELS[agentName]) return AGENT_LABELS[agentName];
  if (agentName.endsWith("_specialist")) {
    const kind = agentName.replace("_specialist", "");
    return `${kind.charAt(0).toUpperCase()}${kind.slice(1)} Agent`;
  }
  return agentName.charAt(0).toUpperCase() + agentName.slice(1);
}

export function AgentIcon({ agentName }) {
  const common = { width: 16, height: 16, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round" };
  if (agentName === "classifier") {
    return <svg {...common}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>;
  }
  if (agentName === "planner") {
    return <svg {...common}><circle cx="12" cy="5" r="3"></circle><line x1="12" y1="22" x2="12" y2="8"></line><path d="M5 12H2a10 10 0 0 0 20 0h-3"></path></svg>;
  }
  if (agentName === "verification") {
    return <svg {...common}><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>;
  }
  if (agentName === "escalation") {
    return <svg {...common}><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>;
  }
  if (agentName === "memory") {
    return <svg {...common}><path d="M12 2a4 4 0 0 0-4 4v1a3 3 0 0 0-2 2.83V12a3 3 0 0 0 1 2.24V16a4 4 0 0 0 4 4h2a4 4 0 0 0 4-4v-1.76A3 3 0 0 0 18 12v-2.17A3 3 0 0 0 16 7V6a4 4 0 0 0-4-4z"></path></svg>;
  }
  // any *_specialist — wrench
  return <svg {...common}><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>;
}

// Same thresholds InvestigationBoard.jsx's ConfidenceBadge already
// established (>=80% high, >=60% medium, else low) — reused, not
// reinvented, so a gauge/bar/badge never disagrees about what "high"
// confidence means for the same value.
export function confidenceTier(value) {
  if (value === null || value === undefined) return null;
  const pct = Math.round(value * 100);
  if (pct >= 80) return "high";
  if (pct >= 60) return "medium";
  return "low";
}

export function ConfidenceBadge({ value }) {
  const tier = confidenceTier(value);
  if (tier === null) return null;
  return <span className={`confidence-badge confidence-${tier}`}>{Math.round(value * 100)}%</span>;
}
