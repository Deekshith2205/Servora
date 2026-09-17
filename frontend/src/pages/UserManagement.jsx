import { useEffect, useState } from "react";
import { fetchUsers, updateUserRole } from "../api/client";
import { STAFF_ROLES } from "../auth/roles";
import Can from "../auth/Can";

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
