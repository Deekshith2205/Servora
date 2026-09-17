import { useState } from "react";
import { useAuth } from "./AuthContext";

// Post-real-auth: this is now just an identity chip + Sign Out, not a
// role picker — switching who you're acting as requires a real login
// (see Login.jsx), matching how a real login system actually works.
export default function RoleSwitcher() {
  const { currentRole, currentUser, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  if (!currentRole) return null;

  const currentName = currentUser?.name || "Unknown";
  const initial = currentName.charAt(0).toUpperCase();

  const handleSignOut = async () => {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      setSigningOut(false);
      setIsOpen(false);
    }
  };

  return (
    <div
      style={{
        position: "relative",
        marginLeft: "auto",
        marginRight: "1rem",
      }}
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: "flex", alignItems: "center", gap: "0.65rem",
          background: "var(--app-surface)", border: "1px solid var(--app-border)",
          padding: "0.4rem 0.9rem 0.4rem 0.4rem", borderRadius: "999px", cursor: "pointer",
          boxShadow: "0 1px 2px rgba(15,23,42,0.04)",
        }}
      >
        <span style={{
          width: "28px", height: "28px", borderRadius: "999px", flexShrink: 0,
          background: "linear-gradient(135deg, #2563EB, #0EA5E9)", color: "#fff",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "0.8rem", fontWeight: 700,
        }}>
          {initial}
        </span>
        <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
          <span style={{ fontSize: "0.68rem", color: "var(--app-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Signed in as
          </span>
          <span style={{ fontWeight: 600, fontSize: "0.88rem", color: "var(--app-text-primary)" }}>
            {currentRole.replace("_", " ")} · {currentName}
          </span>
        </span>
      </button>

      {isOpen && (
        <div style={{
          position: "absolute", top: "100%", right: 0, marginTop: "0.6rem",
          background: "var(--app-surface)", border: "1px solid var(--app-border)",
          borderRadius: "16px", padding: "0.6rem", width: "200px", zIndex: 100,
          boxShadow: "0 20px 25px -5px rgba(15,23,42,0.1), 0 8px 10px -6px rgba(15,23,42,0.08)",
        }}>
          <button
            disabled={signingOut}
            onClick={handleSignOut}
            style={{
              width: "100%", textAlign: "left", padding: "0.55rem 0.6rem", borderRadius: "8px",
              background: "transparent", color: "var(--app-danger-text)", fontWeight: 500,
              border: "none", cursor: signingOut ? "default" : "pointer", fontSize: "0.88rem",
              opacity: signingOut ? 0.6 : 1,
            }}
          >
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      )}
    </div>
  );
}
