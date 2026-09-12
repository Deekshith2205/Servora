import { useState } from "react";
import "./InvestigationTimeline.css";

const getAgentLabel = (agent) => {
  const normalized = agent.toLowerCase();
  if (normalized === "classifier") return "Classifier";
  if (normalized === "planner") return "Planner";
  if (normalized === "specialist") return "Specialist";
  if (normalized === "verification") return "Verification";
  if (normalized === "escalation") return "Human Handoff";
  // Fallback to title case for unknown agents
  return agent.charAt(0).toUpperCase() + agent.slice(1);
};

const getAgentIcon = (agent) => {
  const normalized = agent.toLowerCase();
  if (normalized === "classifier") {
    // Spark icon
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
      </svg>
    );
  }
  if (normalized === "planner") {
    // Route/map icon
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="5" r="3"></circle>
        <line x1="12" y1="22" x2="12" y2="8"></line>
        <path d="M5 12H2a10 10 0 0 0 20 0h-3"></path>
      </svg>
    );
  }
  if (normalized === "specialist") {
    // Tool/wrench icon
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
      </svg>
    );
  }
  if (normalized === "verification") {
    // Check circle icon
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
        <polyline points="22 4 12 14.01 9 11.01"></polyline>
      </svg>
    );
  }
  if (normalized === "escalation") {
    // Handoff icon (user/hand)
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="16" x2="12" y2="12"></line>
        <line x1="12" y1="8" x2="12.01" y2="8"></line>
      </svg>
    );
  }
  
  // Default icon (circle)
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"></circle>
    </svg>
  );
};

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
          const agentLabel = getAgentLabel(step.agent);
          
          return (
            <div key={idx} className="timeline-node">
              {!isLast && <div className="timeline-connector"></div>}
              <div className="timeline-icon">
                {getAgentIcon(step.agent)}
              </div>
              <div className="timeline-content">
                <button 
                  className="timeline-header"
                  onClick={() => toggleStep(idx)}
                  aria-expanded={isExpanded}
                  aria-controls={`step-content-${idx}`}
                >
                  <div className="timeline-agent">
                    {agentLabel}
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
                    {step.output}
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
