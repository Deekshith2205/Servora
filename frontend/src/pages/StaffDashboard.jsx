import { useEffect, useState } from "react";
import { fetchEscalations } from "../api/client";

// Helper to determine badge class
function getBadgeClass(type, value) {
  if (!value) return "badge-neutral";
  const val = value.toLowerCase();
  
  if (type === 'sentiment') {
    if (val === 'negative' || val === 'angry') return 'badge-danger';
    if (val === 'positive') return 'badge-success';
    return 'badge-neutral';
  }
  
  if (type === 'urgency') {
    if (val === 'high' || val === '10' || val === '9' || val === '8') return 'badge-warning';
    if (val === 'medium' || val === '5' || val === '6' || val === '7') return 'badge-info';
    return 'badge-success';
  }
  
  if (type === 'status') {
    if (val === 'open') return 'badge-info';
    if (val === 'resolved') return 'badge-success';
    if (val === 'escalated') return 'badge-warning';
    if (val === 'closed') return 'badge-neutral';
    return 'badge-info'; // default fallback for 'in progress', 'investigating'
  }
  
  return "badge-neutral";
}

export default function StaffDashboard() {
  const [tickets, setTickets] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEscalations()
      .then(setTickets)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="app-panel">
      {error && (
        <div className="app-error-banner">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
          {error}
        </div>
      )}
      
      {loading ? (
        <div className="app-empty-state">Loading escalations...</div>
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
              {tickets.map((t) => (
                <tr key={t.id}>
                  <td style={{fontWeight: 600, color: 'var(--app-text-secondary)'}}>#{t.id}</td>
                  <td>{t.category}</td>
                  <td style={{fontWeight: 500}}>{t.subject}</td>
                  <td>
                    <span className={`app-badge ${getBadgeClass('sentiment', t.sentiment)}`}>
                      {t.sentiment}
                    </span>
                  </td>
                  <td>
                    <span className={`app-badge ${getBadgeClass('urgency', t.urgency)}`}>
                      {t.urgency}
                    </span>
                  </td>
                  <td>
                    <span className={`app-badge ${getBadgeClass('status', t.status)}`}>
                      {t.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : !error ? (
        <div className="app-empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>
          </svg>
          <h3 style={{color: 'var(--app-text-primary)', margin: '0 0 0.5rem 0'}}>No active escalations</h3>
          <p style={{margin: 0}}>There are no tickets requiring human attention right now.</p>
        </div>
      ) : null}
    </div>
  );
}
