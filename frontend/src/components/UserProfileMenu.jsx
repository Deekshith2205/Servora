import { useState, useRef, useEffect } from "react";
import { useAuth } from "../auth/AuthContext";

export default function UserProfileMenu() {
  const { currentUser } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!currentUser) return null;

  return (
    <div className="user-profile-menu" ref={menuRef} style={{ position: "relative" }}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          padding: "0.5rem",
          borderRadius: "8px"
        }}
        aria-haspopup="true"
        aria-expanded={isOpen}
      >
        <div style={{
          width: "32px",
          height: "32px",
          borderRadius: "50%",
          background: "var(--app-primary)",
          color: "white",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: "bold",
          fontSize: "1rem"
        }}>
          {currentUser.name ? currentUser.name.charAt(0).toUpperCase() : "?"}
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
          <span style={{ fontWeight: 600, fontSize: "0.9rem", color: "var(--app-text-primary)" }}>
            {currentUser.name}
          </span>
          {/* We display the RoleBadge elsewhere, but we can keep it here in the dropdown if wanted */}
        </div>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--app-text-muted)" }}>
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>

      {isOpen && (
        <div style={{
          position: "absolute",
          top: "100%",
          right: 0,
          marginTop: "0.5rem",
          background: "var(--app-surface)",
          border: "1px solid var(--app-border)",
          borderRadius: "8px",
          minWidth: "200px",
          boxShadow: "0 10px 15px -3px rgba(0,0,0,0.1)",
          zIndex: 50,
          padding: "0.5rem 0"
        }}>
          <div style={{ padding: "0.5rem 1rem", borderBottom: "1px solid var(--app-border)", marginBottom: "0.5rem" }}>
            <p style={{ margin: 0, fontWeight: 600, color: "var(--app-text-primary)" }}>{currentUser.name}</p>
            <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--app-text-muted)" }}>{currentUser.email || "No email"}</p>
          </div>
          
          <div style={{ padding: "0.5rem 1rem" }}>
            <p style={{ margin: "0 0 0.5rem 0", fontSize: "0.8rem", color: "var(--app-text-muted)" }}>
              Note: Customer Profile destination is not currently present in the repository.
            </p>
            <button 
              disabled
              style={{
                width: "100%",
                textAlign: "left",
                padding: "0.5rem",
                background: "transparent",
                border: "none",
                color: "var(--app-text-muted)",
                cursor: "not-allowed",
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                opacity: 0.7
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
              My Profile (Not Available)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
