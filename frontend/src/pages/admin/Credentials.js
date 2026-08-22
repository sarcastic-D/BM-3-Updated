import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { KeyRound, Save, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

const SLOTS = [
  { key: "telegram_apis", label: "Telegram API", field: "bot_token" },
  { key: "meta_apis", label: "Meta Ads API", field: "access_token" },
  { key: "social_apis", label: "Social APIs", field: "api_key" },
];

export default function Credentials() {
  const [cfg, setCfg] = useState(null);
  useEffect(() => { api.get("/intelligence-sources").then(({ data }) => setCfg(data)); }, []);
  const setKey = (key, field, val) => setCfg((p) => ({ ...p, [key]: { ...p[key], [field]: val } }));
  const save = async () => { await api.put("/intelligence-sources", cfg); toast.success("Credentials stored securely"); };
  if (!cfg) return null;

  return (
    <div>
      <PageHeader title="Credentials / Secrets" subtitle="API keys for premium connectors (free collectors need none)" icon={KeyRound}
        actions={<Button onClick={save} className="gap-1.5" data-testid="credentials-save-button"><Save className="h-4 w-4" /> Save</Button>} />
      <Card className="mb-4 flex items-center gap-2 border-[hsl(var(--success)/0.3)] bg-[hsl(var(--success)/0.08)] p-3">
        <ShieldCheck className="h-4 w-4 text-[hsl(var(--success))]" />
        <span className="text-[12.5px] text-[hsl(var(--success))]">Certificate Transparency, RDAP, DNS, Search-Dorking and Google Play collectors are active and require no credentials.</span>
      </Card>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {SLOTS.map((s) => (
          <Card key={s.key} className="p-4">
            <div className="mb-1 text-[13px] font-semibold">{s.label}</div>
            <Label className="text-[11px] text-muted-foreground">{s.field}</Label>
            <Input type="password" value={cfg[s.key]?.[s.field] || ""} onChange={(e) => setKey(s.key, s.field, e.target.value)} placeholder="••••••••••••" className="mt-1 font-mono" data-testid={`credential-${s.key}`} />
          </Card>
        ))}
      </div>
    </div>
  );
}
