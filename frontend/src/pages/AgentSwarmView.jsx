import { useEffect, useMemo, useState } from "react";
import { fetchInvestigation, fetchInvestigations } from "../api/client";
import AgentDetailCard from "../components/AgentDetailCard";
import { AgentIcon, ConfidenceBadge, agentLabel } from "../components/agentMeta";
import "./AgentSwarmView.css";

// [SWARM] issue #81: Agent Swarm Network — a node/edge diagram of the
// SAME real, already-persisted investigation data the Investigation Board
// renders as a flat list, laid out as a graph instead. See
// GraphEdgeOut's backend docstring (app/api/schemas.py): today's pipeline
// never fans out, so a left-to-right chain is a correct (not just
// convenient) rendering of the real topology — a direct-Planner
// escalation is genuinely a 2-node graph, not a differently-shaped one.
//
// Same honest framing as InvestigationBoard.jsx's own "Honest architecture
// note": /api/chat is fully synchronous, so this replays an already-
// complete investigation with a staggered reveal rather than pretending
// to subscribe to a truly live stream (see issue #79 for that follow-up).

function GraphNode({ node, revealed, active, onClick }) {
  const label = agentLabel(node.agent_name);
  const failed = node.status === "failed";
  return (
    <button
      className={`swarm-node ${revealed ? "revealed" : "pending"} ${failed ? "failed" : ""} ${active ? "active" : ""}`}
      onClick={() => revealed && onClick(node.step_number)}
      disabled={!revealed}
    >
      <span className="swarm-node-icon"><AgentIcon agentName={node.agent_name} /></span>
      <span className="swarm-node-label">{label}</span>
      {revealed && <ConfidenceBadge value={node.confidence} />}
      {revealed && <span className="swarm-node-duration">{node.duration_ms}ms</span>}
    </button>
  );
}

function SwarmGraph({ graph, revealedCount, activeStep, onSelectStep }) {
  const nodes = graph.nodes;
  return (
    <div className="swarm-graph">
      {nodes.map((node, i) => (
        <div className="swarm-graph-item" key={node.step_number}>
          <GraphNode
            node={node}
            revealed={i < revealedCount}
            active={activeStep === node.step_number}
            onClick={onSelectStep}
          />
          {i < nodes.length - 1 && (
            <div className={`swarm-edge ${i < revealedCount - 1 ? "flowing" : "idle"}`}>
              <svg viewBox="0 0 60 12" preserveAspectRatio="none">
                <line x1="0" y1="6" x2="60" y2="6" className="swarm-edge-line" />
                {i < revealedCount - 1 && <line x1="0" y1="6" x2="60" y2="6" className="swarm-edge-pulse" />}
              </svg>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function AgentSwarmView() {
  const [investigations, setInvestigations] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [revealedCount, setRevealedCount] = useState(0);
  const [activeStep, setActiveStep] = useState(null);

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
    if (selectedId === null) return;
    setDetailLoading(true);
    setDetail(null);
    setActiveStep(null);
    fetchInvestigation(selectedId)
      .then(setDetail)
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  // Staggered reveal — same honest "replay, not truly live" framing as
  // InvestigationBoard.jsx (see issue #79 for genuine live streaming).
  useEffect(() => {
    if (!detail) return;
    setRevealedCount(0);
    const total = detail.graph.nodes.length;
    let i = 0;
    const interval = setInterval(() => {
      i += 1;
      setRevealedCount(i);
      if (i >= total) clearInterval(interval);
    }, 500);
    return () => clearInterval(interval);
  }, [detail]);

  const activeStepData = useMemo(() => {
    if (!detail || activeStep === null) return null;
    return detail.timeline.find((s) => s.step_number === activeStep) || null;
  }, [detail, activeStep]);

  return (
    <div className="swarm-page">
      <div className="swarm-layout">
        <div className="swarm-list-panel">
          <div className="swarm-list-header">Recent Investigations</div>
          {listLoading ? (
            <div className="swarm-list-loading">Loading…</div>
          ) : listError ? (
            <div className="app-error-banner" style={{ margin: "0.5rem" }}>
              <span>Unable to load investigations: {listError}</span>
              <button onClick={loadList}>Retry</button>
            </div>
          ) : investigations.length === 0 ? (
            <div className="swarm-empty-note">No investigations yet — send a message in Customer Chat first.</div>
          ) : (
            <div className="swarm-list-items">
              {investigations.map((inv) => (
                <button
                  key={inv.id}
                  className={`swarm-list-item ${inv.id === selectedId ? "active" : ""}`}
                  onClick={() => setSelectedId(inv.id)}
                >
                  <span className={`app-badge ${inv.status === "escalated" ? "badge-warning" : "badge-success"}`}>
                    {inv.status}
                  </span>
                  <span className="swarm-list-item-cause">{inv.root_cause || "Root cause not yet determined."}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="swarm-detail-panel">
          {detailLoading || !detail ? (
            <div className="swarm-empty-note">{detailLoading ? "Loading investigation…" : "Select an investigation."}</div>
          ) : (
            <>
              <div className="swarm-graph-card">
                <div className="swarm-section-title">Agent Network</div>
                <SwarmGraph
                  graph={detail.graph}
                  revealedCount={revealedCount}
                  activeStep={activeStep}
                  onSelectStep={setActiveStep}
                />
                <p className="swarm-hint">Click any agent above to inspect its reasoning, evidence, and tools.</p>
              </div>

              {activeStepData && (
                <div className="swarm-selected-card">
                  <AgentDetailCard step={activeStepData} defaultOpen />
                </div>
              )}

              <div className="swarm-section-title">All Agents in This Investigation</div>
              <div className="swarm-card-list">
                {detail.timeline.map((step) => (
                  <AgentDetailCard key={step.step_number} step={step} />
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
