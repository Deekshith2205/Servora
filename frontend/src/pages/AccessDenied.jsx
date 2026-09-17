export default function AccessDenied({ message }) {
  return (
    <div className="app-panel-fit" style={{ margin: "2rem auto", maxWidth: "600px", textAlign: "center", padding: "4rem 2rem", background: "var(--app-surface)", border: "1px solid var(--app-border)", borderRadius: "12px", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)" }}>
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="var(--app-error, #ef4444)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: "1.5rem" }}>
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
      </svg>
      <h2 style={{ color: "var(--app-text-primary)", margin: "0 0 0.75rem 0", fontSize: "1.5rem", fontFamily: "'Syne', sans-serif" }}>Access Denied</h2>
      <p style={{ color: "var(--app-text-muted)", margin: 0, fontSize: "1rem", lineHeight: "1.5" }}>
        {message || "You do not have permission to view this page or perform this action."}
      </p>
    </div>
  );
}
