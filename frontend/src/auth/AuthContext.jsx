import { createContext, useContext, useEffect, useState } from "react";
import { fetchAuthMe, fetchPermissions } from "../api/client";
import { setPermissionsCache } from "./roles";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [currentRole, setCurrentRole] = useState(localStorage.getItem("servoraRole") || null);
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Switch identity
  const switchIdentity = async (role, userId, customerId) => {
    if (role) localStorage.setItem("servoraRole", role);
    else localStorage.removeItem("servoraRole");

    if (userId) localStorage.setItem("servoraUserId", userId);
    else localStorage.removeItem("servoraUserId");

    if (customerId) localStorage.setItem("servoraCustomerId", customerId);
    else localStorage.removeItem("servoraCustomerId");

    setCurrentRole(role);
    await refreshIdentity();
  };

  const refreshIdentity = async () => {
    setLoading(true);
    try {
      const [actorData, permsData] = await Promise.all([
        fetchAuthMe(),
        fetchPermissions()
      ]);
      setPermissionsCache(permsData);
      setCurrentUser(actorData);
    } catch (err) {
      console.error("Failed to load auth identity/permissions", err);
      setCurrentUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshIdentity();
  }, []);

  return (
    <AuthContext.Provider value={{ currentRole, currentUser, loading, switchIdentity }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
