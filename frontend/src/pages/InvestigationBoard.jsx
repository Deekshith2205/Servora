import { useEffect, useMemo, useState } from "react";
import {
  fetchAgentPerformanceMetrics,
  fetchInvestigation,
  fetchInvestigations,
} from "../api/client";
import { AgentIcon, ConfidenceBadge, agentLabel } from "../components/agentMeta";
import { ChannelBadge } from "../components/channelMeta";
import EvidenceCard from "../components/explainability/EvidenceCard.jsx";
import ExplainabilityDrawer from "../components/explainability/ExplainabilityDrawer.jsx";
import { dedupeEvidence, flattenEvidence, unstructuredEvidence } from "../utils/investigationEvidence.js";
import "./InvestigationBoard.css";

// [FEATURE] AI Investigation Board & Autonomous Reasoning Timeline.
//
// Honest architecture note (see backend/app/orchestrator.py's own docstring
// for the full version): /api/chat is a single, synchronous request — the
// entire classify -> plan -> specialist -> verify -> (escalate|resolve)
// pipeline runs to completion before the API responds. So a real
// Investigation is only ever fetched already-complete; there is no genuine
// server-push "step 2 of 5 in progress" state to subscribe to without a
// bigger architectural change (SSE/WebSocket streaming from inside
// handle_message). What this page does instead — and is upfront about,
// rather than pretending to be truly live — is replay an already-complete
// investigation's real steps with a staggered reveal animation, so it
// still *feels* like watching the agents work, using entirely real,
// already-persisted data (no placeholder/mock content anywhere below).

const STATUS_LABELS = {
  investigating: "Investigating",
  root_cause_found: "Root Cause Found",
  escalated: "Escalated",
  resolved: "Resolved",
};

const STATUS_CLASS = {
  investigating: "status-investigating",
  root_cause_found: "status-root-cause",
  escalated: "status-escalated",
  resolved: "status-resolved",
};

// -------------------------------------------------------------------------
// A. Investigation Status
// -------------------------------------------------------------------------
function StatusBanner({ status, channelKey }) {
  const label = STATUS_LABELS[status] || status;
  const cls = STATUS_CLASS[status] || "status-investigating";
  return (
    <div className={`ib-status-banner ${cls}`}>
      {channelKey && <ChannelBadge channelKey={channelKey} />}
      <span className="ib-status-dot"></span>
      <span className="ib-status-label">{label}</span>
    </div>
  );
}

// -------------------------------------------------------------------------
// B. Agent Activity Feed — staggered reveal of the SAME real steps as the
// timeline below, framed as an in-progress-feeling feed.
// -------------------------------------------------------------------------
function AgentActivityFeed({ steps, revealedCount }) {
  return (
    <div className="ib-section ib-activity-feed">
      <div className="ib-section-title">Agent Activity Feed</div>
      <div className="ib-feed-list">
        {steps.slice(0, revealedCount).map((step, idx) => {
          const isLatest = idx === revealedCount - 1;
          return (
            <div key={idx} className="ib-feed-item" style={{ animationDelay: `${idx * 60}ms` }}>
              <div className="ib-feed-icon"><AgentIcon agentName={step.agent_name} /></div>
              <div className="ib-feed-body">
                <div className="ib-feed-agent">{agentLabel(step.agent_name)}</div>
                <div className="ib-feed-action">
                  {step.action}
                  {isLatest && revealedCount < steps.length && <span className="ib-feed-dots">...</span>}
                </div>
              </div>
              <div className="ib-feed-duration">{step.duration_ms}ms</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// -------------------------------------------------------------------------
// C. Investigation Timeline — vertical checklist, expandable per step.
// -------------------------------------------------------------------------
function InvestigationChecklistTimeline({ steps, revealedCount }) {
  const [expanded, setExpanded] = useState({});
  const toggle = (idx) => setExpanded((prev) => ({ ...prev, [idx]: !prev[idx] }));

  return (
    <div className="ib-section">
      <div className="ib-section-title">Investigation Timeline</div>
      <div className="ib-checklist">
        {steps.slice(0, revealedCount).map((step, idx) => {
          const isOpen = !!expanded[idx];
          const failed = step.status === "failed";
          return (
            <div key={idx} className="ib-checklist-item" style={{ animationDelay: `${idx * 60}ms` }}>
              <div className={`ib-checklist-mark ${failed ? "mark-failed" : "mark-done"}`}>
                {failed ? "!" : "✓"}
              </div>
              <div className="ib-checklist-content">
                <button className="ib-checklist-header" onClick={() => toggle(idx)} aria-expanded={isOpen}>
                  <span className="ib-checklist-action">{step.action}</span>
                  <span className="ib-checklist-meta">
                    <ConfidenceBadge value={step.confidence} />
                    <span className="ib-checklist-agent">{agentLabel(step.agent_name)}</span>
                    <svg className={`ib-chevron ${isOpen ? "open" : ""}`} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                  </span>
                </button>
                {isOpen && (
                  <div className="ib-checklist-detail">
                    <div className="ib-checklist-timing">{step.duration_ms}ms • step {step.step_number}</div>
                    {step.evidence.length > 0 ? (
                      <ul className="ib-checklist-evidence">
                        {step.evidence.map((e, i) => <li key={i}>{e}</li>)}
                      </ul>
                    ) : (
                      <div className="ib-checklist-no-evidence">No tool evidence recorded for this step.</div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// -------------------------------------------------------------------------
// D. Evidence Panel — [Explainability #118/#124]: clickable evidence
// cards (built from structured `evidence_refs`, one card per real
// order/customer/ticket/KB-article the investigation actually looked at)
// instead of the old plain-text prose list. Clicking a card opens the
// Explainability Drawer for exactly that evidence item.
// -------------------------------------------------------------------------
function EvidencePanel({ timeline, activeEvidenceId, onSelectEvidence, investigationChannel }) {
  const structured = useMemo(() => dedupeEvidence(flattenEvidence(timeline)), [timeline]);
  const prose = useMemo(() => unstructuredEvidence(timeline), [timeline]);

  if (structured.length === 0 && prose.length === 0) {
    return (
      <div className="ib-section">
        <div className="ib-section-title">Evidence</div>
        <p className="ib-empty-note">No tool-derived evidence was recorded for this investigation.</p>
      </div>
    );
  }
  return (
    <div className="ib-section">
      <div className="ib-section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Evidence Collected</span>
        {investigationChannel && <ChannelBadge channelKey={investigationChannel} />}
      </div>
      <div className="ib-evidence-grid">
        {structured.map((item) => (
          <EvidenceCard
            key={item.evidenceId}
            item={item}
            active={item.evidenceId === activeEvidenceId}
            onClick={onSelectEvidence}
          />
        ))}
        {/* A step can record a prose evidence sentence with no matching
            structured ref (see unstructuredEvidence()'s docstring) —
            shown as a plain, honestly non-clickable card rather than
            silently dropped. */}
        {prose.map((item) => (
          <EvidenceCard key={item.key} item={{ evidenceId: item.key, ref: { type: null, label: item.text }, agentName: item.agentName, confidence: null, usedTools: [] }} />
        ))}
      </div>
      <p className="ib-hint">Click any evidence item above to see exactly how it was gathered and how it affected the investigation.</p>
    </div>
  );
}

// -------------------------------------------------------------------------
// E. Root Cause Card
// -------------------------------------------------------------------------
function RootCauseCard({ rootCause, confidence }) {
  if (!rootCause) return null;
  return (
    <div className="ib-section">
      <div className="ib-root-cause-card">
        <div className="ib-root-cause-label">Root Cause</div>
        <p className="ib-root-cause-text">{rootCause}</p>
        {confidence !== null && confidence !== undefined && (
          <div className="ib-root-cause-confidence">
            Confidence: <strong>{Math.round(confidence * 100)}%</strong>
          </div>
        )}
      </div>
    </div>
  );
}

// -------------------------------------------------------------------------
// F. Resolution Recommendation
// -------------------------------------------------------------------------
function ResolutionCard({ resolution, confidence, status }) {
  if (!resolution) return null;
  const label = status === "resolved" ? "Resolution Applied" : "AI Suggested Resolution";
  return (
    <div className="ib-section">
      <div className="ib-resolution-card">
        <div className="ib-resolution-label">{label}</div>
        <p className="ib-resolution-text">{resolution}</p>
        {confidence !== null && confidence !== undefined && (
          <div className="ib-resolution-probability">
            <span>Expected Success Probability</span>
            <div className="ib-probability-bar-track">
              <div className="ib-probability-bar-fill" style={{ width: `${Math.round(confidence * 100)}%` }}></div>
            </div>
            <strong>{Math.round(confidence * 100)}%</strong>
          </div>
        )}
      </div>
    </div>
  );
}

// -------------------------------------------------------------------------
// [CRITIC] issue #112: Critic Review — an independent second opinion on
// the root cause/evidence/resolution above, found by locating the
// timeline step with agent_name === "critic" (there is at most one per
// investigation). Deliberately its own section, not folded into the
// checklist: this is specifically ABOUT the specialist's finding, not
// just another step in the sequence.
// -------------------------------------------------------------------------
function CriticReviewCard({ steps }) {
  const criticStep = steps.find((s) => s.agent_name === "critic");
  if (!criticStep || !criticStep.critic_review) return null;
  const { agrees, confidence, alternative_hypothesis, reasoning } = criticStep.critic_review;

  return (
    <div className="ib-section">
      <div className="ib-section-title">Critic Review — Independent Second Opinion</div>
      <div className={`ib-critic-card ${agrees ? "ib-critic-agrees" : "ib-critic-disagrees"}`}>
        <div className="ib-critic-header">
          <span className={`app-badge ${agrees ? "badge-success" : "badge-danger"}`}>
            {agrees ? "Agrees" : "Disagrees"}
          </span>
          <ConfidenceBadge value={confidence} />
        </div>
        <p className="ib-critic-reasoning">{reasoning}</p>
        {!agrees && alternative_hypothesis && (
          <div className="ib-critic-alternative">
            <div className="ib-critic-alternative-label">Alternative Hypothesis</div>
            <p>{alternative_hypothesis}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// -------------------------------------------------------------------------
// G. Escalation Summary
// -------------------------------------------------------------------------
function EscalationSummary({ status, steps }) {
  if (status !== "escalated") return null;
  const attempted = steps.filter((s) => s.agent_name !== "escalation");
  return (
    <div className="ib-section">
      <div className="ib-section-title">Escalation Summary — What AI Already Attempted</div>
      <ul className="ib-escalation-list">
        {attempted.map((s, i) => (
          <li key={i}>
            <strong>{agentLabel(s.agent_name)}:</strong> {s.action}
          </li>
        ))}
      </ul>
    </div>
  );
}

// -------------------------------------------------------------------------
// Agent Performance Metrics — cross-investigation aggregate (a real GROUP
// BY on the backend, not derived from just the one selected investigation).
// -------------------------------------------------------------------------
function AgentPerformancePanel({ metrics }) {
  if (!metrics || metrics.agents.length === 0) return null;
  return (
    <div className="ib-section">
      <div className="ib-section-title">Agent Performance Metrics</div>
      <div className="ib-metrics-grid">
        {metrics.agents.map((a) => (
          <div key={a.agent_name} className="ib-metric-card">
            <div className="ib-metric-agent">{agentLabel(a.agent_name)}</div>
            <div className="ib-metric-value">{a.avg_duration_ms}ms</div>
            <div className="ib-metric-caption">avg duration • {a.total_steps} run(s)</div>
            {a.avg_confidence !== null && (
              <div className="ib-metric-confidence">avg confidence {Math.round(a.avg_confidence * 100)}%</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// -------------------------------------------------------------------------
// Main page
// -------------------------------------------------------------------------
export default function InvestigationBoard() {
  const [investigations, setInvestigations] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(null);

  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);
  const [revealedCount, setRevealedCount] = useState(0);

  const [metrics, setMetrics] = useState(null);

  // [Explainability #119/#124]: which evidence item (if any) the drawer
  // currently shows — "{step_number}:{index}", or null when closed.
  const [activeEvidenceId, setActiveEvidenceId] = useState(null);
  const allEvidence = useMemo(() => dedupeEvidence(flattenEvidence(detail?.timeline)), [detail]);

  const loadList = () => {
    setListLoading(true);
    setListError(null);
    fetchInvestigations()
      .then((rows) => {
        setInvestigations(rows);
        if (rows.length > 0 && selectedId === null) setSelectedId(rows[0].id);
      })
      .catch((err) => setListError(err.message || "Failed to load investigations"))
      .finally(() => setListLoading(false));
  };

  useEffect(loadList, []);

  useEffect(() => {
    fetchAgentPerformanceMetrics().then(setMetrics).catch(() => setMetrics(null));
  }, [investigations.length]);

  useEffect(() => {
    if (selectedId === null) return;
    setDetailLoading(true);
    setDetailError(null);
    setDetail(null);
    setRevealedCount(0);
    setActiveEvidenceId(null); // [Explainability #124]: don't leave the drawer open on a now-stale investigation
    fetchInvestigation(selectedId)
      .then(setDetail)
      .catch((err) => setDetailError(err.message || "Failed to load investigation"))
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  // Staggered reveal — see the module-level "Honest architecture note"
  // above for why this replays an already-complete investigation rather
  // than subscribing to a genuinely live stream.
  useEffect(() => {
    if (!detail) return;
    setRevealedCount(0);
    const total = detail.timeline.length;
    let i = 0;
    const interval = setInterval(() => {
      i += 1;
      setRevealedCount(i);
      if (i >= total) clearInterval(interval);
    }, 450);
    return () => clearInterval(interval);
  }, [detail]);

  const isFullyRevealed = detail && revealedCount >= detail.timeline.length;

  const listSummary = useMemo(() => {
    if (investigations.length === 0) return null;
    const withConfidence = investigations.filter((i) => i.confidence !== null && i.confidence !== undefined);
    const avgConfidence = withConfidence.length
      ? withConfidence.reduce((sum, i) => sum + i.confidence, 0) / withConfidence.length
      : null;
    const escalated = investigations.filter((i) => i.status === "escalated").length;
    return {
      total: investigations.length,
      avgConfidence,
      escalationRate: Math.round((escalated / investigations.length) * 100),
    };
  }, [investigations]);

  return (
    <div className="ib-page">
      {listSummary && (
        <div className="summary-cards-grid">
          <div className="summary-card">
            <span className="summary-card-title">Total Investigations</span>
            <span className="summary-card-value">{listSummary.total}</span>
            <span className="summary-card-desc">Recorded conversations</span>
          </div>
          <div className="summary-card">
            <span className="summary-card-title">Avg Confidence</span>
            <span className="summary-card-value">
              {listSummary.avgConfidence !== null ? `${Math.round(listSummary.avgConfidence * 100)}%` : "—"}
            </span>
            <span className="summary-card-desc">Across all investigations</span>
          </div>
          <div className="summary-card">
            <span className="summary-card-title">Escalation Rate</span>
            <span className="summary-card-value">{listSummary.escalationRate}%</span>
            <span className="summary-card-desc">Required human handoff</span>
          </div>
          <div className="summary-card">
            <span className="summary-card-title">Agents Tracked</span>
            <span className="summary-card-value">{metrics ? metrics.agents.length : "—"}</span>
            <span className="summary-card-desc">Distinct agents recorded</span>
          </div>
        </div>
      )}

      <div className="ib-layout">
        <div className="ib-list-panel">
          <div className="ib-list-header">Recent Investigations</div>
          {listLoading ? (
            <div className="ib-list-loading">Loading…</div>
          ) : listError ? (
            <div className="app-error-banner" style={{ margin: "0.5rem" }}>
              <span>Unable to load investigations: {listError}</span>
              <button onClick={loadList}>Retry</button>
            </div>
          ) : investigations.length === 0 ? (
            <div className="ib-empty-note" style={{ padding: "1rem" }}>
              No investigations yet — send a message in Customer Chat to create one.
            </div>
          ) : (
            <div className="ib-list-items">
              {investigations.map((inv) => (
                <button
                  key={inv.id}
                  className={`ib-list-item ${inv.id === selectedId ? "active" : ""}`}
                  onClick={() => setSelectedId(inv.id)}
                >
                  <div className="ib-list-item-top">
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <ChannelBadge channelKey={inv.channel} />
                      <span className={`app-badge ${inv.status === "escalated" ? "badge-warning" : "badge-success"}`}>
                        {STATUS_LABELS[inv.status] || inv.status}
                      </span>
                    </div>
                    <ConfidenceBadge value={inv.confidence} />
                  </div>
                  <div className="ib-list-item-cause">{inv.root_cause || "Root cause not yet determined."}</div>
                  <div className="ib-list-item-meta">Ticket #{inv.ticket_id} • Customer #{inv.customer_id}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="ib-detail-panel">
          {detailLoading ? (
            <div className="ib-list-loading">Loading investigation…</div>
          ) : detailError ? (
            <div className="app-error-banner"><span>{detailError}</span></div>
          ) : !detail ? (
            <div className="ib-empty-note" style={{ padding: "2rem" }}>
              Select an investigation from the list to inspect its full reasoning chain.
            </div>
          ) : (
            <>
              <StatusBanner status={isFullyRevealed ? detail.status : "investigating"} channelKey={detail.channel} />
              <AgentActivityFeed steps={detail.timeline} revealedCount={revealedCount} />
              <InvestigationChecklistTimeline steps={detail.timeline} revealedCount={revealedCount} />
              {isFullyRevealed && (
                <>
                  <EvidencePanel
                    timeline={detail.timeline}
                    activeEvidenceId={activeEvidenceId}
                    onSelectEvidence={setActiveEvidenceId}
                    investigationChannel={detail.channel}
                  />
                  <RootCauseCard rootCause={detail.root_cause} confidence={detail.confidence} />
                  <ResolutionCard resolution={detail.resolution} confidence={detail.confidence} status={detail.status} />
                  <CriticReviewCard steps={detail.timeline} />
                  <EscalationSummary status={detail.status} steps={detail.timeline} />
                </>
              )}
            </>
          )}
        </div>
      </div>

      <AgentPerformancePanel metrics={metrics} />

      {/* [Explainability #119/#124] */}
      {activeEvidenceId && detail && (
        <ExplainabilityDrawer
          investigationId={detail.id}
          evidenceId={activeEvidenceId}
          allEvidence={allEvidence}
          investigationChannel={detail.channel}
          onClose={() => setActiveEvidenceId(null)}
          onSelectEvidence={setActiveEvidenceId}
        />
      )}
    </div>
  );
}
