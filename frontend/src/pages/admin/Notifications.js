import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Bell, Save } from "lucide-react";
import { toast } from "sonner";

export default function Notifications() {
  const [cfg, setCfg] = useState(null);
  useEffect(() => { api.get("/notifications-config").then(({ data }) => setCfg(data)); }, []);
  const setCh = (i, patch) => setCfg((p) => { const ch = [...p.channels]; ch[i] = { ...ch[i], ...patch }; return { ...p, channels: ch }; });
  const save = async () => { await api.put("/notifications-config", cfg); toast.success("Notification channels saved"); };
  if (!cfg) return null;

  return (
    <div>
      <PageHeader title="Notifications" subtitle="Alert routing for new critical findings" icon={Bell}
        actions={<Button onClick={save} className="gap-1.5" data-testid="notifications-save-button"><Save className="h-4 w-4" /> Save</Button>} />
      <div className="space-y-3">
        {cfg.channels.map((ch, i) => (
          <Card key={i} className="flex flex-wrap items-center gap-3 p-4">
            <Switch checked={ch.enabled} onCheckedChange={(v) => setCh(i, { enabled: v })} />
            <span className="w-20 text-[13px] font-semibold capitalize">{ch.type}</span>
            <Input value={ch.target} onChange={(e) => setCh(i, { target: e.target.value })} placeholder={ch.type === "email" ? "alerts@company.com" : "https://webhook..."} className="h-9 flex-1 min-w-[200px] text-[13px]" data-testid={`notif-target-${ch.type}`} />
            <div className="flex items-center gap-1.5"><span className="text-[11px] text-muted-foreground">min severity</span>
              <Select value={ch.min_severity} onValueChange={(v) => setCh(i, { min_severity: v })}>
                <SelectTrigger className="h-9 w-[120px] text-[12px]"><SelectValue /></SelectTrigger>
                <SelectContent>{["Critical", "High", "Medium", "Low"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
