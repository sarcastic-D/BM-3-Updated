import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Radar, Save } from "lucide-react";
import { toast } from "sonner";

const LABELS = {
  search_providers: "Search Providers (DuckDuckGo)", certificate_transparency: "Certificate Transparency (crt.sh)",
  rdap: "RDAP", dns: "DNS Resolvers", social_apis: "Social APIs", telegram_apis: "Telegram API",
  app_stores: "App Stores", meta_apis: "Meta Ads API",
};
const FREE = ["search_providers", "certificate_transparency", "rdap", "dns", "app_stores"];

export default function IntelligenceSources() {
  const [cfg, setCfg] = useState(null);
  useEffect(() => { api.get("/intelligence-sources").then(({ data }) => setCfg(data)); }, []);

  const toggle = (key, val) => setCfg((p) => ({ ...p, [key]: { ...p[key], enabled: val } }));
  const save = async () => { await api.put("/intelligence-sources", cfg); toast.success("Sources saved"); };

  if (!cfg) return null;
  return (
    <div>
      <PageHeader title="Intelligence Sources" subtitle="Data providers powering the collectors" icon={Radar}
        actions={<Button onClick={save} className="gap-1.5" data-testid="sources-save-button"><Save className="h-4 w-4" /> Save</Button>} />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {Object.keys(LABELS).map((key) => {
          const s = cfg[key] || {};
          const free = FREE.includes(key);
          return (
            <Card key={key} className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2"><span className="text-[13px] font-semibold">{LABELS[key]}</span>
                    {free ? <Badge variant="outline" className="text-[hsl(var(--success))] border-[hsl(var(--success)/0.3)]">Free · No API key</Badge>
                      : <Badge variant="outline" className="text-muted-foreground">Requires API key</Badge>}</div>
                  <div className="mt-1 text-[11.5px] text-muted-foreground">Status: <span className={s.status === "connected" ? "text-[hsl(var(--success))]" : "text-[hsl(var(--warning))]"}>{s.status || "not configured"}</span></div>
                </div>
                <Switch checked={!!s.enabled} onCheckedChange={(v) => toggle(key, v)} data-testid={`source-toggle-${key}`} />
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
