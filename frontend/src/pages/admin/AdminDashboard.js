import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { Card } from "@/components/ui/card";
import { HealthPill } from "@/components/common/Pills";
import { Link } from "react-router-dom";
import { LayoutDashboard, Building2, ListChecks, Activity, ScrollText, ArrowRight } from "lucide-react";

const Kpi = ({ label, value, icon: Icon, tone }) => (
  <Card className="p-4">
    <div className="flex items-center justify-between">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
      <div className="flex h-8 w-8 items-center justify-center rounded-lg" style={{ background: `${tone}1a`, color: tone }}><Icon className="h-4 w-4" /></div>
    </div>
    <div className="mt-2 text-2xl font-bold tabular-nums">{value ?? 0}</div>
  </Card>
);

export default function AdminDashboard() {
  const [tenants, setTenants] = useState([]);
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState([]);
  const [audit, setAudit] = useState([]);

  useEffect(() => {
    api.get("/tenants").then(({ data }) => setTenants(data));
    api.get("/dashboard/stats", { params: { days: 30 } }).then(({ data }) => setStats(data));
    api.get("/monitoring-health").then(({ data }) => setHealth(data));
    api.get("/audit-logs", { params: { page_size: 8 } }).then(({ data }) => setAudit(data.items)).catch(() => {});
  }, []);

  const c = stats?.cards || {};
  const activeTenants = tenants.filter((t) => t.monitoring_enabled).length;

  return (
    <div>
      <PageHeader title="Admin Dashboard" subtitle="Platform-wide monitoring posture and configuration health" icon={LayoutDashboard} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="Tenants" value={tenants.length} icon={Building2} tone="hsl(196 84% 33%)" />
        <Kpi label="Active Monitoring" value={activeTenants} icon={Activity} tone="hsl(158 64% 36%)" />
        <Kpi label="Total Findings" value={c.total} icon={ListChecks} tone="hsl(222 47% 35%)" />
        <Kpi label="Critical" value={c.critical} icon={Activity} tone="hsl(0 72% 51%)" />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[13px] font-semibold">Monitoring Health</span>
            <Link to="/admin/health" className="flex items-center gap-1 text-[12px] text-[hsl(var(--primary))] hover:underline">View all <ArrowRight className="h-3 w-3" /></Link>
          </div>
          <div className="space-y-1.5">
            {health.slice(0, 6).map((h, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
                <div><div className="text-[12.5px] font-medium">{h.collector}</div><div className="text-[11px] text-muted-foreground">{h.tenant_name}</div></div>
                <HealthPill value={h.status} />
              </div>
            ))}
            {health.length === 0 && <div className="py-6 text-center text-[12px] text-muted-foreground">No collector runs yet</div>}
          </div>
        </Card>
        <Card className="p-4">
          <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold"><ScrollText className="h-4 w-4" /> Recent Activity</div>
          <div className="space-y-1.5">
            {audit.map((a) => (
              <div key={a.id} className="flex items-center justify-between border-b border-border/60 py-1.5 last:border-0">
                <div><span className="text-[12.5px] font-medium">{a.actor}</span> <span className="text-[12px] text-muted-foreground">{a.action.replace(/_/g, " ")}</span> <span className="text-[12px]">{a.target}</span></div>
                <span className="text-[11px] text-muted-foreground tabular-nums">{a.ts?.slice(11, 16)}</span>
              </div>
            ))}
            {audit.length === 0 && <div className="py-6 text-center text-[12px] text-muted-foreground">No activity</div>}
          </div>
        </Card>
      </div>
    </div>
  );
}
