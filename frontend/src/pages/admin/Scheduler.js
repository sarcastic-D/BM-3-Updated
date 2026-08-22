import React, { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable } from "@/components/common/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { CalendarClock, Play } from "lucide-react";
import { toast } from "sonner";

export default function Scheduler() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const { data } = await api.get("/schedules"); setRows(data); setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);

  const update = async (r, patch) => {
    const sched = { ...(r.schedule || {}), ...patch };
    await api.put(`/schedules/${r.id}`, sched);
    setRows((p) => p.map((x) => x.id === r.id ? { ...x, schedule: sched } : x));
  };
  const runNow = async (r) => { await api.post(`/tenants/${r.id}/run`); toast.success(`Monitoring started for ${r.name}`); };

  const columns = [
    { key: "name", label: "Tenant", render: (r) => <span className="text-[13px] font-medium">{r.name}</span> },
    { key: "interval", label: "Interval (hrs)", render: (r) => (
      <Input type="number" value={r.schedule?.interval_hours || 24} onChange={(e) => update(r, { interval_hours: Number(e.target.value) })} className="h-8 w-20 text-[12px]" />) },
    { key: "enabled", label: "Enabled", render: (r) => <Switch checked={!!r.schedule?.enabled} onCheckedChange={(v) => update(r, { enabled: v })} data-testid="schedule-toggle" /> },
    { key: "last_scan", label: "Last Scan", render: (r) => <span className="text-[12px] text-muted-foreground tabular-nums">{r.last_scan?.slice(0, 19).replace("T", " ") || "Never"}</span> },
    { key: "run", label: "", render: (r) => <Button size="sm" variant="outline" className="gap-1.5" onClick={() => runNow(r)} data-testid="scheduler-run-button"><Play className="h-3.5 w-3.5" /> Run now</Button> },
  ];

  return (
    <div>
      <PageHeader title="Scheduler" subtitle="Automated scan intervals per tenant" icon={CalendarClock} />
      <DataTable columns={columns} rows={rows} loading={loading} testid="scheduler-table" />
    </div>
  );
}
