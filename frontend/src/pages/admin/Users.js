import React, { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
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
  Popover, PopoverContent, PopoverTrigger,
} from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useAuth } from "@/context/AuthContext";
import { roleLabels } from "@/constants/navConfig";
import { Users, Plus, Building2 } from "lucide-react";
import { toast } from "sonner";

export default function UsersPage() {
  const { tenants } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "analyst" });

  const load = useCallback(async () => {
    setLoading(true);
    const { data } = await api.get("/users"); setRows(data); setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!form.name || !form.email || !form.password) { toast.error("All fields required"); return; }
    try {
      const payload = { ...form };
      if (form.role !== "super_admin") payload.tenant_ids = tenants.map((t) => t.id);
      await api.post("/users", payload); toast.success("User created"); setOpen(false); setForm({ name: "", email: "", password: "", role: "analyst" }); load();
    }
    catch (e) { toast.error(e.response?.data?.detail || "Create failed"); }
  };

  const setRole = async (u, role) => { await api.put(`/users/${u.id}`, { role }); toast.success("Role updated"); load(); };
  const toggleStatus = async (u) => { await api.put(`/users/${u.id}`, { status: u.status === "Active" ? "Inactive" : "Active" }); load(); };

  const toggleTenant = async (u, tid) => {
    const cur = u.tenant_ids || [];
    const next = cur.includes(tid) ? cur.filter((x) => x !== tid) : [...cur, tid];
    await api.put(`/users/${u.id}`, { tenant_ids: next });
    setRows((p) => p.map((x) => x.id === u.id ? { ...x, tenant_ids: next } : x));
    toast.success("Tenant access updated");
  };

  const TenantAccess = ({ u }) => {
    if (u.role === "super_admin") return <Badge variant="outline" className="text-[hsl(var(--primary))] border-[hsl(var(--primary)/0.3)]">All tenants</Badge>;
    const count = (u.tenant_ids || []).length;
    return (
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 gap-1.5 text-[12px]" data-testid="user-tenant-access-button">
            <Building2 className="h-3.5 w-3.5" /> {count} tenant{count === 1 ? "" : "s"}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-64 p-2">
          <div className="mb-1 px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Tenant access</div>
          <ScrollArea className="max-h-56">
            <div className="space-y-0.5">
              {tenants.map((t) => (
                <label key={t.id} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] hover:bg-[hsl(var(--surface-3))]">
                  <Checkbox checked={(u.tenant_ids || []).includes(t.id)} onCheckedChange={() => toggleTenant(u, t.id)} data-testid={`user-tenant-checkbox-${t.tenant_id}`} />
                  <span className="truncate">{t.name}</span>
                </label>
              ))}
              {tenants.length === 0 && <div className="px-2 py-2 text-[12px] text-muted-foreground">No tenants</div>}
            </div>
          </ScrollArea>
        </PopoverContent>
      </Popover>
    );
  };

  const columns = [
    { key: "name", label: "User", render: (r) => (<div><div className="text-[13px] font-semibold">{r.name}</div><div className="text-[11px] text-muted-foreground">{r.email}</div></div>) },
    { key: "role", label: "Role", render: (r) => (
      <Select value={r.role} onValueChange={(v) => setRole(r, v)}>
        <SelectTrigger className="h-8 w-[150px] text-[12px]" data-testid="user-role-select"><SelectValue /></SelectTrigger>
        <SelectContent>{Object.entries(roleLabels).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
      </Select>) },
    { key: "tenant_access", label: "Tenant Access", render: (r) => <TenantAccess u={r} /> },
    { key: "status", label: "Status", render: (r) => <Badge variant="outline" className={r.status === "Active" ? "text-[hsl(var(--success))] border-[hsl(var(--success)/0.3)]" : "text-muted-foreground"}>{r.status}</Badge> },
    { key: "actions", label: "", render: (r) => <Button variant="ghost" size="sm" className="text-[12px]" onClick={() => toggleStatus(r)}>{r.status === "Active" ? "Deactivate" : "Activate"}</Button> },
  ];

  return (
    <div>
      <PageHeader title="Users & RBAC" subtitle="Manage platform users and role-based access" icon={Users}
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button className="gap-1.5" data-testid="create-user-button"><Plus className="h-4 w-4" /> Add User</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Add User</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <div><Label className="text-[12px]">Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="user-name-input" /></div>
                <div><Label className="text-[12px]">Email</Label><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="user-email-input" /></div>
                <div><Label className="text-[12px]">Password</Label><Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="user-password-input" /></div>
                <div><Label className="text-[12px]">Role</Label>
                  <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{Object.entries(roleLabels).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter><Button onClick={create} data-testid="create-user-confirm-button">Create User</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        } />
      <DataTable columns={columns} rows={rows} loading={loading} testid="users-table" />
    </div>
  );
}
