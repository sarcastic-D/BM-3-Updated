import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ShieldAlert, Save } from "lucide-react";
import { toast } from "sonner";

export default function DetectionConfig() {
  const [cfg, setCfg] = useState(null);
  useEffect(() => { api.get("/detection-config").then(({ data }) => setCfg(data)); }, []);
  const save = async () => { await api.put("/detection-config", cfg); toast.success("Detection config saved"); };
  if (!cfg) return null;

  const setRule = (i, patch) => setCfg((p) => { const r = [...p.risk_rules]; r[i] = { ...r[i], ...patch }; return { ...p, risk_rules: r }; });
  const setTh = (grp, k, v) => setCfg((p) => ({ ...p, [grp]: { ...p[grp], [k]: Number(v) } }));

  return (
    <div>
      <PageHeader title="Detection Configuration" subtitle="Risk rules, thresholds, keywords and allow/ignore lists" icon={ShieldAlert}
        actions={<Button onClick={save} className="gap-1.5" data-testid="detection-save-button"><Save className="h-4 w-4" /> Save</Button>} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="p-4 lg:col-span-2">
          <div className="mb-3 text-[13px] font-semibold">Risk Rules</div>
          <div className="space-y-2">
            {cfg.risk_rules.map((r, i) => (
              <div key={i} className="flex items-center gap-3 rounded-lg border border-border px-3 py-2">
                <Switch checked={r.enabled} onCheckedChange={(v) => setRule(i, { enabled: v })} />
                <div className="flex-1"><div className="text-[13px] font-medium">{r.name}</div><div className="font-mono text-[11px] text-muted-foreground">{r.condition}</div></div>
                <div className="flex items-center gap-1"><span className="text-[11px] text-muted-foreground">score</span><Input type="number" value={r.score} onChange={(e) => setRule(i, { score: Number(e.target.value) })} className="h-8 w-16 text-[12px]" /></div>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-4">
          <div className="mb-3 text-[13px] font-semibold">Alert Thresholds</div>
          {Object.keys(cfg.alert_thresholds).map((k) => (
            <div key={k} className="mb-2"><Label className="text-[12px] capitalize">{k}</Label><Input type="number" value={cfg.alert_thresholds[k]} onChange={(e) => setTh("alert_thresholds", k, e.target.value)} className="h-9" /></div>
          ))}
        </Card>
        <Card className="p-4">
          <div className="mb-3 text-[13px] font-semibold">Similarity Thresholds</div>
          {Object.keys(cfg.similarity_thresholds).map((k) => (
            <div key={k} className="mb-2"><Label className="text-[12px] capitalize">{k}</Label><Input type="number" value={cfg.similarity_thresholds[k]} onChange={(e) => setTh("similarity_thresholds", k, e.target.value)} className="h-9" /></div>
          ))}
        </Card>
        <Card className="p-4">
          <div className="mb-2 text-[13px] font-semibold">Keyword Rules</div>
          <Textarea value={(cfg.keyword_rules || []).join(", ")} onChange={(e) => setCfg((p) => ({ ...p, keyword_rules: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) }))} className="text-[13px]" data-testid="keyword-rules-input" />
        </Card>
        <Card className="p-4">
          <div className="mb-2 text-[13px] font-semibold">Ignore / Allow Lists</div>
          <Label className="text-[12px]">Allow list (comma separated)</Label>
          <Textarea value={(cfg.allow_list || []).join(", ")} onChange={(e) => setCfg((p) => ({ ...p, allow_list: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) }))} className="mb-2 text-[13px]" />
          <Label className="text-[12px]">Ignore list (comma separated)</Label>
          <Textarea value={(cfg.ignore_list || []).join(", ")} onChange={(e) => setCfg((p) => ({ ...p, ignore_list: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) }))} className="text-[13px]" />
        </Card>
      </div>
    </div>
  );
}
