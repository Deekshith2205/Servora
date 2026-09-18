import { useAuth } from "./AuthContext";
import { isPermitted } from "./roles";

export default function ProtectedRoute({ permission, children }) {
  const { currentRole, loading } = useAuth();

  if (loading) {
    return <div style={{ padding: "2rem", textAlign: "center", color: "var(--app-text-muted)" }}>Loading access...</div>;
  }

  // Defense in depth: the sidebar (App.jsx) already hides a tab this role
  // can't reach, so reaching this false branch in practice means the
  // role changed out from under an already-mounted page, not a real nav
  // path — this banner is the fallback for that split second, not the
  // primary UX.
  if (!isPermitted(currentRole, permission)) {
    return (
      <div className="app-error-banner" style={{ margin: "2rem auto", maxWidth: "600px", textAlign: "center", padding: "3rem" }}>
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--app-error)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: "1rem" }}>
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
        </svg>
        <h2 style={{ color: "var(--app-text-primary)", margin: "0 0 0.5rem 0" }}>Access Denied</h2>
        <p style={{ color: "var(--app-text-muted)", margin: 0 }}>You do not have permission to view this page.</p>
      </div>
    );
  }

  return children;
}
