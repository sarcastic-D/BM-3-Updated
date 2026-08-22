import {
  LayoutDashboard, Building2, SlidersHorizontal, Radar, ShieldAlert, CalendarClock,
  KeyRound, Users, Bell, ScrollText, Settings, Activity, Search, Globe, Smartphone,
  UserRound, Send, Megaphone, FolderKanban, FileBarChart, ListFilter,
} from "lucide-react";

export const adminNav = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, roles: ["super_admin", "tenant_admin"] },
  { to: "/admin/tenants", label: "Tenants", icon: Building2, roles: ["super_admin"] },
  { to: "/admin/monitoring", label: "Monitoring Config", icon: SlidersHorizontal, roles: ["super_admin"] },
  { to: "/admin/sources", label: "Intelligence Sources", icon: Radar, roles: ["super_admin"] },
  { to: "/admin/detection", label: "Detection Config", icon: ShieldAlert, roles: ["super_admin"] },
  { to: "/admin/scheduler", label: "Scheduler", icon: CalendarClock, roles: ["super_admin", "tenant_admin"] },
  { to: "/admin/credentials", label: "Credentials", icon: KeyRound, roles: ["super_admin"] },
  { to: "/admin/users", label: "Users & RBAC", icon: Users, roles: ["super_admin", "tenant_admin"] },
  { to: "/admin/notifications", label: "Notifications", icon: Bell, roles: ["super_admin"] },
  { to: "/admin/audit", label: "Audit Logs", icon: ScrollText, roles: ["super_admin", "tenant_admin"] },
  { to: "/admin/settings", label: "System Settings", icon: Settings, roles: ["super_admin"] },
  { to: "/admin/health", label: "Monitoring Health", icon: Activity, roles: ["super_admin", "tenant_admin"] },
];

export const tenantNav = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["super_admin", "tenant_admin", "analyst", "viewer"] },
  { to: "/findings", label: "All Findings", icon: ListFilter, roles: ["super_admin", "tenant_admin", "analyst", "viewer"] },
  { to: "/findings/social", label: "Social Media", icon: Search, roles: ["super_admin", "tenant_admin", "analyst", "viewer"] },
  { to: "/findings/fake-websites", label: "Fake Websites", icon: Globe, roles: ["super_admin", "tenant_admin", "analyst", "viewer"] },
  { to: "/findings/domains", label: "Domain Intelligence", icon: Radar, roles: ["super_admin", "tenant_admin", "analyst", "viewer"] },
  { to: "/findings/mobile-apps", label: "Mobile Apps", icon: Smartphone, roles: ["super_admin", "tenant_admin", "analyst", "viewer"] },
  { to: "/findings/executive", label: "Executive Monitoring", icon: UserRound, roles: ["super_admin", "tenant_admin", "analyst", "viewer"] },
  { to: "/findings/telegram", label: "Telegram", icon: Send, roles: ["super_admin", "tenant_admin", "analyst", "viewer"] },
  { to: "/findings/meta-ads", label: "Meta Ads", icon: Megaphone, roles: ["super_admin", "tenant_admin", "analyst", "viewer"] },
  { to: "/cases", label: "Cases", icon: FolderKanban, roles: ["super_admin", "tenant_admin", "analyst", "viewer"] },
  { to: "/reports", label: "Reports", icon: FileBarChart, roles: ["super_admin", "tenant_admin", "analyst", "viewer"] },
];

export const roleLabels = {
  super_admin: "Super Admin",
  tenant_admin: "Tenant Admin",
  analyst: "Analyst",
  viewer: "Viewer",
};
