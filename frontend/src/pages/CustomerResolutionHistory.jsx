import { useEffect, useState } from "react";
import { fetchInvestigationByTicket, fetchMyTickets } from "../api/client";
import "./CustomerResolutionHistory.css";

function TicketHistoryRow({ ticket }) {
  const [investigation, setInvestigation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(false);

  const handleExpand = async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    setExpanded(true);
    if (!investigation && !loading) {
      setLoading(true);
      setError(null);
      try {
        const inv = await fetchInvestigationByTicket(ticket.id);
        setInvestigation(inv);
      } catch (err) {
        setError(err.message || "Failed to load resolution details.");
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <div className="crh-ticket-card">
      <div className="crh-ticket-header" onClick={handleExpand}>
        <div className="crh-ticket-main">
          <h4>{ticket.subject}</h4>
          <span className="crh-ticket-date">{new Date(ticket.created_at).toLocaleDateString()}</span>
        </div>
        <div className="crh-ticket-status">
          <span className={`app-badge status-${ticket.status}`}>
            {ticket.status}
          </span>
          <svg className={`crh-chevron ${expanded ? "expanded" : ""}`} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
        </div>
      </div>
      
      {expanded && (
        <div className="crh-ticket-details">
          <div className="crh-ticket-message">
            <p><strong>Original Message:</strong></p>
            <p>{ticket.message}</p>
          </div>
          
          {loading ? (
            <div className="crh-loading">Loading resolution...</div>
          ) : error ? (
            <div className="crh-error">{error}</div>
          ) : investigation ? (
            <div className="crh-resolution-box">
              <div className="crh-resolution-field">
                <strong>Root Cause</strong>
                <p>{investigation.root_cause || "Not specified."}</p>
              </div>
              <div className="crh-resolution-field">
                <strong>Resolution</strong>
                <p>{investigation.resolution || "Not specified."}</p>
              </div>
            </div>
          ) : (
            <div className="crh-loading">No resolution data available yet.</div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CustomerResolutionHistory() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchMyTickets()
      .then(data => {
        setTickets(data || []);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message || "Failed to load tickets.");
        setLoading(false);
      });
  }, []);

  return (
    <div className="crh-container app-panel-fit">
      <h2>Resolution History</h2>
      <p className="crh-subtitle">Track the status and outcome of your recent support conversations.</p>
      
      {loading ? (
        <div className="crh-loading">Loading history...</div>
      ) : error ? (
        <div className="app-error-banner">{error}</div>
      ) : tickets.length === 0 ? (
        <div className="app-empty-state">
          <p>You have no past conversations.</p>
        </div>
      ) : (
        <div className="crh-ticket-list">
          {tickets.map(t => <TicketHistoryRow key={t.id} ticket={t} />)}
        </div>
      )}
    </div>
  );
}
