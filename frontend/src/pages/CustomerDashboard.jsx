import { useEffect, useState } from "react";
import { fetchMyTickets, fetchNotifications } from "../api/client";

export default function CustomerDashboard({ setActiveTab }) {
  const [tickets, setTickets] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([fetchMyTickets(), fetchNotifications()])
      .then(([ticketsData, notificationsData]) => {
        setTickets(ticketsData || []);
        setNotifications(notificationsData || []);
      })
      .catch((err) => setError(err.message || "Failed to load dashboard data"))
      .finally(() => setLoading(false));
  }, []);

  const openTickets = tickets.filter(t => t.status !== "resolved" && t.status !== "closed");

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', flex: 1 }}>
      
      {error && (
        <div className="app-error-banner">
          Unable to load dashboard: {error}
        </div>
      )}

      {loading ? (
        <div className="app-panel">
          <div className="skeleton-row" style={{height: '24px', width: '200px', border: 'none', borderRadius: '4px'}}></div>
          <div className="skeleton-row" style={{height: '100px', marginTop: '1rem', border: 'none', borderRadius: '4px'}}></div>
        </div>
      ) : (
        <div style={{display: 'flex', flexDirection: 'column', gap: '1.5rem'}}>
          
          <div style={{marginBottom: '0.5rem'}}>
            <h2 style={{fontFamily: "'Syne', sans-serif", fontSize: '1.75rem', margin: '0 0 0.5rem 0', color: 'var(--app-text-primary)'}}>Welcome Back</h2>
            <p style={{margin: 0, color: 'var(--app-text-secondary)'}}>Here's an overview of your support activity.</p>
          </div>
          
          <div className="summary-cards-grid" style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem'}}>
            <div className="app-panel" style={{display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center', gap: '0.5rem', padding: '2rem'}}>
              <h3 style={{margin: 0, fontSize: '3rem', color: 'var(--app-primary)'}}>{openTickets.length}</h3>
              <p style={{margin: 0, color: 'var(--app-text-secondary)', fontWeight: 600}}>Active Support Tickets</p>
              <button 
                className="app-btn app-btn-primary" 
                style={{marginTop: '1rem'}}
                onClick={() => setActiveTab('history')}
              >
                View History
              </button>
            </div>
            
            <div className="app-panel" style={{display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center', gap: '1rem', padding: '2rem'}}>
              <div style={{width: '64px', height: '64px', borderRadius: '50%', background: 'var(--app-surface-hover)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--app-primary)'}}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
              </div>
              <div>
                <h3 style={{margin: '0 0 0.25rem 0', color: 'var(--app-text-primary)'}}>Need Help?</h3>
                <p style={{margin: 0, color: 'var(--app-text-secondary)', fontSize: '0.9rem'}}>Our AI assistant is ready to help you 24/7.</p>
              </div>
              <button 
                className="app-btn app-btn-primary" 
                onClick={() => setActiveTab('chat')}
              >
                Start a Conversation
              </button>
            </div>
          </div>

          <div className="app-panel">
            <h3 style={{margin: '0 0 1rem 0'}}>Recent Notifications</h3>
            {notifications.length === 0 ? (
              <p style={{color: 'var(--app-text-muted)', fontStyle: 'italic', margin: 0}}>You have no recent notifications.</p>
            ) : (
              <div style={{display: 'flex', flexDirection: 'column', gap: '1rem'}}>
                {notifications.slice(0, 5).map(notif => (
                  <div key={notif.id} style={{padding: '1rem', borderRadius: '8px', background: 'var(--app-surface-hover)', border: '1px solid var(--app-border)'}}>
                    <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem'}}>
                      <strong style={{color: 'var(--app-text-primary)'}}>{notif.subject}</strong>
                      <span style={{fontSize: '0.8rem', color: 'var(--app-text-muted)'}}>{new Date(notif.created_at).toLocaleDateString()}</span>
                    </div>
                    <p style={{margin: 0, fontSize: '0.9rem', color: 'var(--app-text-secondary)'}}>{notif.body}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
          
        </div>
      )}
    </div>
  );
}
