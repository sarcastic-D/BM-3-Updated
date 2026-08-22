import React, { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable } from "@/components/common/DataTable";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollText, Search } from "lucide-react";

export default function AuditLogs() {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const { data } = await api.get("/audit-logs", { params: { page, page_size: 25, search: search || undefined } });
    setRows(data.items); setTotal(data.total); setLoading(false);
  }, [page, search]);
  useEffect(() => { load(); }, [load]);

  const columns = [
    { key: "ts", label: "Time", render: (r) => <span className="font-mono text-[12px] text-muted-foreground">{r.ts?.slice(0, 19).replace("T", " ")}</span> },
    { key: "actor", label: "Actor", render: (r) => (<div><div className="text-[12.5px] font-medium">{r.actor}</div><div className="text-[11px] text-muted-foreground">{r.role}</div></div>) },
    { key: "action", label: "Action", render: (r) => <Badge variant="outline">{r.action?.replace(/_/g, " ")}</Badge> },
    { key: "target", label: "Target", render: (r) => <span className="text-[12.5px]">{r.target || "—"}</span> },
    { key: "detail", label: "Detail", render: (r) => <span className="text-[11.5px] text-muted-foreground">{r.detail || "—"}</span> },
  ];

  return (
    <div>
      <PageHeader title="Audit Logs" subtitle="Immutable record of configuration and investigation actions" icon={ScrollText} />
      <div className="mb-4 relative w-[280px]"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input value={search} onChange={(e) => { setPage(1); setSearch(e.target.value); }} placeholder="Search actor / action / target" className="h-9 pl-8 text-[13px]" data-testid="audit-search-input" /></div>
      <DataTable columns={columns} rows={rows} loading={loading} total={total} page={page} pageSize={25} onPageChange={setPage} testid="audit-table" />
    </div>
  );
}
