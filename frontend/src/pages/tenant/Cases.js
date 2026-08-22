import React, { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable } from "@/components/common/DataTable";
import { StatusPill } from "@/components/common/Pills";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { FolderKanban, Search } from "lucide-react";
import { toast } from "sonner";

const CASE_STATUS = ["All", "Open", "In Progress", "Waiting", "Closed"];

export default function Cases() {
  const { selectedTenant, canWrite, tenants } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("All");
  const [search, setSearch] = useState("");
  const [active, setActive] = useState(null);
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const params = {};
    if (selectedTenant !== "All") params.tenant_id = selectedTenant;
    if (status !== "All") params.status = status;
    if (search) params.search = search;
    const { data } = await api.get("/cases", { params });
    setRows(data); setLoading(false);
  }, [selectedTenant, status, search]);

  useEffect(() => { load(); }, [load]);

  const openCase = async (row) => {
    const { data } = await api.get(`/cases/${row.id}`);
    setActive(data);
  };

  const changeStatus = async (s) => {
    await api.put(`/cases/${active.id}`, { status: s });
    setActive((p) => ({ ...p, status: s }));
    toast.success(`Case → ${s}`); load();
  };

  const addNote = async () => {
    if (!note.trim()) return;
    await api.put(`/cases/${active.id}`, { note });
    const { data } = await api.get(`/cases/${active.id}`);
    setActive(data); setNote("");
  };

  const tName = (id) => tenants.find((t) => t.id === id)?.name || "—";

  const columns = [
    { key: "case_number", label: "Case", render: (r) => <span className="font-mono text-[12.5px] font-semibold">{r.case_number}</span> },
    { key: "title", label: "Title", render: (r) => <span className="text-[13px]">{r.title}</span> },
    { key: "tenant", label: "Tenant", render: (r) => <span className="text-[12.5px] text-muted-foreground">{tName(r.tenant_id)}</span> },
    { key: "priority", label: "Priority", render: (r) => <Badge variant="outline">{r.priority}</Badge> },
    { key: "status", label: "Status", render: (r) => <StatusPill value={r.status} /> },
    { key: "findings", label: "Findings", render: (r) => <span className="tabular-nums text-[12.5px]">{r.finding_ids?.length || 0}</span> },
    { key: "created_at", label: "Created", render: (r) => <span className="text-[12px] text-muted-foreground">{r.created_at?.slice(0, 10)}</span> },
  ];

  return (
    <div>
      <PageHeader title="Cases" subtitle="Investigation cases created from findings" icon={FolderKanban} />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search cases" className="h-9 w-[240px] pl-8 text-[13px]" data-testid="cases-search-input" />
        </div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="h-9 w-[160px] text-[13px]" data-testid="cases-status-filter"><SelectValue /></SelectTrigger>
          <SelectContent>{CASE_STATUS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <DataTable columns={columns} rows={rows} loading={loading} onRowClick={openCase} testid="cases-table" emptyText="No cases yet — create one from a finding" />

      <Sheet open={!!active} onOpenChange={(o) => !o && setActive(null)}>
        <SheetContent className="w-full sm:max-w-[560px] overflow-y-auto">
          {active && (
            <div>
              <SheetHeader>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[13px] font-semibold">{active.case_number}</span>
                  <StatusPill value={active.status} />
                  <Badge variant="outline">{active.priority}</Badge>
                </div>
                <SheetTitle className="text-left">{active.title}</SheetTitle>
              </SheetHeader>
              <div className="mt-4 space-y-4">
                {canWrite && (
                  <div>
                    <div className="mb-1 text-[12px] text-muted-foreground">Status</div>
                    <Select value={active.status} onValueChange={changeStatus}>
                      <SelectTrigger className="h-9 text-[13px]" data-testid="case-status-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{["Open", "In Progress", "Waiting", "Closed"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                )}
                <div>
                  <div className="mb-2 text-[13px] font-semibold">Linked findings ({active.findings?.length || 0})</div>
                  <div className="space-y-1.5">
                    {(active.findings || []).map((f) => (
                      <div key={f.id} className="rounded-lg border border-border bg-[hsl(var(--surface-2))] p-2">
                        <div className="font-mono text-[12px]">{f.title}</div>
                        <div className="text-[11px] text-muted-foreground">{f.category} · {f.severity} · risk {f.risk_score}</div>
                      </div>
                    ))}
                    {(!active.findings || active.findings.length === 0) && <div className="text-[12px] text-muted-foreground">No linked findings</div>}
                  </div>
                </div>
                <div>
                  <div className="mb-2 text-[13px] font-semibold">Notes</div>
                  <div className="space-y-1.5">
                    {(active.notes || []).map((n, i) => (
                      <div key={i} className="rounded-lg border border-border p-2">
                        <div className="text-[12.5px]">{n.text}</div>
                        <div className="text-[11px] text-muted-foreground">{n.author} · {n.ts?.slice(0, 16).replace("T", " ")}</div>
                      </div>
                    ))}
                  </div>
                  {canWrite && (
                    <div className="mt-2 flex gap-2">
                      <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a note" className="text-[13px]" data-testid="case-note-input" />
                      <Button onClick={addNote} data-testid="case-add-note-button">Add</Button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
