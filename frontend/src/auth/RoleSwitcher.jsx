import { useState } from "react";
import { useAuth } from "./AuthContext";
import { CUSTOMER, SUPPORT_AGENT, MANAGER, ADMINISTRATOR } from "./roles";

const DEMO_USERS = [
  { id: 1, role: SUPPORT_AGENT, name: "Jordan Lee" },
  { id: 2, role: MANAGER, name: "Priya Shah" },
  { id: 3, role: ADMINISTRATOR, name: "Sam Okafor" }
];

const DEMO_CUSTOMERS = [
  { id: 1, name: "Alice Rao" },
  { id: 2, name: "Bob Nunez" }
];

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

  return (
    <div style={{ position: "relative", marginLeft: "auto", marginRight: "1rem" }}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: "flex", flexDirection: "column", alignItems: "flex-end",
          background: "var(--app-surface)", border: "1px solid var(--app-border)",
          padding: "0.3rem 0.8rem", borderRadius: "6px", cursor: "pointer", color: "var(--app-text)"
        }}
      >
        <div style={{ fontSize: "0.75rem", color: "var(--app-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Demo Role
        </div>
        <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>
          {currentRole ? `${currentRole.replace("_", " ")} - ${currentName}` : "Select Role..."}
        </div>
      </button>

      {isOpen && (
        <div style={{
          position: "absolute", top: "100%", right: 0, marginTop: "0.5rem",
          background: "var(--app-surface)", border: "1px solid var(--app-border)",
          borderRadius: "8px", padding: "0.5rem", width: "220px", zIndex: 100,
          boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.5)"
        }}>
          <div style={{ fontSize: "0.75rem", color: "var(--app-text-muted)", marginBottom: "0.5rem", padding: "0 0.5rem" }}>Switch Role</div>
          <button style={{width:"100%", textAlign:"left", padding:"0.5rem", background:"transparent", border:"none", color:"var(--app-text)", cursor:"pointer"}} onClick={() => handleRoleSelect(CUSTOMER)}>Customer</button>
          <button style={{width:"100%", textAlign:"left", padding:"0.5rem", background:"transparent", border:"none", color:"var(--app-text)", cursor:"pointer"}} onClick={() => handleRoleSelect(SUPPORT_AGENT)}>Support Agent</button>
          <button style={{width:"100%", textAlign:"left", padding:"0.5rem", background:"transparent", border:"none", color:"var(--app-text)", cursor:"pointer"}} onClick={() => handleRoleSelect(MANAGER)}>Manager</button>
          <button style={{width:"100%", textAlign:"left", padding:"0.5rem", background:"transparent", border:"none", color:"var(--app-text)", cursor:"pointer"}} onClick={() => handleRoleSelect(ADMINISTRATOR)}>Administrator</button>
          
          <div style={{ borderTop: "1px solid var(--app-border)", margin: "0.5rem 0" }}></div>
          <div style={{ fontSize: "0.75rem", color: "var(--app-text-muted)", marginBottom: "0.5rem", padding: "0 0.5rem" }}>Switch Identity</div>
          {currentRole === CUSTOMER ? (
            DEMO_CUSTOMERS.map(c => (
              <button key={`c-${c.id}`} style={{width:"100%", textAlign:"left", padding:"0.5rem", background: currentUser?.id === c.id ? "var(--app-bg)" : "transparent", border:"none", color:"var(--app-text)", cursor:"pointer"}} onClick={() => handleIdentitySelect(c.id, true)}>
                {c.name}
              </button>
            ))
          ) : (
            DEMO_USERS.map(u => (
              <button key={`u-${u.id}`} style={{width:"100%", textAlign:"left", padding:"0.5rem", background: currentUser?.id === u.id ? "var(--app-bg)" : "transparent", border:"none", color:"var(--app-text)", cursor:"pointer"}} onClick={() => handleIdentitySelect(u.id, false)}>
                {u.name} ({u.role.replace("_", " ")})
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
