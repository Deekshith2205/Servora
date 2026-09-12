import { useEffect, useState } from "react";
import { fetchAnalyticsSummary } from "../api/client";

export default function Analytics() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = () => {
    setLoading(true);
    setError(null);
    fetchAnalyticsSummary()
      .then(setSummary)
      .catch((err) => setError(err.message || "Failed to load analytics"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  const isNotImplemented = summary && summary.status === "not_implemented";
  const hasRecurringIssues = summary && summary.recurring_issues && summary.recurring_issues.length > 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', flex: 1 }}>
      
      {error && (
        <div className="app-error-banner">
          <div style={{display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            <span>Unable to load analytics: {error}</span>
          </div>
          <button 
            onClick={loadData}
            style={{background: 'var(--app-surface)', color: 'var(--app-danger-text)', border: '1px solid currentColor', padding: '0.4rem 1rem', borderRadius: '4px', cursor: 'pointer', fontWeight: 600, fontSize: '0.8rem'}}
          >
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <div className="app-panel">
           <div style={{display: 'flex', flexDirection: 'column', gap: '1rem'}}>
             <div className="skeleton-row" style={{height: '24px', width: '200px', border: 'none', borderRadius: '4px'}}></div>
             <div className="skeleton-row" style={{height: '16px', width: '300px', border: 'none', borderRadius: '4px'}}></div>
             <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem', marginTop: '2rem'}}>
                <div className="skeleton-row" style={{height: '150px', border: 'none', borderRadius: '12px'}}></div>
                <div className="skeleton-row" style={{height: '150px', border: 'none', borderRadius: '12px'}}></div>
             </div>
           </div>
        </div>
      ) : isNotImplemented ? (
        <div className="app-panel" style={{ background: 'var(--app-surface)', position: 'relative', overflow: 'hidden' }}>
          
          <div style={{position: 'absolute', top: '-100px', right: '-100px', opacity: 0.03, pointerEvents: 'none'}}>
             <svg width="400" height="400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="20" x2="18" y2="10"></line>
                <line x1="12" y1="20" x2="12" y2="4"></line>
                <line x1="6" y1="20" x2="6" y2="14"></line>
             </svg>
          </div>

          <div style={{ maxWidth: '800px', margin: '0 auto', width: '100%' }}>
            
            <div style={{textAlign: 'center', margin: '3rem 0 4rem'}}>
              <div style={{display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '64px', height: '64px', background: 'var(--app-surface-blue)', borderRadius: '16px', color: 'var(--app-primary)', marginBottom: '1.5rem'}}>
                 <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                    <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                    <line x1="12" y1="22.08" x2="12" y2="12"></line>
                 </svg>
              </div>
              <h2 style={{fontFamily: "'Syne', sans-serif", fontSize: '2rem', margin: '0 0 1rem 0', color: 'var(--app-text-primary)'}}>Support Intelligence</h2>
              <p style={{fontSize: '1.1rem', color: 'var(--app-text-secondary)', margin: 0, lineHeight: 1.6}}>
                Analytics insights are being built for Servora's support operations.<br/>
                Once available, this space will surface support patterns and outcomes.
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
              
              <div className="analytics-placeholder-card">
                <div className="analytics-placeholder-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                     <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                  </svg>
                </div>
                <h3>Recurring issues</h3>
                <p>Identify patterns across repeated customer requests to proactively address root causes.</p>
                <div className="analytics-status-badge">In development</div>
              </div>

              <div className="analytics-placeholder-card">
                <div className="analytics-placeholder-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                     <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                     <circle cx="9" cy="7" r="4"></circle>
                     <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                     <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                  </svg>
                </div>
                <h3>Support signals</h3>
                <p>Surface meaningful customer signals that may indicate retention risk or friction.</p>
                <div className="analytics-status-badge">In development</div>
              </div>

            </div>
          </div>
        </div>
      ) : summary ? (
        <div style={{display: 'flex', flexDirection: 'column', gap: '1.5rem'}}>
          <div className="escalations-header">
            <div>
              <h3 style={{margin: '0 0 0.25rem 0', fontSize: '1.1rem', color: 'var(--app-text-primary)'}}>Recurring Issues</h3>
              <p style={{margin: 0, fontSize: '0.85rem', color: 'var(--app-text-secondary)'}}>Automated root-cause clustering of recent open tickets.</p>
            </div>
            {hasRecurringIssues && <div className="escalations-count">{summary.recurring_issues.length} {summary.recurring_issues.length === 1 ? 'cluster' : 'clusters'}</div>}
          </div>
          
          {hasRecurringIssues ? (
            <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '1rem'}}>
              {summary.recurring_issues.map((issue, idx) => (
                <div key={issue.cluster_id || idx} className="app-panel" style={{display: 'flex', flexDirection: 'column', gap: '0.75rem'}}>
                  <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                    <span className="app-badge badge-warning" style={{display: 'inline-flex', alignItems: 'center', gap: '0.4rem'}}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4"></path><path d="M12 8h.01"></path></svg>
                      {issue.ticket_count} tickets affected
                    </span>
                    <span style={{fontSize: '0.75rem', color: 'var(--app-text-muted)'}}>
                      IDs: {issue.ticket_ids?.join(', ')}
                    </span>
                  </div>
                  
                  <div>
                    <span style={{fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 600, color: 'var(--app-text-secondary)', letterSpacing: '0.05em'}}>Theme Pattern</span>
                    <div style={{fontSize: '0.9rem', color: 'var(--app-text-primary)', marginTop: '0.2rem'}}>{issue.pattern}</div>
                  </div>
                  
                  <div className="handoff-card" style={{marginTop: '0.5rem', marginBottom: 0}}>
                    <p className="handoff-card-title">Automated Hypothesis</p>
                    <p style={{margin: 0, fontSize: '0.85rem', color: 'var(--app-text-primary)', lineHeight: 1.5}}>
                      {issue.root_cause_hypothesis}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="app-panel-fit" style={{justifyContent: 'center', minHeight: '300px', border: '1px solid var(--app-border)'}}>
              <div className="app-empty-state" style={{padding: '2rem'}}>
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                  <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
                <h3 style={{color: 'var(--app-text-primary)', margin: '0 0 0.5rem 0'}}>All clear.</h3>
                <p style={{margin: 0}}>No recurring issue clusters detected in the selected period.</p>
              </div>
            </div>
          )}
        </div>
      ) : null}
      
    </div>
  );
}
