import React, { useCallback, useEffect, useState, useRef } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/common/PageHeader";
import { FilterBar } from "@/components/common/FilterBar";
import { DataTable } from "@/components/common/DataTable";
import { FindingDrawer } from "@/components/common/FindingDrawer";
import { SeverityPill, StatusPill, RiskBar } from "@/components/common/Pills";
import { toast } from "sonner";

const defaultColumns = [
  { key: "title", label: "Finding", sortable: true, render: (r) => (
      <div className="max-w-[280px]">
        <div className="truncate font-mono text-[12.5px] font-medium">{r.title}</div>
        <div className="truncate text-[11px] text-muted-foreground">{r.category}</div>
      </div>
    ) },
  { key: "platform", label: "Platform", render: (r) => <span className="text-[12.5px]">{r.platform}</span> },
  { key: "source", label: "Source", render: (r) => <span className="text-[12.5px]">{r.source}</span> },
  { key: "severity", label: "Severity", sortable: true, render: (r) => <SeverityPill value={r.severity} /> },
  { key: "risk_score", label: "Risk", sortable: true, render: (r) => <RiskBar value={r.risk_score} /> },
  { key: "status", label: "Status", render: (r) => <StatusPill value={r.status} /> },
  { key: "first_seen", label: "First Seen", sortable: true, render: (r) => <span className="text-[12px] text-muted-foreground tabular-nums">{r.first_seen?.slice(0, 10)}</span> },
];

export const FindingsPage = ({
  module = null, title, subtitle, icon, moduleFilters = [], booleanFilters = [],
  platformOptions, columns = defaultColumns, screen,
}) => {
  const { selectedTenant } = useAuth();
  const [filters, setFilters] = useState({});
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("first_seen");
  const [sortDir, setSortDir] = useState("desc");
  const [drawerId, setDrawerId] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const pageSize = 25;
  const reqSeq = useRef(0);

  const fetchData = useCallback(async (f, pg, sb, sd) => {
    const seq = ++reqSeq.current;
    setLoading(true);
    try {
      const params = { ...f, page: pg, page_size: pageSize, sort_by: sb, sort_dir: sd };
      if (module) params.module = module;
      const { data } = await api.get("/findings", { params });
      // Ignore stale responses: only the most recent request may update state.
      // Prevents a slow "all tenants" response from overwriting a filtered one.
      if (seq !== reqSeq.current) return;
      setRows(data.items); setTotal(data.total);
    } catch (e) {
      if (seq === reqSeq.current) toast.error("Failed to load findings");
    } finally {
      if (seq === reqSeq.current) setLoading(false);
    }
  }, [module]);

  useEffect(() => { fetchData(filters, page, sortBy, sortDir); }, [filters, page, sortBy, sortDir, fetchData]);

  const onApply = (f) => { setPage(1); setFilters(f); };
  const onSort = (key) => {
    if (sortBy === key) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortBy(key); setSortDir("desc"); }
  };

  const onExport = async () => {
    try {
      const params = { ...filters };
      if (module) params.module = module;
      const res = await api.get("/findings/export", { params, responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url; a.download = `${screen || "findings"}.csv`; a.click();
      window.URL.revokeObjectURL(url);
      toast.success("Export ready");
    } catch (e) { toast.error("Export failed"); }
  };

  const onExportPdf = async () => {
    try {
      const params = { ...filters };
      if (module) params.module = module;
      const res = await api.get("/findings/report.pdf", { params, responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url; a.download = `${screen || "findings"}-report.pdf`; a.click();
      window.URL.revokeObjectURL(url);
      toast.success("PDF report ready");
    } catch (e) { toast.error("PDF export failed"); }
  };

  return (
    <div>
      <PageHeader title={title} subtitle={subtitle} icon={icon} />
      <FilterBar
        screen={screen || module || "findings"}
        moduleFilters={moduleFilters}
        booleanFilters={booleanFilters}
        platformOptions={platformOptions}
        onApply={onApply}
        onExport={onExport}
        onExportPdf={onExportPdf}
      />
      <DataTable
        columns={columns}
        rows={rows}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        sortBy={sortBy}
        sortDir={sortDir}
        onSort={onSort}
        onRowClick={(r) => { setDrawerId(r.id); setDrawerOpen(true); }}
        testid="findings-table"
      />
      <FindingDrawer
        findingId={drawerId}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        onUpdated={() => fetchData(filters, page, sortBy, sortDir)}
      />
    </div>
  );
};
