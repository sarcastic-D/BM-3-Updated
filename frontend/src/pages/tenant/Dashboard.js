import React, { useEffect, useState, useCallback, useRef } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/common/PageHeader";
import { Card } from "@/components/ui/card";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  BarChart, Bar, PieChart, Pie, Cell, Legend,
} from "recharts";
import {
  LayoutDashboard, Flame, ShieldAlert, Globe, Users2, Smartphone, Megaphone, UserRound, FolderKanban,
} from "lucide-react";

const COLORS = ["hsl(0 72% 51%)", "hsl(18 88% 52%)", "hsl(38 92% 50%)", "hsl(158 64% 36%)", "hsl(196 84% 33%)", "hsl(222 47% 35%)"];

const Kpi = ({ label, value, icon: Icon, tone }) => (
  <Card className="p-4">
    <div className="flex items-center justify-between">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
      <div className="flex h-8 w-8 items-center justify-center rounded-lg" style={{ background: `${tone}1a`, color: tone }}><Icon className="h-4 w-4" /></div>
    </div>
    <div className="mt-2 text-2xl font-bold tabular-nums">{value ?? 0}</div>
  </Card>
);

export default function Dashboard() {
  const { selectedTenant } = useAuth();
  const [days, setDays] = useState(30);
  const [stats, setStats] = useState(null);
  const reqSeq = useRef(0);

  const load = useCallback(async () => {
    const seq = ++reqSeq.current;
    const params = { days };
    if (selectedTenant !== "All") params.tenant_id = selectedTenant;
    const { data } = await api.get("/dashboard/stats", { params });
    if (seq !== reqSeq.current) return; // ignore stale response
    setStats(data);
  }, [selectedTenant, days]);

  useEffect(() => { load(); }, [load]);

  const c = stats?.cards || {};
  const tooltipStyle = { fontSize: 12, borderRadius: 8, border: "1px solid hsl(214 24% 88%)" };

  return (
    <div>
      <PageHeader
        title="Monitoring Dashboard"
        subtitle="Findings overview across your monitored assets — respects the tenant filter"
        icon={LayoutDashboard}
        actions={
          <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
            <SelectTrigger className="h-9 w-[150px] text-[13px]" data-testid="dashboard-period-select"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
              <SelectItem value="90">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
        }
      />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="Critical" value={c.critical} icon={Flame} tone="hsl(0 72% 51%)" />
        <Kpi label="High" value={c.high} icon={ShieldAlert} tone="hsl(18 88% 52%)" />
        <Kpi label="New Domains" value={c.new_domains} icon={Globe} tone="hsl(196 84% 33%)" />
        <Kpi label="Fake Social" value={c.fake_social} icon={Users2} tone="hsl(222 47% 35%)" />
        <Kpi label="Fake Apps" value={c.fake_apps} icon={Smartphone} tone="hsl(173 58% 39%)" />
        <Kpi label="Unauthorized Ads" value={c.unauthorized_ads} icon={Megaphone} tone="hsl(27 87% 55%)" />
        <Kpi label="Executive Alerts" value={c.executive_alerts} icon={UserRound} tone="hsl(43 74% 46%)" />
        <Kpi label="Open Cases" value={c.open_cases} icon={FolderKanban} tone="hsl(158 64% 36%)" />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="p-4 lg:col-span-2">
          <div className="mb-3 text-[13px] font-semibold">Findings over time</div>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={stats?.timeline || []}>
              <defs>
                <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(196 84% 33%)" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="hsl(196 84% 33%)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(214 24% 90%)" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="count" stroke="hsl(196 84% 33%)" fill="url(#g1)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
        <Card className="p-4">
          <div className="mb-3 text-[13px] font-semibold">Severity distribution</div>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={(stats?.severity_distribution || []).filter((d) => d.value > 0)} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
                {(stats?.severity_distribution || []).map((e, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <div className="mb-3 text-[13px] font-semibold">By module</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={stats?.by_module || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(214 24% 90%)" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-15} textAnchor="end" height={50} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" fill="hsl(196 84% 33%)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card className="p-4">
          <div className="mb-3 text-[13px] font-semibold">Top sources</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={stats?.top_sources || []} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(214 24% 90%)" />
              <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" fill="hsl(173 58% 39%)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
