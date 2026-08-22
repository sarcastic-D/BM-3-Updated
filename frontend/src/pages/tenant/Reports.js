import React, { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/common/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileBarChart, Download, FileText } from "lucide-react";
import { toast } from "sonner";

export default function Reports() {
  const { selectedTenant, tenants } = useAuth();
  const [stats, setStats] = useState(null);

  const load = useCallback(async () => {
    const params = { days: 90 };
    if (selectedTenant !== "All") params.tenant_id = selectedTenant;
    const { data } = await api.get("/dashboard/stats", { params });
    setStats(data);
  }, [selectedTenant]);

  useEffect(() => { load(); }, [load]);

  const exportCsv = async () => {
    try {
      const params = {};
      if (selectedTenant !== "All") params.tenant_id = selectedTenant;
      const res = await api.get("/findings/export", { params, responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url; a.download = "brand-monitoring-report.csv"; a.click();
      toast.success("Report exported");
    } catch (e) { toast.error("Export failed"); }
  };

  const exportPdf = async () => {
    try {
      const params = {};
      if (selectedTenant !== "All") params.tenant_id = selectedTenant;
      const res = await api.get("/findings/report.pdf", { params, responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url; a.download = "brand-monitoring-report.pdf"; a.click();
      toast.success("PDF report generated");
    } catch (e) { toast.error("PDF export failed"); }
  };

  const c = stats?.cards || {};
  const tenantName = selectedTenant === "All" ? "All Tenants" : tenants.find((t) => t.id === selectedTenant)?.name;

  return (
    <div>
      <PageHeader
        title="Reports"
        subtitle="Executive summary and data export"
        icon={FileBarChart}
        actions={<div className="flex gap-2">
          <Button variant="outline" onClick={exportCsv} className="gap-1.5" data-testid="reports-export-button"><Download className="h-4 w-4" /> Export CSV</Button>
          <Button onClick={exportPdf} className="gap-1.5" data-testid="reports-export-pdf-button"><FileText className="h-4 w-4" /> Export PDF</Button>
        </div>}
      />
      <Card className="p-6">
        <div className="text-[13px] text-muted-foreground">Report scope</div>
        <div className="text-lg font-semibold">{tenantName}</div>
        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          {[["Total findings", c.total], ["Critical", c.critical], ["High", c.high], ["New domains (90d)", c.new_domains],
            ["Fake social", c.fake_social], ["Open cases", c.open_cases], ["Medium", c.medium], ["Low", c.low]].map(([l, v]) => (
            <div key={l} className="rounded-lg border border-border bg-[hsl(var(--surface-2))] p-3">
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{l}</div>
              <div className="mt-1 text-xl font-bold tabular-nums">{v ?? 0}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
