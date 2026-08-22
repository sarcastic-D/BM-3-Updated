import "@/App.css";
import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { AppShell } from "@/components/layout/AppShell";
import { Toaster } from "@/components/ui/sonner";
import { Loader2 } from "lucide-react";

import Login from "@/pages/Login";
import AdminDashboard from "@/pages/admin/AdminDashboard";
import Tenants from "@/pages/admin/Tenants";
import TenantWizard from "@/pages/admin/TenantWizard";
import MonitoringConfig from "@/pages/admin/MonitoringConfig";
import IntelligenceSources from "@/pages/admin/IntelligenceSources";
import DetectionConfig from "@/pages/admin/DetectionConfig";
import Scheduler from "@/pages/admin/Scheduler";
import Credentials from "@/pages/admin/Credentials";
import UsersPage from "@/pages/admin/Users";
import Notifications from "@/pages/admin/Notifications";
import AuditLogs from "@/pages/admin/AuditLogs";
import SystemSettings from "@/pages/admin/SystemSettings";
import MonitoringHealth from "@/pages/admin/MonitoringHealth";

import Dashboard from "@/pages/tenant/Dashboard";
import AllFindings from "@/pages/tenant/AllFindings";
import SocialMedia from "@/pages/tenant/SocialMedia";
import FakeWebsites from "@/pages/tenant/FakeWebsites";
import DomainIntel from "@/pages/tenant/DomainIntel";
import MobileApps from "@/pages/tenant/MobileApps";
import Executive from "@/pages/tenant/Executive";
import Telegram from "@/pages/tenant/Telegram";
import MetaAds from "@/pages/tenant/MetaAds";
import Cases from "@/pages/tenant/Cases";
import Reports from "@/pages/tenant/Reports";

const FullLoader = () => (
  <div className="flex h-screen items-center justify-center bg-background">
    <Loader2 className="h-7 w-7 animate-spin text-muted-foreground" />
  </div>
);

const RequireAuth = ({ children, roles }) => {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <FullLoader />;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (roles && !roles.includes(user.role)) {
    const fallback = ["super_admin", "tenant_admin"].includes(user.role) ? "/admin" : "/dashboard";
    return <Navigate to={fallback} replace />;
  }
  return <AppShell>{children}</AppShell>;
};

const LandingRedirect = () => {
  const { user, loading } = useAuth();
  if (loading) return <FullLoader />;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={["super_admin", "tenant_admin"].includes(user.role) ? "/admin" : "/dashboard"} replace />;
};

const ADMIN = ["super_admin"];
const ADMIN_OR_TA = ["super_admin", "tenant_admin"];

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <Toaster position="top-right" richColors />
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<LandingRedirect />} />

            {/* Admin Portal */}
            <Route path="/admin" element={<RequireAuth roles={ADMIN_OR_TA}><AdminDashboard /></RequireAuth>} />
            <Route path="/admin/tenants" element={<RequireAuth roles={ADMIN}><Tenants /></RequireAuth>} />
            <Route path="/admin/tenants/:id/wizard" element={<RequireAuth roles={ADMIN}><TenantWizard /></RequireAuth>} />
            <Route path="/admin/monitoring" element={<RequireAuth roles={ADMIN}><MonitoringConfig /></RequireAuth>} />
            <Route path="/admin/sources" element={<RequireAuth roles={ADMIN}><IntelligenceSources /></RequireAuth>} />
            <Route path="/admin/detection" element={<RequireAuth roles={ADMIN}><DetectionConfig /></RequireAuth>} />
            <Route path="/admin/scheduler" element={<RequireAuth roles={ADMIN_OR_TA}><Scheduler /></RequireAuth>} />
            <Route path="/admin/credentials" element={<RequireAuth roles={ADMIN}><Credentials /></RequireAuth>} />
            <Route path="/admin/users" element={<RequireAuth roles={ADMIN_OR_TA}><UsersPage /></RequireAuth>} />
            <Route path="/admin/notifications" element={<RequireAuth roles={ADMIN}><Notifications /></RequireAuth>} />
            <Route path="/admin/audit" element={<RequireAuth roles={ADMIN_OR_TA}><AuditLogs /></RequireAuth>} />
            <Route path="/admin/settings" element={<RequireAuth roles={ADMIN}><SystemSettings /></RequireAuth>} />
            <Route path="/admin/health" element={<RequireAuth roles={ADMIN_OR_TA}><MonitoringHealth /></RequireAuth>} />

            {/* Tenant View */}
            <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
            <Route path="/findings" element={<RequireAuth><AllFindings /></RequireAuth>} />
            <Route path="/findings/social" element={<RequireAuth><SocialMedia /></RequireAuth>} />
            <Route path="/findings/fake-websites" element={<RequireAuth><FakeWebsites /></RequireAuth>} />
            <Route path="/findings/domains" element={<RequireAuth><DomainIntel /></RequireAuth>} />
            <Route path="/findings/mobile-apps" element={<RequireAuth><MobileApps /></RequireAuth>} />
            <Route path="/findings/executive" element={<RequireAuth><Executive /></RequireAuth>} />
            <Route path="/findings/telegram" element={<RequireAuth><Telegram /></RequireAuth>} />
            <Route path="/findings/meta-ads" element={<RequireAuth><MetaAds /></RequireAuth>} />
            <Route path="/cases" element={<RequireAuth><Cases /></RequireAuth>} />
            <Route path="/reports" element={<RequireAuth><Reports /></RequireAuth>} />

            <Route path="*" element={<LandingRedirect />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
