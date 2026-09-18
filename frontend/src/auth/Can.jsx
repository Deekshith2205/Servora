import { useAuth } from "./AuthContext";
import { isPermitted } from "./roles";

export default function Can({ permission, children }) {
  const { currentRole, loading } = useAuth();

  if (loading || !isPermitted(currentRole, permission)) {
    return null;
  }

  return children;
}
