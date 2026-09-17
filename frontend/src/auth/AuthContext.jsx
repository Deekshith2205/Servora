import { createContext, useContext, useEffect, useState } from "react";
import { fetchAuthMe, fetchPermissions, googleSignInRequest, loginRequest, logoutRequest, registerRequest } from "../api/client";
import { setPermissionsCache } from "./roles";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [currentRole, setCurrentRole] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshIdentity = async () => {
    setLoading(true);
    try {
      const [actorData, permsData] = await Promise.all([fetchAuthMe(), fetchPermissions()]);
      setPermissionsCache(permsData);
      setCurrentUser(actorData);
      setCurrentRole(actorData?.role || null);
    } catch (err) {
      console.error("Failed to load auth identity/permissions", err);
      setCurrentUser(null);
      setCurrentRole(null);
    } finally {
      setLoading(false);
    }
  };

  // Real login: POST /api/auth/login verifies the password against a
  // real stored hash and hands back a genuine, server-side session
  // token — this is the ONLY thing api/client.js's request() attaches
  // (as `Authorization: Bearer <token>`) from here on.
  const login = async (email, password) => {
    const result = await loginRequest(email, password);
    localStorage.setItem("servoraToken", result.token);
    await refreshIdentity();
    return result;
  };

  const register = async (name, email, password) => {
    const result = await registerRequest(name, email, password);
    localStorage.setItem("servoraToken", result.token);
    await refreshIdentity();
    return result;
  };

  // credential is the ID token Google Identity Services' JS client
  // returns — verified server-side, see app/api/auth.py::google_sign_in().
  const loginWithGoogle = async (credential) => {
    const result = await googleSignInRequest(credential);
    localStorage.setItem("servoraToken", result.token);
    await refreshIdentity();
    return result;
  };

  const logout = async () => {
    try {
      await logoutRequest();
    } catch (err) {
      // Best-effort server-side invalidation — the token is discarded
      // client-side regardless, so this is never a reason to stay "logged in".
      console.error("Logout request failed", err);
    } finally {
      localStorage.removeItem("servoraToken");
      setCurrentRole(null);
      setCurrentUser(null);
    }
  };

  useEffect(() => {
    if (localStorage.getItem("servoraToken")) {
      refreshIdentity();
    } else {
      setLoading(false);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ currentRole, currentUser, loading, login, register, logout, loginWithGoogle }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
