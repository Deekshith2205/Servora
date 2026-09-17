import { useState } from "react";
import { useAuth } from "./AuthContext";
import { CUSTOMER, SUPPORT_AGENT, MANAGER, ADMINISTRATOR } from "./roles";
import { DEMO_USERS, DEMO_CUSTOMERS } from "./demoIdentities";

export default function RoleSwitcher() {
  const { currentRole, currentUser, switchIdentity } = useAuth();
  const [isOpen, setIsOpen] = useState(false);

  const handleRoleSelect = async (role) => {
    if (role === CUSTOMER) {
      // Default to Alice
      await switchIdentity(CUSTOMER, null, DEMO_CUSTOMERS[0].id);
    } else {
      // Find matching user
      const user = DEMO_USERS.find(u => u.role === role);
      if (user) {
        await switchIdentity(role, user.id, null);
      }
    }
    setIsOpen(false);
  };

  const handleIdentitySelect = async (id, isCustomer) => {
    if (isCustomer) {
      await switchIdentity(CUSTOMER, null, id);
    } else {
      const user = DEMO_USERS.find(u => u.id === parseInt(id));
      if (user) {
        await switchIdentity(user.role, user.id, null);
      }
    }
    setIsOpen(false);
  };

  // GET /api/auth/me already returns the real resolved name directly
  // (see app/auth/dependency.py::CurrentActor) — no need to re-derive it
  // by matching actor_type/id against the DEMO_USERS/DEMO_CUSTOMERS
  // lists above, which used response fields (actor_type, a bare id) the
  // real endpoint never actually sends (it sends role/user_id/
  // customer_id/name), so that lookup always fell through to "Unknown".
  const currentName = currentUser?.name || "Unknown";
  const initial = currentName.charAt(0).toUpperCase();

  const rowStyle = (active) => ({
    width: "100%", textAlign: "left", padding: "0.55rem 0.6rem", borderRadius: "8px",
    background: active ? "var(--app-primary-soft)" : "transparent",
    color: active ? "var(--app-primary)" : "var(--app-text-primary)",
    fontWeight: active ? 600 : 500,
    border: "none", cursor: "pointer", fontSize: "0.88rem", transition: "background 0.15s",
  });

  return (
    <div style={{ position: "relative", marginLeft: "auto", marginRight: "1rem" }}>
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
            Demo Role
          </span>
          <span style={{ fontWeight: 600, fontSize: "0.88rem", color: "var(--app-text-primary)" }}>
            {currentRole ? `${currentRole.replace("_", " ")} · ${currentName}` : "Select role..."}
          </span>
        </span>
      </button>

      {isOpen && (
        <div style={{
          position: "absolute", top: "100%", right: 0, marginTop: "0.6rem",
          background: "var(--app-surface)", border: "1px solid var(--app-border)",
          borderRadius: "16px", padding: "0.6rem", width: "240px", zIndex: 100,
          boxShadow: "0 20px 25px -5px rgba(15,23,42,0.1), 0 8px 10px -6px rgba(15,23,42,0.08)",
        }}>
          <div style={{ fontSize: "0.7rem", color: "var(--app-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "0.4rem", padding: "0 0.4rem" }}>Switch Role</div>
          <button style={rowStyle(currentRole === CUSTOMER)} onClick={() => handleRoleSelect(CUSTOMER)}>Customer</button>
          <button style={rowStyle(currentRole === SUPPORT_AGENT)} onClick={() => handleRoleSelect(SUPPORT_AGENT)}>Support Agent</button>
          <button style={rowStyle(currentRole === MANAGER)} onClick={() => handleRoleSelect(MANAGER)}>Manager</button>
          <button style={rowStyle(currentRole === ADMINISTRATOR)} onClick={() => handleRoleSelect(ADMINISTRATOR)}>Administrator</button>

          <div style={{ borderTop: "1px solid var(--app-border)", margin: "0.5rem 0.2rem" }}></div>
          <div style={{ fontSize: "0.7rem", color: "var(--app-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "0.4rem", padding: "0 0.4rem" }}>Switch Identity</div>
          {currentRole === CUSTOMER ? (
            DEMO_CUSTOMERS.map(c => (
              <button key={`c-${c.id}`} style={rowStyle(currentUser?.id === c.id)} onClick={() => handleIdentitySelect(c.id, true)}>
                {c.name}
              </button>
            ))
          ) : (
            DEMO_USERS.map(u => (
              <button key={`u-${u.id}`} style={rowStyle(currentUser?.id === u.id)} onClick={() => handleIdentitySelect(u.id, false)}>
                {u.name} ({u.role.replace("_", " ")})
              </button>
            ))
          )}

          <div style={{ borderTop: "1px solid var(--app-border)", margin: "0.5rem 0.2rem" }}></div>
          <button
            style={{ ...rowStyle(false), color: "var(--app-danger-text)" }}
            onClick={async () => { await switchIdentity(null, null, null); setIsOpen(false); }}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
