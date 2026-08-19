import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "@/lib/api";

const AdminAuthContext = createContext(null);

function formatApiError(error) {
  if (!error) return "Something went wrong. Please try again.";

  // Handle network / CORS errors where browser blocks response access
  if (!error.response) {
    if (error.code === "ERR_NETWORK" || error.message?.includes("Network Error")) {
      return "Network/CORS error: Unable to connect to backend server. Please verify backend deployment and CORS origin settings.";
    }
    return error.message || "Unable to connect to the server.";
  }

  const detail = error.response.data?.detail;
  if (detail == null) {
    if (error.response.status === 401) return "Invalid email or password.";
    if (error.response.status === 403) return "Access forbidden.";
    if (error.response.status === 429) return "Too many failed attempts. Account temporarily locked.";
    if (error.response.status >= 500) return "Server error. Please try again later.";
    return "Something went wrong. Please try again.";
  }
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  }
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export const AdminAuthProvider = ({ children }) => {
  // admin: null while checking session, false when confirmed logged out, object when authenticated
  const [admin, setAdmin] = useState(null);
  const [checking, setChecking] = useState(true);

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setAdmin(data);
    } catch {
      setAdmin(false);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = async (email, password) => {
    try {
      const { data } = await api.post("/auth/login", { email, password });
      if (data.access_token) {
        localStorage.setItem("admin_token", data.access_token);
      }
      setAdmin(data);
      return { success: true };
    } catch (e) {
      return {
        success: false,
        error: formatApiError(e),
      };
    }
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // ignore — we clear client state regardless
    }
    localStorage.removeItem("admin_token");
    setAdmin(false);
  };

  return (
    <AdminAuthContext.Provider value={{ admin, checking, login, logout }}>
      {children}
    </AdminAuthContext.Provider>
  );
};

export const useAdminAuth = () => useContext(AdminAuthContext);
