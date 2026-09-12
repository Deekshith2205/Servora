import { useEffect, useState } from "react";
import { fetchAnalyticsSummary } from "../api/client";

// STUB page. Tracked by issue: "Analytics dashboard (churn/anomaly radar)".
export default function Analytics() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalyticsSummary()
      .then(setSummary)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="app-panel" style={{alignItems: 'center', justifyContent: 'center'}}>
      {loading ? (
        <div className="app-empty-state">Loading analytics...</div>
      ) : (
        <div className="app-empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="20" x2="18" y2="10"></line>
            <line x1="12" y1="20" x2="12" y2="4"></line>
            <line x1="6" y1="20" x2="6" y2="14"></line>
          </svg>
          <h3 style={{color: 'var(--app-text-primary)', margin: '0 0 0.5rem 0', fontSize: '1.25rem'}}>Analytics overview</h3>
          <p style={{margin: 0, maxWidth: '400px'}}>
            Analytics data will appear here when available. The analytics dashboard is currently under active development.
          </p>
          
          {/* Keep the raw stub data if it exists just for completeness, but keep it muted */}
          {summary && (
            <div style={{marginTop: '3rem', textAlign: 'left', background: 'var(--app-bg)', padding: '1rem', borderRadius: 'var(--app-radius-md)', fontSize: '0.8rem', color: 'var(--app-text-muted)', border: '1px solid var(--app-border)'}}>
              <div style={{fontWeight: 600, marginBottom: '0.5rem', textTransform: 'uppercase', fontSize: '0.7rem'}}>Raw Stub Data</div>
              <pre style={{margin: 0, overflowX: 'auto'}}>{JSON.stringify(summary, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
