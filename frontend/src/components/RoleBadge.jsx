import { useAuth } from "../auth/AuthContext";

export default function RoleBadge() {
  const { currentRole } = useAuth();

  if (!currentRole) return null;

  const formatRole = (role) => {
    return role.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
  };

  const getRoleColor = (role) => {
    switch (role) {
      case "administrator": return "var(--app-error, #ef4444)"; // Red-ish
      case "manager": return "var(--app-warning, #f59e0b)"; // Yellow/Orange
      case "support_agent": return "var(--app-primary, #3b82f6)"; // Blue
      case "customer": return "var(--app-success, #10b981)"; // Green
      default: return "var(--app-text-muted, #9ca3af)";
    }
  };

  return (
    <div style={{
      display: "inline-flex",
      alignItems: "center",
      padding: "0.35rem 0.75rem",
      backgroundColor: "var(--app-bg-inset, rgba(0,0,0,0.2))",
      border: `1px solid ${getRoleColor(currentRole)}`,
      borderRadius: "9999px",
      fontSize: "0.75rem",
      fontWeight: "600",
      color: getRoleColor(currentRole),
      textTransform: "uppercase",
      letterSpacing: "0.05em",
      boxShadow: "0 1px 2px rgba(0,0,0,0.1)"
    }}>
      <span style={{
        display: "inline-block",
        width: "6px",
        height: "6px",
        borderRadius: "50%",
        backgroundColor: getRoleColor(currentRole),
        marginRight: "6px"
      }}></span>
      {formatRole(currentRole)}
    </div>
  );
}
