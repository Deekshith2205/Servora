// [SWARM] issue #82: shared expandable agent card — reasoning, evidence,
// tools used, outputs. Used by both the new Agent Swarm view (clicking a
// node) and the Investigation Board's checklist expand panel, so the two
// views show the same depth of detail instead of diverging.
import { useState } from "react";
import { AgentIcon, ConfidenceBadge, agentLabel } from "./agentMeta";
import "./AgentDetailCard.css";

export default function AgentDetailCard({ step, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const failed = step.status === "failed";

  return (
    <div className="adc-card">
      <button className="adc-header" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className={`adc-icon ${failed ? "adc-icon-failed" : ""}`}>
          <AgentIcon agentName={step.agent_name} />
        </span>
        <span className="adc-title">
          <span className="adc-agent">{agentLabel(step.agent_name)}</span>
          <span className="adc-action">{step.action}</span>
        </span>
        <span className="adc-meta">
          <ConfidenceBadge value={step.confidence} />
          <span className="adc-duration">{step.duration_ms}ms</span>
          <svg className={`adc-chevron ${open ? "open" : ""}`} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </span>
      </button>

      {open && (
        <div className="adc-body">
          <div className="adc-section">
            <div className="adc-section-label">Reasoning</div>
            <p className="adc-reasoning">{step.reasoning || step.action}</p>
          </div>

          <div className="adc-section">
            <div className="adc-section-label">Tools Used</div>
            {step.used_tools && step.used_tools.length > 0 ? (
              <div className="adc-chip-row">
                {step.used_tools.map((t, i) => <span key={i} className="adc-chip">{t}</span>)}
              </div>
            ) : (
              <p className="adc-empty">No tools called.</p>
            )}
          </div>

          <div className="adc-section">
            <div className="adc-section-label">Evidence</div>
            {step.evidence && step.evidence.length > 0 ? (
              <ul className="adc-evidence-list">
                {step.evidence.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            ) : (
              <p className="adc-empty">No tool evidence recorded for this step.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
