// [Explainability #119]: the right-side drill-down drawer — opened from
// an EvidenceCard (#118) click on the Investigation Board (#124). Single
// data source: GET /api/investigations/{id}/evidence/{evidenceId} (#123).
import { useEffect, useState } from "react";
import { fetchEvidenceDetail } from "../../api/client";
import { agentLabel, agentType, AgentIcon, ConfidenceBadge } from "../agentMeta.jsx";
import { ChannelBadge } from "../channelMeta.jsx";
import EvidenceTimeline from "./EvidenceTimeline.jsx";
import SourceRecordViewer from "./SourceRecordViewer.jsx";
import ToolExecutionPanel from "./ToolExecutionPanel.jsx";
import ConfidenceBreakdown from "./ConfidenceBreakdown.jsx";
import "./ExplainabilityDrawer.css";

function formatTimestamp(isoString) {
  try {
    return new Date(isoString).toLocaleString([], { hour: "2-digit", minute: "2-digit", month: "short", day: "numeric" });
  } catch {
    return isoString;
  }
}

export default function ExplainabilityDrawer({ investigationId, evidenceId, allEvidence, investigationChannel, onClose, onSelectEvidence }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setDetail(null);
    setError(null);
    setLoading(true);
    fetchEvidenceDetail(investigationId, evidenceId)
      .then(setDetail)
      .catch((err) => setError(err.message || "Failed to load this evidence item"))
      .finally(() => setLoading(false));
  }, [investigationId, evidenceId]);

  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="expl-overlay" onClick={onClose}>
      <div className="expl-drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Evidence details">
        <div className="expl-drawer-header">
          <div>
            <div className="expl-drawer-eyebrow" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span>Evidence Detail</span>
              {investigationChannel && <ChannelBadge channelKey={investigationChannel} />}
            </div>
            <h3 className="expl-drawer-title">{detail ? detail.title : "Loading…"}</h3>
          </div>
          <button className="expl-drawer-close" onClick={onClose} aria-label="Close">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <EvidenceTimeline items={allEvidence} activeEvidenceId={evidenceId} onSelect={onSelectEvidence} />

        <div className="expl-drawer-content">
          {loading && <div className="expl-loading">Loading evidence detail…</div>}
          {error && <div className="expl-error">{error}</div>}

          {detail && (
            <>
              {/* Section 1: Evidence Summary */}
              <div className="expl-section">
                <div className="expl-section-title">Evidence Summary</div>
                <div className="expl-summary-row">
                  <span className="expl-summary-icon"><AgentIcon agentName={detail.agent_name} /></span>
                  <div>
                    <div className="expl-summary-agent">{agentLabel(detail.agent_name)}</div>
                    <div className="expl-summary-type">{agentType(detail.agent_name)} Agent</div>
                  </div>
                </div>
                <div className="expl-summary-meta">
                  <span className="expl-summary-inv-id">Investigation #{detail.investigation_id}</span>
                  <span>{formatTimestamp(detail.timestamp)}</span>
                  <ConfidenceBadge value={detail.confidence} />
                </div>
              </div>

              {/* Section 2: Source Record */}
              <div className="expl-section">
                <div className="expl-section-title">Source Record</div>
                <SourceRecordViewer evidenceRef={detail.evidence_ref} />
              </div>

              {/* Section 3: Tool Execution */}
              <div className="expl-section">
                <div className="expl-section-title">Tool Execution</div>
                <ToolExecutionPanel tools={detail.tools} />
              </div>

              {/* Section 4: Agent Reasoning */}
              <div className="expl-section">
                <div className="expl-section-title">Agent Reasoning</div>
                <p className="expl-reasoning-text">{detail.reasoning}</p>
              </div>

              {/* Section 5: Confidence Breakdown */}
              <div className="expl-section">
                <div className="expl-section-title">Confidence Breakdown</div>
                <ConfidenceBreakdown breakdown={detail.confidence_breakdown} />
              </div>

              {/* Section 6: Investigation Impact */}
              <div className="expl-section expl-impact-section">
                <div className="expl-section-title">Investigation Impact</div>
                <p className="expl-impact-text">{detail.impact}</p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
