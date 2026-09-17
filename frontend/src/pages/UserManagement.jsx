import { useEffect, useState } from "react";
import { createUser, fetchUsers, updateUserRole } from "../api/client";
import { STAFF_ROLES } from "../auth/roles";
import Can from "../auth/Can";

function AddStaffForm({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState(STAFF_ROLES[0]);
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setName(""); setEmail(""); setRole(STAFF_ROLES[0]); setPassword(""); setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const user = await createUser({ name: name.trim(), email: email.trim(), role, password });
      onCreated(user);
      reset();
      setOpen(false);
    } catch (err) {
      setError(err.message || "Failed to create user");
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="app-btn-primary" style={{ alignSelf: "flex-start" }}>
        + Add Staff Member
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="app-panel" style={{ gap: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontFamily: "'Syne', sans-serif", color: "var(--app-text-primary)" }}>Add Staff Member</h3>
        <button type="button" onClick={() => { setOpen(false); reset(); }} className="app-btn-secondary">Cancel</button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.85rem" }}>
        <input required placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} className="app-input" style={{ padding: "0.6rem 0.8rem", borderRadius: "8px", border: "1px solid var(--app-border)" }} />
        <input required type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} className="app-input" style={{ padding: "0.6rem 0.8rem", borderRadius: "8px", border: "1px solid var(--app-border)" }} />
        <select value={role} onChange={(e) => setRole(e.target.value)} className="app-input" style={{ padding: "0.6rem 0.8rem", borderRadius: "8px", border: "1px solid var(--app-border)", background: "var(--app-surface)" }}>
          {STAFF_ROLES.map((r) => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
        </select>
        <input required type="password" placeholder="Initial password (min 8 chars)" value={password} onChange={(e) => setPassword(e.target.value)} className="app-input" style={{ padding: "0.6rem 0.8rem", borderRadius: "8px", border: "1px solid var(--app-border)" }} />
      </div>
      {error && <div className="app-error-banner"><span>{error}</span></div>}
      <button type="submit" disabled={submitting} className="app-btn-primary" style={{ alignSelf: "flex-start" }}>
        {submitting ? "Creating…" : "Create Staff Account"}
      </button>
    </form>
  );
}

export default function UserManagement() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [updatingId, setUpdatingId] = useState(null);

  const loadUsers = () => {
    setLoading(true);
    setError(null);
    fetchUsers()
      .then((data) => setUsers(data))
      .catch((err) => setError(err.message || "Failed to load users"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleRoleChange = (userId, newRole) => {
    setUpdatingId(userId);
    updateUserRole(userId, newRole)
      .then((updatedUser) => {
        setUsers((curr) => curr.map((u) => (u.id === updatedUser.id ? updatedUser : u)));
      })
      .catch((err) => {
        alert(err.message || "Failed to update role");
      })
      .finally(() => {
        setUpdatingId(null);
      });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", flex: 1, overflowY: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ fontFamily: "'Syne', sans-serif", fontSize: "1.75rem", margin: "0 0 0.5rem 0", color: "var(--app-text-primary)" }}>User Management</h2>
          <p style={{ margin: 0, color: "var(--app-text-secondary)" }}>Manage roles and access for staff members.</p>
        </div>
        <button onClick={loadUsers} className="app-btn-secondary">Refresh</button>
      </div>

      <Can permission="manage_users">
        <AddStaffForm onCreated={(user) => setUsers((curr) => [...curr, user])} />
      </Can>

      {error && (
        <div className="app-error-banner">
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="app-panel">
          <div className="skeleton-row" style={{ height: "40px", marginBottom: "1rem" }}></div>
          <div className="skeleton-row" style={{ height: "40px", marginBottom: "1rem" }}></div>
          <div className="skeleton-row" style={{ height: "40px" }}></div>
        </div>
      ) : users.length === 0 ? (
        <div className="app-empty-state">
          <h3>No users found</h3>
          <p>There are no staff users registered in the system.</p>
        </div>
      ) : (
        <div className="app-panel" style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--app-border)", background: "var(--app-bg-inset)" }}>
                <th style={{ padding: "1rem", color: "var(--app-text-secondary)", fontWeight: 600, fontSize: "0.85rem", textTransform: "uppercase" }}>ID</th>
                <th style={{ padding: "1rem", color: "var(--app-text-secondary)", fontWeight: 600, fontSize: "0.85rem", textTransform: "uppercase" }}>Name</th>
                <th style={{ padding: "1rem", color: "var(--app-text-secondary)", fontWeight: 600, fontSize: "0.85rem", textTransform: "uppercase" }}>Email</th>
                <th style={{ padding: "1rem", color: "var(--app-text-secondary)", fontWeight: 600, fontSize: "0.85rem", textTransform: "uppercase" }}>Role</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} style={{ borderBottom: "1px solid var(--app-border)" }}>
                  <td style={{ padding: "1rem", color: "var(--app-text-muted)" }}>#{user.id}</td>
                  <td style={{ padding: "1rem", color: "var(--app-text-primary)", fontWeight: 500 }}>{user.name}</td>
                  <td style={{ padding: "1rem", color: "var(--app-text-secondary)" }}>{user.email}</td>
                  <td style={{ padding: "1rem" }}>
                    <Can permission="manage_users">
                      <select
                        value={user.role}
                        onChange={(e) => handleRoleChange(user.id, e.target.value)}
                        disabled={updatingId === user.id}
                        className="app-input"
                        style={{ padding: "0.5rem", borderRadius: "6px", border: "1px solid var(--app-border)", background: "var(--app-surface)", cursor: "pointer" }}
                      >
                        {Object.values(STAFF_ROLES).map((role) => (
                          <option key={role} value={role}>{role.charAt(0).toUpperCase() + role.slice(1)}</option>
                        ))}
                      </select>
                    </Can>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
