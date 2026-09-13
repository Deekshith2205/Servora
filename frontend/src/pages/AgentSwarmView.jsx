import { useEffect, useMemo, useState } from "react";
import { fetchInvestigation, fetchInvestigations } from "../api/client";
import AgentDetailCard from "../components/AgentDetailCard";
import { AgentIcon, ConfidenceBadge, agentLabel } from "../components/agentMeta";
import { subscribeLive } from "../liveInvestigation";
import "./AgentSwarmView.css";

// [SWARM] issue #81: Agent Swarm Network — a node/edge diagram of the
// SAME real, already-persisted investigation data the Investigation Board
// renders as a flat list, laid out as a graph instead. See
// GraphEdgeOut's backend docstring (app/api/schemas.py): today's pipeline
// never fans out, so a left-to-right chain is a correct (not just
// convenient) rendering of the real topology — a direct-Planner
// escalation is genuinely a 2-node graph, not a differently-shaped one.
//
// [SWARM] issue #85: this page now has two real modes, not one replay
// mode pretending to be live:
//   - LIVE: an investigation actually in flight right now (started from
//     Customer Chat, see liveInvestigation.js) — nodes appear as REAL SSE
//     events arrive (issue #79), not a timer. There is no "idle" filler
//     for future steps here because the total step count genuinely isn't
//     known yet on this branch.
//   - REPLAY: browsing an already-complete investigation from the list —
//     still a staggered reveal (same honest framing as before), now with
//     a speed control since it's explicitly a replay, not a pretense of
//     being live.

const LIVE_ID = "__live__";

// [SWARM] issue #83: status vocabulary — see stepStatus()'s callers for
// which parts are real vs. simulated in each mode.
function stepStatus(index, revealedCount, total, node) {
  if (index >= revealedCount) return "idle";
  if (index === revealedCount - 1 && revealedCount < total) return "running";
  return node.status === "failed" ? "failed" : "completed";
}

const STATUS_LABEL = { idle: "Idle", running: "Running", completed: "Completed", failed: "Failed" };

function GraphNode({ node, status, active, onClick }) {
  const label = agentLabel(node.agent_name);
  const clickable = status !== "idle";
  return (
    <button
      className={`swarm-node status-${status} ${active ? "active" : ""}`}
      onClick={() => clickable && onClick(node.step_number)}
      disabled={!clickable}
    >
      <span className="swarm-node-icon"><AgentIcon agentName={node.agent_name} /></span>
      <span className="swarm-node-label">{label}</span>
      <span className="swarm-node-status">
        <span className="swarm-node-status-dot"></span>
        {STATUS_LABEL[status]}
      </span>
      {status !== "idle" && (
        <span className="swarm-node-meta">
          <ConfidenceBadge value={node.confidence} />
          <span className="swarm-node-duration">{node.duration_ms}ms</span>
        </span>
      )}
    </button>
  );
}

// [SWARM] issue #88: layered layout so genuine parallel investigation
// (two-plus specialists depending on the SAME planner step, and a
// reconciliation step depending on all of them) actually reads as
// fan-out/fan-in — not a flat left-to-right row pretending every step is
// a simple chain. `depends_on` (from the real graph.edges, or from a live
// event — see orchestrator.py's stream payload) determines each node's
// column: depth 0 = no dependencies, depth N = one more than the deepest
// parent. Nodes at the same depth render as a vertical stack within one
// column.
//
// Documented assumption, true for everything this orchestrator can
// currently produce (see _reconcile_specialist_responses()'s fan-out/
// fan-in shape): every edge connects ADJACENT columns — a node's parents
// are never more than one depth shallower. If a future change ever
// produced a dependency that skips a column, this renderer would still
// place both nodes correctly by depth, it just wouldn't draw that
// specific long-distance connector.
function computeLayers(nodes, edges) {
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
  const maxDepth = nodes.length === 0 ? -1 : Math.max(...nodes.map((n) => depthOf[n.step_number]));
  const layers = Array.from({ length: maxDepth + 1 }, () => []);
  for (const n of nodes) layers[depthOf[n.step_number]].push(n);
  return { layers, parentsOf };
}

function ConnectorSVG({ fromLayer, toLayer, parentsOf, flowing }) {
  const fromIndexOf = Object.fromEntries(fromLayer.map((n, i) => [n.step_number, i]));
  const lines = toLayer.flatMap((toNode, toIdx) =>
    (parentsOf[toNode.step_number] || [])
      .filter((p) => p in fromIndexOf)
      .map((p) => ({
        y1: ((fromIndexOf[p] + 0.5) / fromLayer.length) * 100,
        y2: ((toIdx + 0.5) / toLayer.length) * 100,
        key: `${p}-${toNode.step_number}`,
      }))
  );
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="swarm-connector-svg">
      {lines.map((l) => (
        <path key={l.key} d={`M0,${l.y1} C50,${l.y1} 50,${l.y2} 100,${l.y2}`} className={`swarm-connector-path ${flowing ? "flowing" : ""}`} />
      ))}
    </svg>
  );
}

function SwarmGraph({ graph, revealedCount, activeStep, onSelectStep, liveGrowing }) {
  const nodes = graph.nodes;
  const total = nodes.length;
  const visibleNodes = liveGrowing ? nodes : nodes.filter((_, i) => i < revealedCount);
  const { layers, parentsOf } = useMemo(() => computeLayers(nodes, graph.edges), [nodes, graph.edges]);
  // Only render columns/nodes that are currently "visible" (revealed in
  // replay mode, or arrived in live mode) — filter each layer down.
  const visibleStepNumbers = new Set(visibleNodes.map((n) => n.step_number));
  const visibleLayers = layers.map((layer) => layer.filter((n) => visibleStepNumbers.has(n.step_number))).filter((l) => l.length > 0);

  return (
    <div className="swarm-columns">
      {visibleLayers.map((layer, colIdx) => (
        <div className="swarm-column-group" key={colIdx}>
          {colIdx > 0 && (
            <div className="swarm-connector">
              <ConnectorSVG fromLayer={visibleLayers[colIdx - 1]} toLayer={layer} parentsOf={parentsOf} flowing />
            </div>
          )}
          <div className={`swarm-column ${layer.length > 1 ? "swarm-column-parallel" : ""}`}>
            {layer.length > 1 && <div className="swarm-parallel-badge">PARALLEL</div>}
            {layer.map((node) => {
              const i = nodes.findIndex((n) => n.step_number === node.step_number);
              const status = liveGrowing ? (node.status === "failed" ? "failed" : "completed") : stepStatus(i, revealedCount, total, node);
              return <GraphNode key={node.step_number} node={node} status={status} active={activeStep === node.step_number} onClick={onSelectStep} />;
            })}
          </div>
        </div>
      ))}
      {liveGrowing && (
        <div className="swarm-column-group">
          <div className="swarm-connector"><div className="swarm-connector-idle-line"></div></div>
          <div className="swarm-column">
            <div className="swarm-node status-idle swarm-node-pending-next">
              <span className="swarm-node-label">…</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------------------
// [SWARM] issue #84: Swarm Timeline — a horizontal, Gantt-style strip
// distinct from the network graph above (topology) and the Investigation
// Board's vertical checklist (detail-oriented): this one reads as "order
// and relative duration of execution" at a glance. Segment width is
// proportional to each step's REAL duration_ms, not a fixed placeholder.
// -------------------------------------------------------------------------
function SwarmTimelineStrip({ timeline, revealedCount, activeStep, onSelectStep, liveGrowing }) {
  const total = timeline.length;
  const maxDuration = Math.max(1, ...timeline.map((s) => s.duration_ms));
  return (
    <div className="swarm-timeline-strip">
      {timeline.map((step, i) => {
        if (!liveGrowing && i >= revealedCount) return null;
        const status = liveGrowing ? (step.status === "failed" ? "failed" : "completed") : stepStatus(i, revealedCount, total, step);
        const widthPct = Math.max(6, Math.round((step.duration_ms / maxDuration) * 100));
        return (
          <button
            key={step.step_number}
            className={`swarm-strip-segment status-${status} ${activeStep === step.step_number ? "active" : ""}`}
            style={{ flexGrow: widthPct }}
            onClick={() => onSelectStep(step.step_number)}
            title={`${agentLabel(step.agent_name)} — ${step.duration_ms}ms`}
          >
            <AgentIcon agentName={step.agent_name} />
            <span className="swarm-strip-label">{agentLabel(step.agent_name)}</span>
          </button>
        );
      })}
    </div>
  );
}

const SPEED_OPTIONS = [
  { label: "0.5x", intervalMs: 900 },
  { label: "1x", intervalMs: 500 },
  { label: "2x", intervalMs: 250 },
  { label: "Instant", intervalMs: 0 },
];

export default function AgentSwarmView() {
  const [investigations, setInvestigations] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [revealedCount, setRevealedCount] = useState(0);
  const [activeStep, setActiveStep] = useState(null);
  const [speedIndex, setSpeedIndex] = useState(1); // default 1x

  // [SWARM] issue #85: the one investigation currently streaming live, if any.
  const [liveState, setLiveState] = useState(null);

  useEffect(() => subscribeLive(setLiveState), []);

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

  useEffect(loadList, []); // eslint-disable-line react-hooks/exhaustive-deps

  // A live stream is active (either just started, or already in progress
  // when this component mounted — see subscribeLive's "push current value
  // immediately" fix in liveInvestigation.js) — jump straight to it, the
  // whole point of "live" mode is watching it happen.
  useEffect(() => {
    if (liveState && !liveState.done) {
      setSelectedId(LIVE_ID);
    }
  }, [liveState?.streamKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // The live investigation finished — fetch the real, now-persisted
  // record and hand off from "live" to a normal (fully revealed, no
  // re-stagger) detail view.
  useEffect(() => {
    if (!liveState?.done) return;
    const { investigation_id } = liveState.done;
    fetchInvestigation(investigation_id).then((full) => {
      setDetail(full);
      setRevealedCount(full.graph.nodes.length);
      setSelectedId(full.id);
      loadList();
    });
  }, [liveState?.done]); // eslint-disable-line react-hooks/exhaustive-deps

  const isLive = selectedId === LIVE_ID;

  useEffect(() => {
    if (selectedId === null || isLive) return;
    setDetailLoading(true);
    setDetail(null);
    setActiveStep(null);
    fetchInvestigation(selectedId)
      .then(setDetail)
      .finally(() => setDetailLoading(false));
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Staggered reveal for REPLAY mode only — real live mode (above) needs
  // no timer at all, since revealedCount there is just "however many real
  // SSE events have arrived."
  useEffect(() => {
    if (!detail || isLive) return;
    const intervalMs = SPEED_OPTIONS[speedIndex].intervalMs;
    const total = detail.graph.nodes.length;
    if (intervalMs === 0) {
      setRevealedCount(total);
      return;
    }
    setRevealedCount(0);
    let i = 0;
    const interval = setInterval(() => {
      i += 1;
      setRevealedCount(i);
      if (i >= total) clearInterval(interval);
    }, intervalMs);
    return () => clearInterval(interval);
  }, [detail, speedIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  // Synthetic "graph"/"timeline" for live mode, built directly from real
  // SSE step events — no fetch, no fake timing.
  const liveGraph = useMemo(() => {
    if (!liveState) return null;
    const nodes = liveState.steps.map((s) => ({
      step_number: s.step_number, agent_name: s.agent_name, status: s.status,
      confidence: s.confidence, duration_ms: s.duration_ms,
    }));
    // [SWARM] issue #88: real dependency info from each live event
    // (orchestrator.py::_record() publishes it — see that function) —
    // NOT assumed to be a flat chain, so a genuine parallel fan-out shows
    // up live, not just on replay.
    const edges = liveState.steps.flatMap((s) => (s.depends_on || []).map((from) => ({ from_step: from, to_step: s.step_number })));
    return { nodes, edges };
  }, [liveState]);

  const liveTimeline = useMemo(() => {
    if (!liveState) return [];
    return liveState.steps.map((s) => ({
      step_number: s.step_number, agent_name: s.agent_name, action: s.action, status: s.status,
      confidence: s.confidence, duration_ms: s.duration_ms, reasoning: null, evidence: [], evidence_refs: [], used_tools: [],
    }));
  }, [liveState]);

  const activeStepData = useMemo(() => {
    const timeline = isLive ? liveTimeline : detail?.timeline;
    if (!timeline || activeStep === null) return null;
    return timeline.find((s) => s.step_number === activeStep) || null;
  }, [isLive, liveTimeline, detail, activeStep]);

  const showingLiveEntry = liveState && !liveState.done;

  return (
    <div className="swarm-page">
      <div className="swarm-layout">
        <div className="swarm-list-panel">
          <div className="swarm-list-header">Recent Investigations</div>
          {showingLiveEntry && (
            <button className={`swarm-list-item swarm-list-item-live ${isLive ? "active" : ""}`} onClick={() => setSelectedId(LIVE_ID)}>
              <span className="app-badge badge-live">
                <span className="swarm-live-dot"></span> LIVE
              </span>
              <span className="swarm-list-item-cause">Investigation in progress — {liveState.steps.length} step(s) so far…</span>
            </button>
          )}
          {listLoading ? (
            <div className="swarm-list-loading">Loading…</div>
          ) : listError ? (
            <div className="app-error-banner" style={{ margin: "0.5rem" }}>
              <span>Unable to load investigations: {listError}</span>
              <button onClick={loadList}>Retry</button>
            </div>
          ) : investigations.length === 0 && !showingLiveEntry ? (
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
          {isLive ? (
            <>
              <div className="swarm-graph-card">
                <div className="swarm-mode-banner swarm-mode-live">
                  <span className="swarm-live-dot"></span> LIVE — watching this investigation happen in real time
                </div>
                <div className="swarm-section-title">Agent Network</div>
                {liveGraph.nodes.length === 0 ? (
                  <p className="swarm-hint">Waiting for the first agent to respond…</p>
                ) : (
                  <SwarmGraph graph={liveGraph} activeStep={activeStep} onSelectStep={setActiveStep} liveGrowing />
                )}
              </div>
              {liveGraph.nodes.length > 0 && (
                <div className="swarm-graph-card">
                  <div className="swarm-section-title">Swarm Timeline</div>
                  <SwarmTimelineStrip timeline={liveTimeline} activeStep={activeStep} onSelectStep={setActiveStep} liveGrowing />
                </div>
              )}
              {activeStepData && (
                <div className="swarm-selected-card">
                  <AgentDetailCard step={activeStepData} defaultOpen />
                </div>
              )}
            </>
          ) : detailLoading || !detail ? (
            <div className="swarm-empty-note">{detailLoading ? "Loading investigation…" : "Select an investigation."}</div>
          ) : (
            <>
              <div className="swarm-graph-card">
                <div className="swarm-mode-banner swarm-mode-replay">
                  <span>REPLAY</span>
                  <div className="swarm-speed-control">
                    {SPEED_OPTIONS.map((opt, i) => (
                      <button
                        key={opt.label}
                        className={`swarm-speed-btn ${speedIndex === i ? "active" : ""}`}
                        onClick={() => setSpeedIndex(i)}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="swarm-section-title">Agent Network</div>
                <SwarmGraph
                  graph={detail.graph}
                  revealedCount={revealedCount}
                  activeStep={activeStep}
                  onSelectStep={setActiveStep}
                />
                <p className="swarm-hint">Click any agent above to inspect its reasoning, evidence, and tools.</p>
              </div>

              <div className="swarm-graph-card">
                <div className="swarm-section-title">Swarm Timeline</div>
                <SwarmTimelineStrip
                  timeline={detail.timeline}
                  revealedCount={revealedCount}
                  activeStep={activeStep}
                  onSelectStep={setActiveStep}
                />
                <p className="swarm-hint">Segment width reflects real execution duration.</p>
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
