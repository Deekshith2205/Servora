import { useAuth } from "./AuthContext";
import { hasPermission } from "./roles";

export default function Can({ permission, children }) {
  const { currentRole, loading } = useAuth();

  const isAllowed = Array.isArray(permission)
    ? permission.some(p => hasPermission(currentRole, p))
    : hasPermission(currentRole, permission);

  if (loading || !isAllowed) {
    return null;
  }

  return children;
}
