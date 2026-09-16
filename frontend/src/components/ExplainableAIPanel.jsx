// [EXPLAIN] issue #93: shared "Why did Servora recommend this?" panel.
// One component, two display modes — `compact` (a toggle link + popover,
// used inline under a Customer Chat reply) and `full` (a standalone
// section, used in the Staff Dashboard's escalation drawer) — rather than
// two divergent implementations.
//
// Sections here: Confidence Score, Reasoning Summary, Contributing
// Agents, Alternative Decisions, Evidence Explorer, Policy References,
// Decision Tree (#97).
import { useEffect, useState } from "react";
import { fetchExplanation, fetchInvestigationByTicket } from "../api/client";
import { ConfidenceBreakdownBars, ConfidenceGauge } from "./ConfidenceGauge";
import DecisionTree from "./DecisionTree";
import { EvidenceExplorer, PolicyReferenceExplorer } from "./EvidenceExplorer";
import { agentLabel } from "./agentMeta";
import { ChannelBadge } from "./channelMeta";
import "./ExplainableAIPanel.css";

// [EXPLAIN] issue #96: the chosen action rendered visually distinct from
// (and above) the rejected alternatives — `chosen_action` and
// `alternatives_considered` are mutually exclusive by construction on the
// backend (see explanations.py::_chosen_action's docstring), so this
// never risks showing the same action in both places.
function AlternativesSection({ chosenAction, alternatives }) {
  if (!alternatives || alternatives.length === 0) return null;
  return (
    <div className="eap-section">
      <div className="eap-section-label">Alternative Actions Considered</div>
      {chosenAction && (
        <div className="eap-alt-chosen">
          <span className="eap-alt-chosen-badge">Chosen</span>
          <span className="eap-alt-action">{chosenAction}</span>
        </div>
      )}
      <ul className="eap-alternatives-list">
        {alternatives.map((a, i) => (
          <li key={i}>
            <span className="eap-alt-action eap-alt-rejected">{a.action}</span>
            <span className="eap-alt-reason"> — {a.rejected_because}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ContributingAgentsSection({ agents }) {
  if (!agents || agents.length === 0) return null;
  return (
    <div className="eap-section">
      <div className="eap-section-label">Agents Consulted</div>
      <div className="eap-chip-row">
        {agents.map((a) => <span key={a.agent_name} className="eap-chip eap-chip-agent">{agentLabel(a.agent_name)}</span>)}
      </div>
    </div>
  );
}

function PanelBody({ explanation }) {
  return (
    <div className="eap-body">
      <div className="eap-section eap-confidence-section">
        <div className="eap-section-label">Confidence</div>
        <ConfidenceGauge value={explanation.confidence.overall} size={128} />
        <ConfidenceBreakdownBars byAgent={explanation.confidence.by_agent} />
      </div>

      <div className="eap-section eap-source-section">
        <div className="eap-section-label">Source</div>
        <ChannelBadge channelKey={explanation.channel} />
      </div>

      <div className="eap-section">
        <div className="eap-section-label">Decision Rationale</div>
        <p className="eap-rationale">{explanation.decision_rationale}</p>
      </div>

      <ContributingAgentsSection agents={explanation.agents_consulted} />
      <AlternativesSection chosenAction={explanation.chosen_action} alternatives={explanation.alternatives_considered} />
      <DecisionTree chosenAction={explanation.chosen_action} alternatives={explanation.alternatives_considered} status={explanation.status} agentsConsulted={explanation.agents_consulted} />
      <EvidenceExplorer evidenceRefs={explanation.evidence_refs} />
      <PolicyReferenceExplorer policyReferences={explanation.policy_references} />
    </div>
  );
}

export default function ExplainableAIPanel({ investigationId, ticketId, mode = "compact" }) {
  const [explanation, setExplanation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(mode === "full");

  useEffect(() => {
    if (!open || explanation || (!investigationId && !ticketId)) return;
    setLoading(true);
    setError(null);
    const resolveId = investigationId
      ? Promise.resolve(investigationId)
      : fetchInvestigationByTicket(ticketId).then((inv) => inv.id);
    resolveId
      .then((id) => fetchExplanation(id))
      .then(setExplanation)
      .catch((err) => setError(err.message || "Failed to load explanation"))
      .finally(() => setLoading(false));
  }, [open, investigationId, ticketId, explanation]);

  if (!investigationId && !ticketId) return null;

  if (mode === "compact") {
    return (
      <div className="eap-compact">
        <button className="eap-why-link" onClick={() => setOpen((v) => !v)}>
          {open ? "Hide reasoning" : "Why did Servora recommend this?"}
        </button>
        {open && (
          <div className="eap-popover">
            {loading && <div className="eap-loading">Loading explanation…</div>}
            {error && <div className="eap-error">{error}</div>}
            {explanation && <PanelBody explanation={explanation} />}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="eap-full">
      <div className="eap-full-title">Why did Servora recommend this?</div>
      {loading && <div className="eap-loading">Loading explanation…</div>}
      {error && <div className="eap-error">{error}</div>}
      {explanation && <PanelBody explanation={explanation} />}
    </div>
  );
}
