import { useEffect, useState, useMemo } from "react";
import { approveKBArticle, fetchEscalationDetail, fetchEscalations, fetchResolvedHistory, resolveEscalation, assignEscalation, closeEscalation } from "../api/client";
import BookingsPanel from "./BookingsPanel";
import InvestigationTimeline from "../components/InvestigationTimeline";
import ExplainableAIPanel from "../components/ExplainableAIPanel";
import { ChannelBadge } from "../components/channelMeta";

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

  const [resolvedTickets, setResolvedTickets] = useState([]);
  const [resolvedError, setResolvedError] = useState(null);
  const [resolvedLoading, setResolvedLoading] = useState(true);
  
  const [selectedEscalation, setSelectedEscalation] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Issue #17: resolve-then-suggest-a-KB-article flow, scoped to whichever
  // escalation is currently open in the drawer.
  const [resolveNotes, setResolveNotes] = useState("");
  const [resolving, setResolving] = useState(false);
  const [resolveError, setResolveError] = useState(null);
  const [kbSuggestion, setKbSuggestion] = useState(null); // { should_add, title, body, tags } | null
  // Bug found verifying issue #17 live (no API key configured, the common
  // default): the Learning Agent degrades gracefully and the resolve
  // response legitimately carries kb_suggestion: null. That's indistinguishable
  // from "haven't resolved in this session" if we only look at kbSuggestion
  // being falsy — this flag disambiguates "resolved just now, no suggestion
  // came back" from "already resolved, nothing to show" so the right message
  // renders instead of both collapsing onto the same generic one.
  const [justResolved, setJustResolved] = useState(false);
  const [kbApproving, setKbApproving] = useState(false);
  const [kbApproved, setKbApproved] = useState(false);
  const [kbApproveError, setKbApproveError] = useState(null);

  const [assigning, setAssigning] = useState(false);
  const [assignError, setAssignError] = useState(null);
  const [assignmentInput, setAssignmentInput] = useState("");

  const [closing, setClosing] = useState(false);
  const [closeError, setCloseError] = useState(null);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);

  const doFetch = () => {
    Promise.all([
      fetchEscalations().then((data) => {
        const records = Array.isArray(data) ? data : data.value || [];
        setTickets(records);
      }).catch((err) => setError(err.message || "Failed to load escalations")),
      fetchResolvedHistory().then((data) => {
        const records = Array.isArray(data) ? data : data.value || [];
        setResolvedTickets(records);
      }).catch((err) => setResolvedError(err.message || "Failed to load resolved history"))
    ]).finally(() => {
      setLoading(false);
      setResolvedLoading(false);
    });
  };

  const loadData = () => {
    setLoading(true);
    setError(null);
    setResolvedLoading(true);
    setResolvedError(null);
    doFetch();
  };

  useEffect(() => {
    doFetch();
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

    // Reset the resolve/KB-suggestion flow — it's scoped per escalation.
    setResolveNotes("");
    setResolving(false);
    setResolveError(null);
    setKbSuggestion(null);
    setJustResolved(false);
    setKbApproving(false);
    setKbApproved(false);
    setKbApproveError(null);

    // Reset assign/close state
    setAssigning(false);
    setAssignError(null);
    setAssignmentInput(ticket.assigned_to || "");
    setClosing(false);
    setCloseError(null);
    setShowCloseConfirm(false);

    fetchEscalationDetail(ticket.id)
      .then((res) => {
        setSelectedEscalation((curr) => {
          if (curr && curr.id === ticket.id) {
            setDetail(res);
            setAssignmentInput(res.assigned_to || "");
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

  const handleAssign = () => {
    if (!selectedEscalation) return;
    setAssigning(true);
    setAssignError(null);
    const valToAssign = assignmentInput.trim() === "" ? null : assignmentInput.trim();

    assignEscalation(selectedEscalation.id, valToAssign)
      .then((res) => {
        setSelectedEscalation((curr) => 
          curr && curr.id === selectedEscalation.id ? { ...curr, assigned_to: res.assigned_to } : curr
        );
        setDetail((curr) => 
          curr ? { ...curr, assigned_to: res.assigned_to } : curr
        );
        setAssignmentInput(res.assigned_to || "");
        
        // Update it in the tickets list so it reflects in the table row
        setTickets((prev) => prev.map((t) => t.id === res.id ? { ...t, assigned_to: res.assigned_to } : t));
      })
      .catch((err) => setAssignError(err.message || "Failed to assign escalation"))
      .finally(() => setAssigning(false));
  };

  const handleClose = () => {
    if (!selectedEscalation) return;
    setClosing(true);
    setCloseError(null);

    closeEscalation(selectedEscalation.id)
      .then((res) => {
        setSelectedEscalation((curr) =>
          curr && curr.id === selectedEscalation.id ? { ...curr, status: "closed" } : curr
        );
        setDetail((curr) => 
          curr ? { ...curr, status: "closed" } : curr
        );
        // Remove from active queue
        setTickets((prev) => prev.filter((t) => t.id !== res.id));
        setShowCloseConfirm(false);
      })
      .catch((err) => setCloseError(err.message || "Failed to close escalation"))
      .finally(() => setClosing(false));
  };

  const handleResolve = () => {
    if (!selectedEscalation) return;
    setResolving(true);
    setResolveError(null);

    resolveEscalation(selectedEscalation.id, resolveNotes)
      .then((res) => {
        setSelectedEscalation((curr) =>
          curr && curr.id === selectedEscalation.id ? { ...curr, status: res.ticket.status } : curr
        );
        setKbSuggestion(res.kb_suggestion);
        setJustResolved(true);
        // The resolved ticket should drop out of the open-queue list too —
        // GET /api/escalations only ever returns open/escalated tickets, so
        // patching status in place (leaving the row in `tickets`) left a
        // stale "Resolved" row (and an inflated total) in the table until
        // the next full reload. Filter it out here instead, to match what
        // a refetch would actually return.
        setTickets((prev) => prev.filter((t) => t.id !== res.ticket.id));
        setResolvedTickets((prev) => [res.ticket, ...prev]);
      })
      .catch((err) => setResolveError(err.message || "Failed to resolve this escalation"))
      .finally(() => setResolving(false));
  };

  const handleApproveKB = () => {
    if (!kbSuggestion) return;
    setKbApproving(true);
    setKbApproveError(null);

    approveKBArticle(kbSuggestion)
      .then(() => setKbApproved(true))
      .catch((err) => setKbApproveError(err.message || "Failed to add this to the knowledge base"))
      .finally(() => setKbApproving(false));
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

      {/* Resolved History Panel */}
      <div style={{marginTop: '4px'}}>
        {resolvedError && (
          <div className="app-error-banner">
            <div style={{display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
              <span>Unable to load resolved history: {resolvedError}</span>
            </div>
            <button 
              onClick={loadData}
              style={{background: 'var(--app-surface)', color: 'var(--app-danger-text)', border: '1px solid currentColor', padding: '0.4rem 1rem', borderRadius: '4px', cursor: 'pointer', fontWeight: 600, fontSize: '0.8rem'}}
            >
              Retry
            </button>
          </div>
        )}
        
        {resolvedLoading ? (
          <div className="app-panel-fit">
            <div className="app-table-container">
              {[1, 2].map(i => <div key={i} className="skeleton-row"></div>)}
            </div>
          </div>
        ) : resolvedTickets.length > 0 ? (
          <div className="app-panel-fit">
            <div className="escalations-header">
              <div>
                <h3 style={{margin: '0 0 0.25rem 0', fontSize: '1.1rem', color: 'var(--app-text-primary)'}}>Resolved History</h3>
                <p style={{margin: 0, fontSize: '0.85rem', color: 'var(--app-text-secondary)'}}>Past conversations successfully resolved.</p>
              </div>
              <div className="escalations-count">{resolvedTickets.length}</div>
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
                  {resolvedTickets.map((t) => {
                    return (
                      <tr 
                        key={t.id} 
                        onClick={() => handleSelectEscalation(t)}
                        className={`escalation-row ${selectedEscalation?.id === t.id ? 'active' : ''}`}
                      >
                        <td className="col-id">#{t.id}</td>
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
              Showing {resolvedTickets.length} {resolvedTickets.length === 1 ? 'record' : 'records'}
            </div>
          </div>
        ) : !resolvedError ? (
          <div className="app-panel-fit" style={{justifyContent: 'center', minHeight: '150px'}}>
            <div className="app-empty-state" style={{padding: '2rem'}}>
              <h3 style={{color: 'var(--app-text-primary)', margin: '0 0 0.5rem 0'}}>No history</h3>
              <p style={{margin: 0}}>No resolved conversations yet.</p>
            </div>
          </div>
        ) : null}
      </div>

      {/* Issue #20: staff review/edit UI for bookings the Booking Agent (#18) drafted. */}
      <BookingsPanel />

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
                  <div className="drawer-field">
                    <span className="drawer-field-label">Classifier Confidence</span>
                    <span className="drawer-field-value">
                      {selectedEscalation.confidence === null || selectedEscalation.confidence === undefined ? (
                        <span style={{color: 'var(--app-text-muted)', fontSize: '0.85rem'}}>Confidence unavailable</span>
                      ) : (
                        <span>
                          {Math.round(selectedEscalation.confidence * 100)}% &middot; {
                            selectedEscalation.confidence >= 0.80 ? 'High' : 
                            selectedEscalation.confidence >= 0.60 ? 'Moderate' : 'Low'
                          }
                        </span>
                      )}
                    </span>
                  </div>
                  {selectedEscalation.customer_id && (
                    <div className="drawer-field">
                      <span className="drawer-field-label">Customer ID</span>
                      <span className="drawer-field-value">#{selectedEscalation.customer_id}</span>
                    </div>
                  )}
                  <div className="drawer-field">
                    <span className="drawer-field-label">Assigned to</span>
                    <span className="drawer-field-value">
                      {selectedEscalation.assigned_to ? selectedEscalation.assigned_to : <span style={{color: 'var(--app-text-muted)', fontStyle: 'italic'}}>Unassigned</span>}
                    </span>
                  </div>
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
                  {detail.customer && (
                    <div className="drawer-section">
                      <div className="drawer-section-title">Customer Profile</div>
                      <div className="drawer-field-grid">
                        <div className="drawer-field">
                          <span className="drawer-field-label">Name</span>
                          <span className="drawer-field-value">{detail.customer.name}</span>
                        </div>
                        <div className="drawer-field">
                          <span className="drawer-field-label">Tier</span>
                          <span className="drawer-field-value">
                            <span className={`app-badge ${detail.customer.tier.toLowerCase() === 'vip' ? 'badge-warning' : 'badge-neutral'}`}>
                              {detail.customer.tier.toUpperCase()}
                            </span>
                          </span>
                        </div>
                        <div className="drawer-field">
                          <span className="drawer-field-label">Email</span>
                          <span className="drawer-field-value">{detail.customer.email}</span>
                        </div>
                        <div className="drawer-field">
                          <span className="drawer-field-label">Phone</span>
                          <span className="drawer-field-value">{detail.customer.phone || 'N/A'}</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {detail.customer.channels_used && detail.customer.channels_used.length > 0 && (
                    <div className="drawer-section">
                      <div className="drawer-section-title">Channels Used</div>
                      <div style={{display: 'flex', gap: '0.5rem', flexWrap: 'wrap'}}>
                        {detail.customer.channels_used.map(ch => (
                          <ChannelBadge key={ch} channelKey={ch} />
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="drawer-section">
                    <div className="drawer-section-title">Conversation History</div>
                    {detail.customer.conversation_history && detail.customer.conversation_history.length > 0 ? (
                      <div style={{display: 'flex', flexDirection: 'column', gap: '0.5rem'}}>
                        {detail.customer.conversation_history.map(pt => (
                          <div key={pt.id} style={{
                            display: 'flex', 
                            flexDirection: 'column',
                            gap: '0.5rem',
                            padding: '0.75rem', 
                            background: 'var(--app-surface)', 
                            border: '1px solid var(--app-border)', 
                            borderRadius: '6px',
                            fontSize: '0.85rem'
                          }}>
                            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                              <div style={{display: 'flex', gap: '0.75rem', alignItems: 'center'}}>
                                <span style={{color: 'var(--app-text-muted)'}}>#{pt.id}</span>
                                <ChannelBadge channelKey={pt.channel} />
                              </div>
                              <span className={`app-badge ${getBadgeClass('status', pt.status)}`}>{pt.status}</span>
                            </div>
                            <div style={{fontWeight: 500, color: 'var(--app-text-primary)'}}>{pt.subject}</div>
                            <div style={{display: 'flex', justifyContent: 'space-between', color: 'var(--app-text-secondary)', fontSize: '0.75rem'}}>
                              <span>{pt.category || 'Uncategorized'}</span>
                              <span>{new Date(pt.created_at).toLocaleString()}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{background: 'transparent', border: '1px dashed var(--app-border)', textAlign: 'center', padding: '1rem', borderRadius: '8px'}}>
                        <p style={{margin: 0, fontSize: '0.85rem', color: 'var(--app-text-muted)'}}>No previous conversations.</p>
                      </div>
                    )}
                  </div>
                  {detail.trace && detail.trace.length > 0 ? (
                    <>
                      <div className="drawer-section">
                        <InvestigationTimeline trace={detail.trace} />
                      </div>
                      {/* [EXPLAIN] issue #93/#99: full-mode panel, same
                          component the Customer Chat's compact "Why?"
                          link opens. */}
                      <div className="drawer-section">
                        <ExplainableAIPanel ticketId={selectedEscalation.id} mode="full" />
                      </div>
                    </>
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

              <div className="drawer-section">
                <div className="drawer-section-title">Staff Actions</div>
                <div style={{display: 'flex', flexDirection: 'column', gap: '1.5rem'}}>
                  
                  <div style={{display: 'flex', flexDirection: 'column', gap: '0.5rem'}}>
                    <label style={{fontSize: '0.85rem', fontWeight: 600, color: 'var(--app-text-secondary)'}}>Assigned to</label>
                    <div style={{display: 'flex', gap: '0.5rem'}}>
                      <input 
                        type="text" 
                        value={assignmentInput} 
                        onChange={(e) => setAssignmentInput(e.target.value)} 
                        placeholder="Unassigned"
                        disabled={assigning}
                        className="app-input"
                        style={{flex: 1}}
                      />
                      <button 
                        className="app-btn-secondary" 
                        onClick={handleAssign} 
                        disabled={assigning || (assignmentInput.trim() === (selectedEscalation.assigned_to || ""))}
                      >
                        {assigning ? 'Assigning...' : 'Assign'}
                      </button>
                    </div>
                    {assignError && <div style={{color: 'var(--app-danger-text)', fontSize: '0.8rem'}}>{assignError}</div>}
                  </div>

                  <div style={{display: 'flex', gap: '0.75rem'}}>
                    <button 
                      className="app-btn-danger" 
                      onClick={() => setShowCloseConfirm(true)}
                      disabled={closing || selectedEscalation.status === 'closed' || selectedEscalation.status === 'resolved'}
                      style={{flex: 1}}
                    >
                      Close case
                    </button>
                  </div>
                  
                  {showCloseConfirm && (
                    <div style={{background: '#fee2e2', border: '1px solid #fca5a5', padding: '1rem', borderRadius: '8px', fontSize: '0.85rem'}}>
                      <p style={{margin: '0 0 0.75rem', color: '#991b1b', fontWeight: 500}}>Close this escalation? It will leave the active support queue without running the resolution workflow.</p>
                      <div style={{display: 'flex', gap: '0.5rem'}}>
                        <button className="app-btn-secondary" onClick={() => setShowCloseConfirm(false)} disabled={closing}>Cancel</button>
                        <button className="app-btn-danger" onClick={handleClose} disabled={closing}>
                          {closing ? 'Closing...' : 'Close case'}
                        </button>
                      </div>
                      {closeError && <div style={{color: '#991b1b', fontSize: '0.8rem', marginTop: '0.5rem'}}>{closeError}</div>}
                    </div>
                  )}
                </div>
              </div>

              {/* Issue #17: resolve this escalation, then let the Learning
                  Agent suggest a KB article for a human to approve. */}
              <div className="drawer-section">
                <div className="drawer-section-title">Resolution</div>

                {justResolved ? (
                  <div style={{display: "flex", flexDirection: "column", gap: "0.75rem"}}>
                    <p style={{margin: 0, fontSize: "0.85rem", color: "var(--app-success-text)"}}>
                      ✓ Marked resolved.
                    </p>

                    {kbSuggestion === null ? (
                      <p style={{margin: 0, fontSize: "0.85rem", color: "var(--app-text-muted)"}}>
                        No knowledge base update suggested for this resolution — the
                        Learning Agent didn't return a suggestion (e.g. no LLM
                        provider configured for this environment).
                      </p>
                    ) : kbSuggestion.should_add ? (
                      kbApproved ? (
                        <p style={{margin: 0, fontSize: "0.85rem", color: "var(--app-success-text)"}}>
                          ✓ Added to the knowledge base.
                        </p>
                      ) : (
                        <div className="handoff-card" style={{margin: 0}}>
                          <p className="handoff-card-title">Add to knowledge base?</p>
                          <p style={{margin: "0 0 0.4rem", fontWeight: 600, fontSize: "0.9rem", color: "var(--app-text-primary)"}}>
                            {kbSuggestion.title}
                          </p>
                          <p style={{margin: "0 0 0.6rem", fontSize: "0.85rem", color: "var(--app-text-primary)", lineHeight: 1.5}}>
                            {kbSuggestion.body}
                          </p>
                          {kbSuggestion.tags?.length > 0 && (
                            <div style={{display: "flex", gap: "0.4rem", flexWrap: "wrap", marginBottom: "0.6rem"}}>
                              {kbSuggestion.tags.map((tag) => (
                                <span key={tag} className="app-badge badge-info">{tag}</span>
                              ))}
                            </div>
                          )}
                          {kbApproveError && <p className="error" style={{fontSize: "0.8rem"}}>{kbApproveError}</p>}
                          <div style={{display: "flex", gap: "0.5rem"}}>
                            <button
                              onClick={handleApproveKB}
                              disabled={kbApproving}
                              style={{background: "var(--app-primary)", color: "#fff", border: "none", padding: "0.4rem 1rem", borderRadius: "6px", cursor: "pointer", fontWeight: 600, fontSize: "0.8rem"}}
                            >
                              {kbApproving ? "Adding…" : "Approve"}
                            </button>
                            <button
                              onClick={() => setKbSuggestion({ ...kbSuggestion, should_add: false })}
                              disabled={kbApproving}
                              style={{background: "var(--app-surface)", border: "1px solid var(--app-border)", padding: "0.4rem 1rem", borderRadius: "6px", cursor: "pointer", fontWeight: 600, fontSize: "0.8rem"}}
                            >
                              Dismiss
                            </button>
                          </div>
                        </div>
                      )
                    ) : (
                      <p style={{margin: 0, fontSize: "0.85rem", color: "var(--app-text-muted)"}}>
                        No knowledge base update suggested for this resolution — the Learning Agent
                        judged it a one-off, not a reusable pattern.
                      </p>
                    )}
                  </div>
                ) : selectedEscalation.status === "resolved" ? (
                  <p style={{margin: 0, fontSize: "0.85rem", color: "var(--app-text-secondary)"}}>
                    This escalation is marked resolved.
                  </p>
                ) : (
                  <div style={{display: "flex", flexDirection: "column", gap: "0.6rem"}}>
                    <label style={{fontSize: "0.8rem", fontWeight: 600, color: "var(--app-text-secondary)"}}>
                      How was this resolved? (optional, but helps the KB suggestion)
                    </label>
                    <textarea
                      value={resolveNotes}
                      onChange={(e) => setResolveNotes(e.target.value)}
                      placeholder="e.g. Manually migrated the customer off the legacy billing plan, then issued the refund."
                      rows={3}
                      style={{width: "100%", padding: "0.5rem", borderRadius: "6px", border: "1px solid var(--app-border)", fontFamily: "inherit", fontSize: "0.85rem", resize: "vertical"}}
                    />
                    {resolveError && <p className="error" style={{fontSize: "0.8rem"}}>{resolveError}</p>}
                    <button
                      onClick={handleResolve}
                      disabled={resolving}
                      style={{alignSelf: "flex-start", background: "var(--app-primary)", color: "#fff", border: "none", padding: "0.5rem 1.2rem", borderRadius: "6px", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem"}}
                    >
                      {resolving ? "Resolving…" : "Mark Resolved"}
                    </button>
                  </div>
                )}
              </div>

            </div>
          </div>
        </div>
      )}
      
    </div>
  );
}
