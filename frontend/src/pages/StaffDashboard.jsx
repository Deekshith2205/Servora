import { useEffect, useState, useMemo } from "react";
import { fetchEscalations } from "../api/client";

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
    // In this backend, urgency is numeric out of 10
    const num = parseInt(val, 10);
    if (!isNaN(num)) {
      if (num >= 8) return 'badge-warning';
      if (num >= 5) return 'badge-info';
      return 'badge-success';
    }
    // Fallback if string labels were used
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

  const loadData = () => {
    setLoading(true);
    setError(null);
    fetchEscalations()
      .then((data) => {
        // Handle standard backend structure
        const records = Array.isArray(data) ? data : data.value || [];
        setTickets(records);
      })
      .catch((err) => setError(err.message || "Failed to load escalations"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  // Handle Escape key to close drawer
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === "Escape") setSelectedEscalation(null);
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, []);

  // Calculate metrics accurately from real data
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', flex: 1 }}>
      
      {/* Human Handoff Context Banner */}
      <div className="handoff-banner">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="16" x2="12" y2="12"></line>
          <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>
        <span>
          <strong>Servora Handoff:</strong> Autonomous investigation complete &rarr; Human attention required &rarr; Support team reviews context
        </span>
      </div>

      {/* Summary Cards */}
      {metrics && !error && !loading && (
        <div className="summary-cards-grid">
          <div className="summary-card">
            <span className="summary-card-title">Active Escalations</span>
            <span className="summary-card-value">{metrics.active}</span>
          </div>
          <div className="summary-card">
            <span className="summary-card-title">High Priority</span>
            <span className="summary-card-value" style={{color: metrics.highPriority > 0 ? 'var(--app-danger-text)' : 'inherit'}}>
              {metrics.highPriority}
            </span>
          </div>
          <div className="summary-card">
            <span className="summary-card-title">Requires Attention</span>
            <span className="summary-card-value">{metrics.requiresAttention}</span>
          </div>
          <div className="summary-card">
            <span className="summary-card-title">Total Escalations</span>
            <span className="summary-card-value">{metrics.total}</span>
          </div>
        </div>
      )}

      {/* Main Panel */}
      <div className="app-panel">
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
          <div className="app-table-container">
            {[1, 2, 3, 4].map(i => <div key={i} className="skeleton-row"></div>)}
          </div>
        ) : tickets.length > 0 ? (
          <div className="app-table-container">
            <table className="app-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Category</th>
                  <th>Subject</th>
                  <th>Sentiment</th>
                  <th>Urgency</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {tickets.map((t) => {
                  const isHighPriority = parseInt(t.urgency, 10) >= 8;
                  return (
                    <tr 
                      key={t.id} 
                      onClick={() => setSelectedEscalation(t)}
                      style={{background: selectedEscalation?.id === t.id ? 'var(--app-surface-hover)' : ''}}
                    >
                      <td style={{fontWeight: 600, color: 'var(--app-text-secondary)'}}>
                        {isHighPriority && <span className="priority-indicator" title="High Priority"></span>}
                        #{t.id}
                      </td>
                      <td>{t.category}</td>
                      <td style={{fontWeight: 500}}>{t.subject}</td>
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
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : !error ? (
          <div className="app-empty-state">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
              <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
            <h3 style={{color: 'var(--app-text-primary)', margin: '0 0 0.5rem 0'}}>You're all caught up.</h3>
            <p style={{margin: 0}}>No escalations currently require human attention.</p>
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
              
            </div>
          </div>
        </div>
      )}
      
    </div>
  );
}
