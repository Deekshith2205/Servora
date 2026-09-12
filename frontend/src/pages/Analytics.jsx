import { useEffect, useState } from "react";
import { fetchAnalyticsSummary } from "../api/client";

export default function Analytics() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const doFetch = () => {
    fetchAnalyticsSummary()
      .then(setSummary)
      .catch((err) => setError(err.message || "Failed to load analytics"))
      .finally(() => setLoading(false));
  };

  const loadData = () => {
    setLoading(true);
    setError(null);
    doFetch();
  };

  useEffect(() => {
    doFetch();
  }, []);

  const hasRecurringIssues = summary && summary.recurring_issues && summary.recurring_issues.length > 0;
  const hasChurnSignals = summary && summary.churn_signals && summary.churn_signals.length > 0;
  
  const hasTrend = summary && summary.trend && summary.trend.length > 0;
  const trendMax = hasTrend ? Math.max(1, ...summary.trend.map((d) => d.count)) : 1;
  
  const hasSentiment = summary && summary.sentiment_trend && summary.sentiment_trend.length > 0;
  const sentimentMax = hasSentiment ? Math.max(1, ...summary.sentiment_trend.map((d) => Math.max(d.positive, d.neutral, d.negative))) : 1;
  
  const hasConfidence = summary && summary.confidence_distribution && summary.confidence_distribution.total > 0;

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
      ) : summary ? (
        <div style={{display: 'flex', flexDirection: 'column', gap: '1.5rem'}}>
          
          <div style={{marginBottom: '0.5rem'}}>
            <h2 style={{fontFamily: "'Syne', sans-serif", fontSize: '1.75rem', margin: '0 0 0.5rem 0', color: 'var(--app-text-primary)'}}>Support Intelligence</h2>
            <p style={{margin: 0, color: 'var(--app-text-secondary)'}}>Understand support activity and outcomes.</p>
          </div>
          
          <div className="summary-cards-grid">
            <div className="summary-card">
              <span className="summary-card-title">Resolution Rate</span>
              <span className="summary-card-value">
                {summary.resolution_rate.total > 0 ? `${Math.round(summary.resolution_rate.rate * 100)}%` : '0%'}
              </span>
              <span className="summary-card-desc">
                {summary.resolution_rate.total > 0 ? `${summary.resolution_rate.resolved} of ${summary.resolution_rate.total} processed` : 'No ticket data'}
              </span>
            </div>
            
            <div className="summary-card">
              <span className="summary-card-title">Escalation Rate</span>
              <span className="summary-card-value">
                {summary.escalation_rate.total > 0 ? `${Math.round(summary.escalation_rate.rate * 100)}%` : '0%'}
              </span>
              <span className="summary-card-desc">
                {summary.escalation_rate.total > 0 ? `${summary.escalation_rate.escalated} of ${summary.escalation_rate.total} processed` : 'No ticket data'}
              </span>
            </div>
            
            <div className="summary-card">
              <span className="summary-card-title">Processed Conversations</span>
              <span className="summary-card-value">{summary.resolution_rate.total}</span>
              <span className="summary-card-desc">Resolved + escalated</span>
            </div>
          </div>
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

          {/* Issue #16: ticket volume trend */}
          <div style={{display: 'flex', flexDirection: 'column', gap: '0.75rem'}}>
            <div className="escalations-header">
              <div>
                <h3 style={{margin: '0 0 0.25rem 0', fontSize: '1.1rem', color: 'var(--app-text-primary)'}}>Ticket Volume Trend</h3>
                <p style={{margin: 0, fontSize: '0.85rem', color: 'var(--app-text-secondary)'}}>Daily ticket volume over the last 30 days.</p>
              </div>
            </div>
            {hasTrend && (
              <div className="app-panel" style={{padding: '1rem 1rem 0.5rem'}}>
                <svg
                  viewBox={`0 0 ${summary.trend.length * 12} 120`}
                  width="100%"
                  height="120"
                  preserveAspectRatio="none"
                >
                  {summary.trend.map((day, i) => {
                    const barHeight = Math.max(3, (day.count / trendMax) * 116);
                    return (
                      <rect
                        key={day.date}
                        x={i * 12}
                        y={120 - barHeight}
                        width={9}
                        height={barHeight}
                        rx={1.5}
                        style={{ fill: 'var(--app-primary)', opacity: day.count ? 1 : 0.15 }}
                      >
                        <title>{`${day.date}: ${day.count} ticket${day.count === 1 ? '' : 's'}`}</title>
                      </rect>
                    );
                  })}
                </svg>
              </div>
            )}
          </div>

          <div style={{display: 'flex', flexDirection: 'column', gap: '0.75rem'}}>
            <div className="escalations-header">
              <div>
                <h3 style={{margin: '0 0 0.25rem 0', fontSize: '1.1rem', color: 'var(--app-text-primary)'}}>Sentiment Trend</h3>
                <p style={{margin: 0, fontSize: '0.85rem', color: 'var(--app-text-secondary)'}}>Daily ticket sentiment over the last 30 days.</p>
              </div>
              <div style={{display: 'flex', gap: '1rem', fontSize: '0.8rem'}}>
                <span style={{display: 'flex', alignItems: 'center', gap: '0.4rem'}}><span style={{display: 'inline-block', width: '12px', height: '4px', borderRadius: '2px', background: 'var(--app-success-text)'}}></span> Positive</span>
                <span style={{display: 'flex', alignItems: 'center', gap: '0.4rem'}}><span style={{display: 'inline-block', width: '12px', height: '4px', borderRadius: '2px', background: 'var(--app-warning-text)'}}></span> Neutral</span>
                <span style={{display: 'flex', alignItems: 'center', gap: '0.4rem'}}><span style={{display: 'inline-block', width: '12px', height: '4px', borderRadius: '2px', background: 'var(--app-danger-text)'}}></span> Negative</span>
              </div>
            </div>
            {hasSentiment && (
              <div className="app-panel" style={{padding: '1rem 1rem 0.5rem'}}>
                <svg
                  viewBox={`0 0 ${summary.sentiment_trend.length * 12} 120`}
                  width="100%"
                  height="120"
                  preserveAspectRatio="none"
                >
                  {summary.sentiment_trend.map((day, i) => {
                    // stack bars
                    const posH = (day.positive / sentimentMax) * 116;
                    const neuH = (day.neutral / sentimentMax) * 116;
                    const negH = (day.negative / sentimentMax) * 116;
                    
                    const drawH = Math.max(3, posH + neuH + negH);
                    const drawNeg = negH > 0 ? Math.max(1, (negH / (posH + neuH + negH)) * drawH) : 0;
                    const drawNeu = neuH > 0 ? Math.max(1, (neuH / (posH + neuH + negH)) * drawH) : 0;
                    const drawPos = posH > 0 ? Math.max(1, (posH / (posH + neuH + negH)) * drawH) : 0;
                    
                    let y = 120;
                    const elements = [];
                    
                    if (day.positive === 0 && day.neutral === 0 && day.negative === 0) {
                      return (
                        <rect key={day.date} x={i * 12} y={120 - 3} width={9} height={3} rx={1.5} style={{ fill: 'var(--app-border)' }} />
                      );
                    }
                    
                    if (drawPos > 0) {
                      y -= drawPos;
                      elements.push(<rect key={`${day.date}-pos`} x={i * 12} y={y} width={9} height={drawPos} fill="var(--app-success-text)" title={`${day.date}: ${day.positive} positive`} />);
                    }
                    if (drawNeu > 0) {
                      y -= drawNeu;
                      elements.push(<rect key={`${day.date}-neu`} x={i * 12} y={y} width={9} height={drawNeu} fill="var(--app-warning-text)" title={`${day.date}: ${day.neutral} neutral`} />);
                    }
                    if (drawNeg > 0) {
                      y -= drawNeg;
                      elements.push(<rect key={`${day.date}-neg`} x={i * 12} y={y} width={9} height={drawNeg} fill="var(--app-danger-text)" title={`${day.date}: ${day.negative} negative`} />);
                    }
                    
                    return <g key={day.date}>{elements}</g>;
                  })}
                </svg>
              </div>
            )}
          </div>

          <div style={{display: 'flex', flexDirection: 'column', gap: '0.75rem'}}>
            <div className="escalations-header">
              <div>
                <h3 style={{margin: '0 0 0.25rem 0', fontSize: '1.1rem', color: 'var(--app-text-primary)'}}>Classifier Confidence</h3>
                <p style={{margin: 0, fontSize: '0.85rem', color: 'var(--app-text-secondary)'}}>Distribution of LLM confidence scores.</p>
              </div>
            </div>
            <div className="app-panel" style={{padding: '1.5rem', display: 'flex', gap: '2rem', alignItems: 'center'}}>
              {hasConfidence ? (
                <>
                  <div style={{flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem'}}>
                    <div style={{display: 'flex', alignItems: 'center', gap: '1rem'}}>
                      <div style={{width: '80px', fontSize: '0.85rem', color: 'var(--app-text-secondary)'}}>High (&ge;0.8)</div>
                      <div style={{flex: 1, height: '8px', background: 'var(--app-surface)', borderRadius: '4px', overflow: 'hidden'}}>
                        <div style={{width: `${(summary.confidence_distribution.high / summary.confidence_distribution.total) * 100}%`, height: '100%', background: 'var(--app-success-text)', borderRadius: '4px'}}></div>
                      </div>
                      <div style={{width: '40px', textAlign: 'right', fontWeight: 600}}>{summary.confidence_distribution.high}</div>
                    </div>
                    <div style={{display: 'flex', alignItems: 'center', gap: '1rem'}}>
                      <div style={{width: '80px', fontSize: '0.85rem', color: 'var(--app-text-secondary)'}}>Moderate</div>
                      <div style={{flex: 1, height: '8px', background: 'var(--app-surface)', borderRadius: '4px', overflow: 'hidden'}}>
                        <div style={{width: `${(summary.confidence_distribution.moderate / summary.confidence_distribution.total) * 100}%`, height: '100%', background: 'var(--app-warning-text)', borderRadius: '4px'}}></div>
                      </div>
                      <div style={{width: '40px', textAlign: 'right', fontWeight: 600}}>{summary.confidence_distribution.moderate}</div>
                    </div>
                    <div style={{display: 'flex', alignItems: 'center', gap: '1rem'}}>
                      <div style={{width: '80px', fontSize: '0.85rem', color: 'var(--app-text-secondary)'}}>Low (&lt;0.6)</div>
                      <div style={{flex: 1, height: '8px', background: 'var(--app-surface)', borderRadius: '4px', overflow: 'hidden'}}>
                        <div style={{width: `${(summary.confidence_distribution.low / summary.confidence_distribution.total) * 100}%`, height: '100%', background: 'var(--app-danger-text)', borderRadius: '4px'}}></div>
                      </div>
                      <div style={{width: '40px', textAlign: 'right', fontWeight: 600}}>{summary.confidence_distribution.low}</div>
                    </div>
                  </div>
                  <div style={{textAlign: 'center', paddingLeft: '2rem', borderLeft: '1px solid var(--app-border)'}}>
                    <div style={{fontSize: '2rem', fontWeight: 700, color: 'var(--app-text-primary)'}}>{summary.confidence_distribution.total}</div>
                    <div style={{fontSize: '0.85rem', color: 'var(--app-text-secondary)'}}>Total tickets</div>
                  </div>
                </>
              ) : (
                <div style={{width: '100%', textAlign: 'center', padding: '1rem'}}>
                  <p style={{margin: 0, color: 'var(--app-text-muted)'}}>Classifier confidence data unavailable yet.</p>
                </div>
              )}
            </div>
          </div>

          {/* Issue #16: churn risk — customers with multiple still-unresolved tickets */}
          <div style={{display: 'flex', flexDirection: 'column', gap: '0.75rem'}}>
            <div className="escalations-header">
              <div>
                <h3 style={{margin: '0 0 0.25rem 0', fontSize: '1.1rem', color: 'var(--app-text-primary)'}}>Churn Risk</h3>
                <p style={{margin: 0, fontSize: '0.85rem', color: 'var(--app-text-secondary)'}}>Customers with multiple still-unresolved tickets.</p>
              </div>
              {hasChurnSignals && (
                <div className="escalations-count">
                  {summary.churn_signals.length} flagged
                </div>
              )}
            </div>

            {hasChurnSignals ? (
              <div className="app-table-container">
                <table className="app-table">
                  <thead>
                    <tr>
                      <th>Customer</th>
                      <th>Unresolved</th>
                      <th>Categories</th>
                      <th>Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.churn_signals.map((s) => (
                      <tr key={s.customer_id}>
                        <td>{s.customer_name || `Customer #${s.customer_id}`}</td>
                        <td>{s.unresolved_ticket_count}</td>
                        <td style={{textTransform: 'capitalize'}}>{s.categories.join(', ')}</td>
                        <td>
                          <span className={`app-badge ${s.risk_level === 'high' ? 'badge-danger' : 'badge-warning'}`}>
                            {s.risk_level}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="app-panel-fit" style={{justifyContent: 'center', minHeight: '160px', border: '1px solid var(--app-border)'}}>
                <div className="app-empty-state" style={{padding: '1.5rem'}}>
                  <p style={{margin: 0}}>No customers currently show a repeat-unresolved pattern.</p>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : null}
      
    </div>
  );
}
