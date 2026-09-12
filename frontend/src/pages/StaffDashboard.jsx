import { useEffect, useState, useMemo } from "react";
import { fetchEscalationDetail, fetchEscalations } from "../api/client";

// Helper to determine badge class
function getBadgeClass(type, value) {
  if (!value) return "badge-neutral";
  const val = value.toString().toLowerCase();
  
  if (type === 'sentiment') {
    if (val === 'negative' || val === 'angry') return 'badge-danger';
    if (val === 'positive') return 'badge-success';
    return 'badge-neutral';
  }
  
  if (type === 'urgency') {
    const num = parseInt(val, 10);
    if (!isNaN(num)) {
      if (num >= 8) return 'badge-warning';
      if (num >= 5) return 'badge-info';
      return 'badge-success';
    }
    if (val === 'high') return 'badge-warning';
    if (val === 'medium') return 'badge-info';
    return 'badge-success';
  }
  
  if (type === 'status') {
    if (val === 'open') return 'badge-info';
    if (val === 'resolved') return 'badge-success';
    if (val === 'escalated') return 'badge-warning';
    if (val === 'closed') return 'badge-neutral';
    return 'badge-info'; 
  }
  
  return "badge-neutral";
}

export default function StaffDashboard() {
  const [tickets, setTickets] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  
  const [selectedEscalation, setSelectedEscalation] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadData = () => {
    setLoading(true);
    setError(null);
    fetchEscalations()
      .then((data) => {
        const records = Array.isArray(data) ? data : data.value || [];
        setTickets(records);
      })
      .catch((err) => setError(err.message || "Failed to load escalations"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === "Escape") setSelectedEscalation(null);
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, []);

  const handleSelectEscalation = (ticket) => {
    setSelectedEscalation(ticket);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    
    fetchEscalationDetail(ticket.id)
      .then((res) => {
        setSelectedEscalation((curr) => {
          if (curr && curr.id === ticket.id) {
            setDetail(res);
            setDetailLoading(false);
          }
          return curr;
        });
      })
      .catch((err) => {
        setSelectedEscalation((curr) => {
          if (curr && curr.id === ticket.id) {
            setDetailError(err.message || "Failed to load escalation detail");
            setDetailLoading(false);
          }
          return curr;
        });
      });
  };

  const metrics = useMemo(() => {
    if (!tickets || tickets.length === 0) return null;
    
    let active = 0;
    let highPriority = 0;
    let requiresAttention = 0;

    tickets.forEach(t => {
      const status = (t.status || "").toLowerCase();
      const urgencyNum = parseInt(t.urgency, 10);
      
      if (status !== "closed" && status !== "resolved") active++;
      if (!isNaN(urgencyNum) && urgencyNum >= 8) highPriority++;
      if (status === "open") requiresAttention++;
    });

    return {
      active,
      highPriority,
      requiresAttention,
      total: tickets.length
    };
  }, [tickets]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', flex: 1, paddingBottom: '2rem' }}>
      
      {/* Human Handoff Context Banner */}
      <div className="handoff-banner">
        <div style={{display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, color: 'var(--app-primary)'}}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="16" x2="12" y2="12"></line>
            <line x1="12" y1="8" x2="12.01" y2="8"></line>
          </svg>
          Servora Handoff
        </div>
        <div className="handoff-banner-text">
          Autonomous investigation complete <span className="arrow">&rarr;</span> Human attention required <span className="arrow">&rarr;</span> Support team reviews context
        </div>
      </div>

      {/* Summary Cards */}
      {metrics && !error && !loading && (
        <div className="summary-cards-grid">
          <div className="summary-card">
            <span className="summary-card-title">Active Escalations</span>
            <span className="summary-card-value">{metrics.active}</span>
            <span className="summary-card-desc">Currently open or in progress</span>
          </div>
          <div className="summary-card">
            <span className="summary-card-title">High Priority</span>
            <div style={{display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
              <span className="summary-card-value" style={{color: metrics.highPriority > 0 ? 'var(--app-danger-text)' : 'inherit'}}>
                {metrics.highPriority}
              </span>
              {metrics.highPriority > 0 && (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--app-danger-text)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginTop: '4px'}}>
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                  <line x1="12" y1="9" x2="12" y2="13"></line>
                  <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
              )}
            </div>
            <span className="summary-card-desc">Urgency requiring attention</span>
          </div>
          <div className="summary-card">
            <span className="summary-card-title">Requires Attention</span>
            <span className="summary-card-value">{metrics.requiresAttention}</span>
            <span className="summary-card-desc">Open cases</span>
          </div>
          <div className="summary-card">
            <span className="summary-card-title">Total Escalations</span>
            <span className="summary-card-value">{metrics.total}</span>
            <span className="summary-card-desc">Loaded from support queue</span>
          </div>
        </div>
      )}

      {/* Main Panel */}
      <div style={{marginTop: '4px'}}>
        {error && (
          <div className="app-error-banner">
            <div style={{display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
              <span>Unable to load escalations: {error}</span>
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
          <div className="app-panel-fit">
            <div className="app-table-container">
              {[1, 2, 3, 4].map(i => <div key={i} className="skeleton-row"></div>)}
            </div>
          </div>
        ) : tickets.length > 0 ? (
          <div className="app-panel-fit">
            <div className="escalations-header">
              <div>
                <h3 style={{margin: '0 0 0.25rem 0', fontSize: '1.1rem', color: 'var(--app-text-primary)'}}>Escalations</h3>
                <p style={{margin: 0, fontSize: '0.85rem', color: 'var(--app-text-secondary)'}}>Cases handed off from Servora for human review.</p>
              </div>
              <div className="escalations-count">{tickets.length} {tickets.length === 1 ? 'case' : 'cases'}</div>
            </div>
            
            <div className="app-table-container">
              <table className="app-table">
                <thead>
                  <tr>
                    <th style={{width: '80px'}}>ID</th>
                    <th style={{width: '120px'}}>Category</th>
                    <th>Subject</th>
                    <th style={{width: '120px'}}>Sentiment</th>
                    <th style={{width: '120px'}}>Urgency</th>
                    <th style={{width: '120px'}}>Status</th>
                    <th style={{width: '40px'}}></th>
                  </tr>
                </thead>
                <tbody>
                  {tickets.map((t) => {
                    const isHighPriority = parseInt(t.urgency, 10) >= 8;
                    return (
                      <tr 
                        key={t.id} 
                        onClick={() => handleSelectEscalation(t)}
                        className={`escalation-row ${selectedEscalation?.id === t.id ? 'active' : ''}`}
                      >
                        <td className="col-id">
                          {isHighPriority && <span className="priority-indicator" title="High Priority"></span>}
                          #{t.id}
                        </td>
                        <td className="col-category">{t.category}</td>
                        <td className="col-subject">{t.subject}</td>
                        <td>
                          <span className={`app-badge ${getBadgeClass('sentiment', t.sentiment)}`}>
                            {t.sentiment}
                          </span>
                        </td>
                        <td>
                          <span className={`app-badge ${getBadgeClass('urgency', t.urgency)}`}>
                            {t.urgency}/10
                          </span>
                        </td>
                        <td>
                          <span className={`app-badge ${getBadgeClass('status', t.status)}`}>
                            {t.status}
                          </span>
                        </td>
                        <td className="col-action">
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="9 18 15 12 9 6"></polyline>
                          </svg>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="escalations-footer">
              Showing {tickets.length} {tickets.length === 1 ? 'escalation' : 'escalations'}
            </div>
          </div>
        ) : !error ? (
          <div className="app-panel-fit" style={{justifyContent: 'center', minHeight: '300px'}}>
            <div className="app-empty-state" style={{padding: '2rem'}}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                <polyline points="22 4 12 14.01 9 11.01"></polyline>
              </svg>
              <h3 style={{color: 'var(--app-text-primary)', margin: '0 0 0.5rem 0'}}>You're all caught up.</h3>
              <p style={{margin: 0}}>No escalations currently require human attention.</p>
            </div>
          </div>
        ) : null}
      </div>

      {/* Escalation Detail Drawer */}
      {selectedEscalation && (
        <div className="app-drawer-overlay" onClick={() => setSelectedEscalation(null)}>
          <div className="app-drawer" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
            <div className="app-drawer-header">
              <div>
                <h2 className="app-drawer-title">Escalation #{selectedEscalation.id}</h2>
                <p className="app-drawer-subtitle">{selectedEscalation.subject}</p>
              </div>
              <button className="app-drawer-close" onClick={() => setSelectedEscalation(null)} aria-label="Close">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>
            
            <div className="app-drawer-content">
              
              <div className="drawer-section">
                <div className="drawer-section-title">Escalation Context</div>
                <div className="drawer-field-grid">
                  <div className="drawer-field">
                    <span className="drawer-field-label">Category</span>
                    <span className="drawer-field-value" style={{textTransform: 'capitalize'}}>{selectedEscalation.category}</span>
                  </div>
                  <div className="drawer-field">
                    <span className="drawer-field-label">Status</span>
                    <span className="drawer-field-value">
                      <span className={`app-badge ${getBadgeClass('status', selectedEscalation.status)}`}>
                        {selectedEscalation.status}
                      </span>
                    </span>
                  </div>
                  <div className="drawer-field">
                    <span className="drawer-field-label">Sentiment</span>
                    <span className="drawer-field-value">
                      <span className={`app-badge ${getBadgeClass('sentiment', selectedEscalation.sentiment)}`}>
                        {selectedEscalation.sentiment}
                      </span>
                    </span>
                  </div>
                  <div className="drawer-field">
                    <span className="drawer-field-label">Urgency</span>
                    <span className="drawer-field-value">
                      <span className={`app-badge ${getBadgeClass('urgency', selectedEscalation.urgency)}`}>
                        {selectedEscalation.urgency}/10
                      </span>
                    </span>
                  </div>
                  {selectedEscalation.customer_id && (
                    <div className="drawer-field">
                      <span className="drawer-field-label">Customer ID</span>
                      <span className="drawer-field-value">#{selectedEscalation.customer_id}</span>
                    </div>
                  )}
                </div>
              </div>

              {selectedEscalation.message && (
                <div className="drawer-section">
                  <div className="drawer-section-title">Customer Message</div>
                  <div className="drawer-message-box">
                    {selectedEscalation.message}
                  </div>
                </div>
              )}

              {/* Data fetched from detail API */}
              {detailLoading ? (
                <div className="drawer-section" style={{display: 'flex', flexDirection: 'column', gap: '0.75rem'}}>
                  <div className="skeleton-row" style={{height: '16px', width: '120px', borderRadius: '4px', border: 'none'}}></div>
                  <div className="skeleton-row" style={{height: '100px', borderRadius: '8px', border: 'none'}}></div>
                </div>
              ) : detailError ? (
                <div className="app-error-banner">
                  <span>{detailError}</span>
                </div>
              ) : detail ? (
                <>
                  {detail.trace && detail.trace.length > 0 ? (
                    <div className="drawer-section">
                      <div className="drawer-section-title">Servora Investigation</div>
                      <ul style={{margin: 0, paddingLeft: '1.2rem', color: 'var(--app-text-secondary)', fontSize: '0.9rem', display: 'flex', flexDirection: 'column', gap: '0.5rem'}}>
                        {detail.trace.map((step, i) => (
                          <li key={i}>
                            <strong style={{color: 'var(--app-text-primary)'}}>{step.agent}:</strong> {step.output}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <div className="drawer-section" style={{background: 'transparent', border: '1px dashed var(--app-border)', textAlign: 'center'}}>
                      <p style={{margin: 0, fontSize: '0.85rem', color: 'var(--app-text-muted)'}}>No reasoning trace on file for this escalation.</p>
                    </div>
                  )}

                  {detail.handoff_packet && (
                    <div className="drawer-section handoff-card" style={{margin: 0}}>
                      <div className="drawer-section-title handoff-card-title">Human Handoff</div>
                      <dl className="handoff-card-dl" style={{display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '0.5rem 1rem', margin: 0, fontSize: '0.9rem'}}>
                        <dt style={{fontWeight: 600, color: 'var(--app-text-secondary)'}}>Situation</dt>
                        <dd style={{margin: 0, color: 'var(--app-text-primary)'}}>{detail.handoff_packet.situation}</dd>
                        
                        <dt style={{fontWeight: 600, color: 'var(--app-text-secondary)'}}>Likely cause</dt>
                        <dd style={{margin: 0, color: 'var(--app-text-primary)'}}>{detail.handoff_packet.root_cause_hypothesis}</dd>
                        
                        <dt style={{fontWeight: 600, color: 'var(--app-text-secondary)'}}>Recommended next step</dt>
                        <dd style={{margin: 0, color: 'var(--app-text-primary)'}}>{detail.handoff_packet.recommended_action}</dd>
                        
                        <dt style={{fontWeight: 600, color: 'var(--app-text-secondary)'}}>Urgency</dt>
                        <dd style={{margin: 0, color: 'var(--app-text-primary)'}}>{detail.handoff_packet.urgency}/10</dd>
                      </dl>
                    </div>
                  )}
                </>
              ) : null}
              
            </div>
          </div>
        </div>
      )}
      
    </div>
  );
}
