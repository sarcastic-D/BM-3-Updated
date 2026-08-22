import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable } from "@/components/common/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Building2, Plus, MoreVertical, Play, Settings2, CheckCircle2, Search, Trash2, Sparkles, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function Tenants() {
  const nav = useNavigate();
  const { loadTenants } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("All");
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [form, setForm] = useState({ name: "", primary_domain: "", brand_names: "", products: "", industry: "", country: "", timezone: "UTC" });

  const autoDetect = async () => {
    if (!form.primary_domain) { toast.error("Enter the primary domain first"); return; }
    setAnalyzing(true);
    try {
      const { data } = await api.get("/tools/analyze-domain", { params: { domain: form.primary_domain } });
      if (data.error && !data.brand_names.length) { toast.error("Could not analyze domain"); return; }
      setForm((f) => ({
        ...f,
        name: f.name || (data.brand_names[0] || ""),
        brand_names: data.brand_names.join(", "),
        products: data.products.slice(0, 10).join(", "),
      }));
      toast.success(`Detected ${data.brand_names.length} brand(s), ${data.products.length} product(s)`);
    } catch (e) { toast.error("Domain analysis failed"); }
    finally { setAnalyzing(false); }
  };

  const load = useCallback(async () => {
    setLoading(true);
    const params = {};
    if (status !== "All") params.status = status;
    if (search) params.search = search;
    const { data } = await api.get("/tenants", { params });
    setRows(data); setLoading(false);
  }, [status, search]);

  useEffect(() => { load(); }, [load]);

  // Defensively clear any lingering body pointer-events lock left by a closing
  // dropdown/menu so the delete confirmation dialog stays fully interactive.
  useEffect(() => {
    if (toDelete) {
      const id = setTimeout(() => { document.body.style.pointerEvents = ""; }, 50);
      return () => clearTimeout(id);
    }
  }, [toDelete]);

  const create = async () => {
    if (!form.name || !form.primary_domain) { toast.error("Name and primary domain required"); return; }
    try {
      const { data } = await api.post("/tenants", {
        name: form.name, primary_domain: form.primary_domain,
        brand_names: form.brand_names ? form.brand_names.split(",").map((s) => s.trim()).filter(Boolean) : [],
        products: form.products ? form.products.split(",").map((s) => s.trim()).filter(Boolean) : [],
        industry: form.industry, country: form.country, timezone: form.timezone,
      });
      toast.success("Tenant created"); setOpen(false); await loadTenants();
      nav(`/admin/tenants/${data.id}/wizard`);
    } catch (e) { toast.error("Create failed"); }
  };

  const runNow = async (t) => {
    await api.post(`/tenants/${t.id}/run`);
    toast.success(`Monitoring started for ${t.name}`);
  };
  const activate = async (t) => { await api.post(`/tenants/${t.id}/activate`); toast.success("Activated"); load(); loadTenants(); };

  const confirmDelete = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      const { data } = await api.delete(`/tenants/${toDelete.id}`);
      toast.success(`Deleted "${toDelete.name}" (${data.deleted_findings} findings removed)`);
      setRows((p) => p.filter((x) => x.id !== toDelete.id)); // optimistic: remove immediately
      setToDelete(null);
      loadTenants(); // refresh switcher in background
      load();        // reconcile table in background
    } catch (e) {
      toast.error(e.response?.data?.detail || "Delete failed");
    } finally { setDeleting(false); }
  };

  const columns = [
    { key: "name", label: "Tenant", render: (r) => (<div><div className="text-[13px] font-semibold">{r.name}</div><div className="font-mono text-[11px] text-muted-foreground">{r.tenant_id} · {r.primary_domain}</div></div>) },
    { key: "industry", label: "Industry", render: (r) => <span className="text-[12.5px] text-muted-foreground">{r.industry || "—"}</span> },
    { key: "findings", label: "Findings", render: (r) => <span className="tabular-nums text-[12.5px]">{r.findings_count}</span> },
    { key: "monitoring", label: "Monitoring", render: (r) => r.monitoring_enabled ? <Badge className="bg-[hsl(var(--success)/0.12)] text-[hsl(var(--success))] border-[hsl(var(--success)/0.3)]" variant="outline">Enabled</Badge> : <Badge variant="outline" className="text-muted-foreground">Disabled</Badge> },
    { key: "status", label: "Status", render: (r) => <Badge variant="outline">{r.status}</Badge> },
    { key: "actions", label: "", className: "w-24", render: (r) => (
      <div className="flex items-center justify-end gap-0.5" onClick={(e) => e.stopPropagation()}>
        <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-[hsl(var(--destructive))]" title="Delete tenant" data-testid="tenant-delete-button" onClick={() => setToDelete(r)}>
          <Trash2 className="h-4 w-4" />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild><Button variant="ghost" size="sm" data-testid="tenant-actions-button"><MoreVertical className="h-4 w-4" /></Button></DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => nav(`/admin/tenants/${r.id}/wizard`)}><Settings2 className="mr-2 h-4 w-4" /> Configure</DropdownMenuItem>
            <DropdownMenuItem onClick={() => runNow(r)}><Play className="mr-2 h-4 w-4" /> Run monitoring now</DropdownMenuItem>
            {!r.monitoring_enabled && <DropdownMenuItem onClick={() => activate(r)}><CheckCircle2 className="mr-2 h-4 w-4" /> Activate</DropdownMenuItem>}
            <DropdownMenuItem onSelect={(e) => { e.preventDefault(); setTimeout(() => setToDelete(r), 120); }} className="text-[hsl(var(--destructive))] focus:text-[hsl(var(--destructive))]" data-testid="tenant-delete-menu-item"><Trash2 className="mr-2 h-4 w-4" /> Delete tenant</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    ) },
  ];

  return (
    <div>
      <PageHeader title="Tenants" subtitle="Create and configure monitored organizations" icon={Building2}
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button className="gap-1.5" data-testid="create-tenant-button"><Plus className="h-4 w-4" /> Create Tenant</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Create Tenant</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <div><Label className="text-[12px]">Tenant Name *</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Acme Corporation" data-testid="tenant-name-input" /></div>
                <div>
                  <Label className="text-[12px]">Primary Domain *</Label>
                  <div className="flex gap-2">
                    <Input value={form.primary_domain} onChange={(e) => setForm({ ...form, primary_domain: e.target.value })} placeholder="acme.com" data-testid="tenant-domain-input" />
                    <Button type="button" variant="outline" onClick={autoDetect} disabled={analyzing} className="shrink-0 gap-1.5" data-testid="tenant-autodetect-button">
                      {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Auto-detect
                    </Button>
                  </div>
                  <p className="mt-1 text-[11px] text-muted-foreground">Analyze the domain to auto-fill brand aliases & products, or enter them manually below.</p>
                </div>
                <div><Label className="text-[12px]">Brand Names / Aliases (comma separated)</Label><Input value={form.brand_names} onChange={(e) => setForm({ ...form, brand_names: e.target.value })} placeholder="Acme, AcmeCorp" data-testid="tenant-brands-input" /></div>
                <div><Label className="text-[12px]">Products (comma separated)</Label><Input value={form.products} onChange={(e) => setForm({ ...form, products: e.target.value })} placeholder="Product A, Product B" data-testid="tenant-products-input" /></div>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="text-[12px]">Industry</Label><Input value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} /></div>
                  <div><Label className="text-[12px]">Country</Label><Input value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} /></div>
                </div>
              </div>
              <DialogFooter><Button onClick={create} data-testid="create-tenant-confirm-button">Create & Configure</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search tenants" className="h-9 w-[240px] pl-8 text-[13px]" data-testid="tenants-search-input" /></div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="h-9 w-[150px] text-[13px]"><SelectValue /></SelectTrigger>
          <SelectContent>{["All", "Active", "Inactive"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <DataTable columns={columns} rows={rows} loading={loading} testid="tenants-table" onRowClick={(r) => nav(`/admin/tenants/${r.id}/wizard`)} />

      <Dialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Delete tenant?</DialogTitle></DialogHeader>
          {toDelete && (
            <p className="text-[13px] text-muted-foreground">
              This permanently deletes <span className="font-semibold text-foreground">{toDelete.name}</span> ({toDelete.tenant_id}) and all of its data — <span className="font-semibold text-foreground">{toDelete.findings_count} findings</span>, related cases, and monitoring history. Users will lose access to it. This cannot be undone.
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setToDelete(null)} disabled={deleting}>Cancel</Button>
            <Button className="bg-[hsl(var(--destructive))] text-white hover:bg-[hsl(var(--destructive)/0.9)]" onClick={confirmDelete} disabled={deleting} data-testid="tenant-delete-confirm-button">
              {deleting ? "Deleting…" : "Delete permanently"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
