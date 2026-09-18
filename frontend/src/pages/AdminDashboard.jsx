import React from "react";
import Analytics from "./Analytics";

export default function AdminDashboard({ setActiveTab }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', flex: 1, paddingBottom: '2rem' }}>
      
      <div className="escalations-header" style={{ marginBottom: '-1rem' }}>
        <div>
          <h2 style={{fontFamily: "'Syne', sans-serif", fontSize: '1.75rem', margin: '0 0 0.5rem 0', color: 'var(--app-text-primary)'}}>
            Admin Overview
          </h2>
          <p style={{margin: 0, color: 'var(--app-text-secondary)'}}>
            System administration and organizational analytics.
          </p>
        </div>
      </div>

      {/* Quick Links */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem' }}>
        
        <div className="app-panel" style={{ cursor: 'pointer', transition: 'all 0.2s ease', border: '1px solid var(--app-border)' }} onClick={() => setActiveTab('users')}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
            <div style={{ background: 'var(--app-surface-hover)', padding: '0.5rem', borderRadius: '8px', color: 'var(--app-primary)' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
              </svg>
            </div>
            <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--app-text-primary)' }}>Users</h3>
          </div>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--app-text-secondary)' }}>Manage roles, access, and accounts.</p>
        </div>

        <div className="app-panel" style={{ cursor: 'pointer', transition: 'all 0.2s ease', border: '1px solid var(--app-border)' }} onClick={() => setActiveTab('kb')}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
            <div style={{ background: 'var(--app-surface-hover)', padding: '0.5rem', borderRadius: '8px', color: 'var(--app-primary)' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
                <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
              </svg>
            </div>
            <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--app-text-primary)' }}>Knowledge Base</h3>
          </div>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--app-text-secondary)' }}>Manage internal and customer articles.</p>
        </div>

        <div className="app-panel" style={{ cursor: 'pointer', transition: 'all 0.2s ease', border: '1px solid var(--app-border)' }} onClick={() => setActiveTab('settings')}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
            <div style={{ background: 'var(--app-surface-hover)', padding: '0.5rem', borderRadius: '8px', color: 'var(--app-primary)' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
              </svg>
            </div>
            <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--app-text-primary)' }}>Settings</h3>
          </div>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--app-text-secondary)' }}>System configuration and routing.</p>
        </div>

      </div>

      <hr style={{ border: 0, borderTop: '1px solid var(--app-border)', margin: '1rem 0' }} />

      {/* Embedded Analytics Component */}
      <Analytics />
    </div>
  );
}
