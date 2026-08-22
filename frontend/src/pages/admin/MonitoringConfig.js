import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { SlidersHorizontal, Save } from "lucide-react";
import { toast } from "sonner";

const Toggle = ({ label, checked, onChange }) => (
  <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2.5">
    <span className="text-[13px] capitalize">{label.replace(/_/g, " ")}</span>
    <Switch checked={!!checked} onCheckedChange={onChange} />
  </div>
);

export default function MonitoringConfig() {
  const [tenants, setTenants] = useState([]);
  const [tid, setTid] = useState("");
  const [t, setT] = useState(null);

  useEffect(() => { api.get("/tenants").then(({ data }) => { setTenants(data); if (data[0]) setTid(data[0].id); }); }, []);
  useEffect(() => { if (tid) api.get(`/tenants/${tid}`).then(({ data }) => setT(data)); }, [tid]);

  const patchMon = (path, val) => setT((p) => {
    const mc = JSON.parse(JSON.stringify(p.monitoring_config));
    const parts = path.split("."); let cur = mc;
    for (let i = 0; i < parts.length - 1; i++) cur = cur[parts[i]];
    cur[parts[parts.length - 1]] = val; return { ...p, monitoring_config: mc };
  });

  const save = async () => { await api.put(`/tenants/${tid}`, { monitoring_config: t.monitoring_config }); toast.success("Monitoring configuration saved"); };

  const mc = t?.monitoring_config;

  return (
    <div>
      <PageHeader title="Monitoring Configuration" subtitle="Enable or disable collectors per tenant — workers read this live" icon={SlidersHorizontal}
        actions={t && <Button onClick={save} className="gap-1.5" data-testid="monitoring-save-button"><Save className="h-4 w-4" /> Save</Button>} />
      <div className="mb-4 w-[280px]">
        <Select value={tid} onValueChange={setTid}>
          <SelectTrigger className="h-9 text-[13px]" data-testid="monitoring-tenant-select"><SelectValue placeholder="Select tenant" /></SelectTrigger>
          <SelectContent>{tenants.map((x) => <SelectItem key={x.id} value={x.id}>{x.name}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      {mc && (
        <Card className="p-5">
          <Tabs defaultValue="domains">
            <TabsList>
              <TabsTrigger value="domains">Domains</TabsTrigger>
              <TabsTrigger value="social">Social</TabsTrigger>
              <TabsTrigger value="mobile">Mobile Apps</TabsTrigger>
              <TabsTrigger value="other">Other</TabsTrigger>
            </TabsList>
            <TabsContent value="domains" className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-3">{Object.keys(mc.domains).map((k) => <Toggle key={k} label={k} checked={mc.domains[k]} onChange={(v) => patchMon(`domains.${k}`, v)} />)}</TabsContent>
            <TabsContent value="social" className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-3">{Object.keys(mc.social).map((k) => <Toggle key={k} label={k} checked={mc.social[k]} onChange={(v) => patchMon(`social.${k}`, v)} />)}</TabsContent>
            <TabsContent value="mobile" className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-3">{Object.keys(mc.mobile_apps).map((k) => <Toggle key={k} label={k} checked={mc.mobile_apps[k]} onChange={(v) => patchMon(`mobile_apps.${k}`, v)} />)}</TabsContent>
            <TabsContent value="other" className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-3">
              <Toggle label="meta_ads" checked={mc.meta_ads} onChange={(v) => patchMon("meta_ads", v)} />
              <Toggle label="executive_monitoring" checked={mc.executive_monitoring} onChange={(v) => patchMon("executive_monitoring", v)} />
              <Toggle label="email_impersonation" checked={mc.email_impersonation} onChange={(v) => patchMon("email_impersonation", v)} />
            </TabsContent>
          </Tabs>
        </Card>
      )}
    </div>
  );
}
