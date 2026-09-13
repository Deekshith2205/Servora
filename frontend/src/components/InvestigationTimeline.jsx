import { useState } from "react";
import { AgentIcon, agentLabel } from "./agentMeta";
import "./InvestigationTimeline.css";

// [EXPLAIN] issue #93: this used to have its own local getAgentLabel/
// getAgentIcon that matched against the literal string "specialist" —
// which never equals a real agent_name like "billing_specialist", so
// every specialist step silently fell through to the generic fallback
// icon/label. Now shares agentMeta.jsx with InvestigationBoard.jsx and
// the Explainable AI Panel, which already handled the "*_specialist"
// suffix correctly.

export default function InvestigationTimeline({ trace }) {
  const [expandedSteps, setExpandedSteps] = useState({});

  if (!trace || trace.length === 0) {
    return (
      <div className="investigation-panel-empty">
        <p>Investigation history unavailable.</p>
      </div>
    );
  }

  const toggleStep = (idx) => {
    setExpandedSteps(prev => ({
      ...prev,
      [idx]: !prev[idx]
    }));
  };

  return (
    <div className="investigation-timeline-wrapper">
      <div className="investigation-timeline-title">Investigation timeline</div>
      <div className="investigation-timeline">
        {trace.map((step, idx) => {
          const isExpanded = !!expandedSteps[idx];
          const isLast = idx === trace.length - 1;
          const label = agentLabel(step.agent);

          return (
            <div key={idx} className="timeline-node">
              {!isLast && <div className="timeline-connector"></div>}
              <div className="timeline-icon">
                <AgentIcon agentName={step.agent} />
              </div>
              <div className="timeline-content">
                <button
                  className="timeline-header"
                  onClick={() => toggleStep(idx)}
                  aria-expanded={isExpanded}
                  aria-controls={`step-content-${idx}`}
                >
                  <div className="timeline-agent">
                    {label}
                  </div>
                  <div className="timeline-status">
                    Completed
                    <svg 
                      className={`timeline-chevron ${isExpanded ? 'expanded' : ''}`}
                      width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                    >
                      <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                  </div>
                </button>
                {isExpanded && (
                  <div id={`step-content-${idx}`} className="timeline-output">
                    {step.root_cause && (
                      <div style={{
                        marginBottom: '0.75rem', 
                        padding: '0.5rem 0.75rem', 
                        background: 'var(--app-surface)', 
                        borderRadius: '4px', 
                        borderLeft: '3px solid var(--app-warning)',
                        fontSize: '0.85rem'
                      }}>
                        <strong style={{color: 'var(--app-warning-text)'}}>Root Cause: </strong> 
                        {step.root_cause}
                      </div>
                    )}
                    {step.resolution && (
                      <div style={{
                        marginBottom: '0.75rem', 
                        padding: '0.5rem 0.75rem', 
                        background: 'var(--app-surface)', 
                        borderRadius: '4px', 
                        borderLeft: '3px solid var(--app-success)',
                        fontSize: '0.85rem'
                      }}>
                        <strong style={{color: 'var(--app-success-text)'}}>Resolution: </strong> 
                        {step.resolution}
                      </div>
                    )}
                    {step.output || step.reply}
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
