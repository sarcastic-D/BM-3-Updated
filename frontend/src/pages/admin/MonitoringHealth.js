import React, { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable } from "@/components/common/DataTable";
import { HealthPill } from "@/components/common/Pills";
import { Button } from "@/components/ui/button";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { Activity, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function MonitoringHealth() {
  const { selectedTenant } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    const params = {};
    if (selectedTenant !== "All") params.tenant_id = selectedTenant;
    const { data } = await api.get("/monitoring-health", { params });
    setRows(data); setLoading(false);
  }, [selectedTenant]);

  useEffect(() => { load(); }, [load]);

  const rerun = async (r) => {
    await api.post(`/tenants/${r.tenant_id}/run`, null, { params: { collector: r.collector_key } });
    toast.success(`Re-running ${r.collector}`);
    setTimeout(load, 4000);
  };

  const columns = [
    { key: "tenant_name", label: "Tenant", render: (r) => <span className="text-[13px] font-medium">{r.tenant_name}</span> },
    { key: "collector", label: "Collector", render: (r) => <span className="text-[13px]">{r.collector}</span> },
    { key: "last_run", label: "Last Run", render: (r) => <span className="text-[12px] text-muted-foreground tabular-nums">{r.last_run?.slice(0, 19).replace("T", " ")}</span> },
    { key: "items_found", label: "Found", render: (r) => <span className="tabular-nums text-[12.5px]">{r.items_found ?? "—"}</span> },
    { key: "new_findings", label: "New", render: (r) => <span className="tabular-nums text-[12.5px]">{r.new_findings ?? "—"}</span> },
    { key: "status", label: "Status", render: (r) => <HealthPill value={r.status} /> },
  ];

  return (
    <div>
      <PageHeader title="Monitoring Health" subtitle="Collector status across tenants — click a row to inspect" icon={Activity}
        actions={<Button variant="outline" onClick={load} className="gap-1.5"><RefreshCw className="h-4 w-4" /> Refresh</Button>} />
      <DataTable columns={columns} rows={rows} loading={loading} testid="monitoring-health-table" onRowClick={setActive} emptyText="No collector runs yet" />
      <Sheet open={!!active} onOpenChange={(o) => !o && setActive(null)}>
        <SheetContent className="w-full sm:max-w-[520px]">
          {active && (<div>
            <SheetHeader><div className="flex items-center gap-2"><HealthPill value={active.status} /></div><SheetTitle className="text-left">{active.collector}</SheetTitle></SheetHeader>
            <div className="mt-4 space-y-2 rounded-lg border border-border bg-[hsl(var(--surface-2))] p-3 text-[12.5px]">
              <div className="flex justify-between"><span className="text-muted-foreground">Tenant</span><span className="font-medium">{active.tenant_name}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Last run</span><span className="font-mono">{active.last_run?.slice(0, 19).replace("T", " ")}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Last success</span><span className="font-mono">{active.last_success?.slice(0, 19).replace("T", " ") || "—"}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Duration</span><span className="font-mono">{active.duration_ms} ms</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Items found</span><span className="tabular-nums">{active.items_found}</span></div>
            </div>
            {active.error && <div className="mt-3 rounded-lg border border-[hsl(var(--destructive)/0.3)] bg-[hsl(var(--destructive)/0.08)] p-3 text-[12px] text-[hsl(var(--destructive))]">Error: {active.error}</div>}
            <Button className="mt-4 gap-1.5" onClick={() => rerun(active)} data-testid="health-rerun-button"><RefreshCw className="h-4 w-4" /> Re-run collector</Button>
          </div>)}
        </SheetContent>
      </Sheet>
    </div>
  );
}
