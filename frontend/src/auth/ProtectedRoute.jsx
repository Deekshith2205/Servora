import { useAuth } from "./AuthContext";
import { isPermitted } from "./roles";
import AccessDenied from "../pages/AccessDenied";

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
    return <AccessDenied />;
  }

  return children;
}
