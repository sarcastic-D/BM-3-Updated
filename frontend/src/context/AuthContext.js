import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "@/lib/api";

const AuthContext = createContext(null);

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tenants, setTenants] = useState([]);
  const [selectedTenant, setSelectedTenantState] = useState(
    () => localStorage.getItem("bm_tenant") || "All");

  // persist the selected tenant so it survives page reloads
  const setSelectedTenant = useCallback((val) => {
    setSelectedTenantState(val);
    if (val && val !== "All") localStorage.setItem("bm_tenant", val);
    else localStorage.removeItem("bm_tenant");
  }, []);

  const loadTenants = useCallback(async () => {
    try {
      const { data } = await api.get("/tenants");
      setTenants(data);
      // if the persisted tenant is no longer accessible, fall back to "All"
      const stored = localStorage.getItem("bm_tenant");
      if (stored && !data.some((t) => t.id === stored)) {
        localStorage.removeItem("bm_tenant");
        setSelectedTenantState("All");
      }
    } catch (e) {
      /* ignore */
    }
  }, []);

  const bootstrap = useCallback(async () => {
    const token = localStorage.getItem("bm_token");
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
      await loadTenants();
    } catch (e) {
      localStorage.removeItem("bm_token");
    } finally {
      setLoading(false);
    }
  }, [loadTenants]);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("bm_token", data.token);
    setUser(data.user);
    await loadTenants();
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("bm_token");
    setUser(null);
    window.location.href = "/login";
  };

  const isAdmin = user?.role === "super_admin";
  const isTenantAdmin = user?.role === "tenant_admin";
  const canWrite = ["super_admin", "tenant_admin", "analyst"].includes(user?.role);

  return (
    <AuthContext.Provider
      value={{ user, loading, login, logout, tenants, loadTenants, selectedTenant, setSelectedTenant, isAdmin, isTenantAdmin, canWrite }}
    >
      {children}
    </AuthContext.Provider>
  );
};
