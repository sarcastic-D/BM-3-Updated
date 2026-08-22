import React from "react";
import { NavLink, useLocation } from "react-router-dom";
import { adminNav, tenantNav, roleLabels } from "@/constants/navConfig";
import { useAuth } from "@/context/AuthContext";
import { ShieldHalf } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

const NavItem = ({ item }) => (
  <NavLink
    to={item.to}
    end={item.to === "/admin"}
    data-testid={`sidebar-nav-${item.label.toLowerCase().replace(/[^a-z]+/g, "-")}-link`}
    className={({ isActive }) =>
      `group flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors duration-150 ${
        isActive
          ? "bg-[hsl(var(--accent))] text-[hsl(var(--accent-foreground))]"
          : "text-muted-foreground hover:bg-[hsl(var(--surface-3))] hover:text-foreground"
      }`
    }
  >
    {({ isActive }) => (
      <>
        <span className={`h-4 w-0.5 rounded-full ${isActive ? "bg-[hsl(var(--primary))]" : "bg-transparent"}`} />
        <item.icon className="h-4 w-4 shrink-0" />
        <span className="truncate">{item.label}</span>
      </>
    )}
  </NavLink>
);

const Group = ({ title, items, role }) => {
  const visible = items.filter((i) => i.roles.includes(role));
  if (!visible.length) return null;
  return (
    <div className="px-2">
      <div className="px-3 pb-1.5 pt-4 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/70">{title}</div>
      <div className="space-y-0.5">
        {visible.map((i) => (
          <NavItem key={i.to} item={i} />
        ))}
      </div>
    </div>
  );
};

export const Sidebar = () => {
  const { user } = useAuth();
  const role = user?.role;
  return (
    <aside className="hidden md:flex w-[264px] shrink-0 flex-col border-r border-border bg-card">
      <div className="flex h-14 items-center gap-2.5 border-b border-border px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[hsl(var(--primary))] text-white">
          <ShieldHalf className="h-4.5 w-4.5" />
        </div>
        <div className="leading-tight">
          <div className="text-[14px] font-bold tracking-tight">BrandShield</div>
          <div className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">DRP Console</div>
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="pb-6">
          <Group title="Admin Portal" items={adminNav} role={role} />
          <Group title="Tenant View" items={tenantNav} role={role} />
        </div>
      </ScrollArea>
      <div className="border-t border-border p-3">
        <div className="rounded-lg bg-[hsl(var(--surface-2))] px-3 py-2">
          <div className="text-[12px] font-semibold">{user?.name}</div>
          <div className="text-[11px] text-muted-foreground">{roleLabels[role]}</div>
        </div>
      </div>
    </aside>
  );
};
