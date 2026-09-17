import { useAuth } from "./AuthContext";
import { hasPermission } from "./roles";
import AccessDenied from "../pages/AccessDenied";

export default function ProtectedRoute({ permission, children }) {
  const { currentRole, loading } = useAuth();

  if (loading) {
    return <div style={{ padding: "2rem", textAlign: "center", color: "var(--app-text-muted)" }}>Loading access...</div>;
  }

  const isAllowed = Array.isArray(permission) 
    ? permission.some(p => hasPermission(currentRole, p))
    : hasPermission(currentRole, permission);

  if (!isAllowed) {
    return <AccessDenied />;
  }

  return children;
}
