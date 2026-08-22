import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Settings, Save } from "lucide-react";
import { toast } from "sonner";

const FIELDS = [
  ["retention_days", "Data retention (days)", "number"],
  ["default_scan_interval_hours", "Default scan interval (hours)", "number"],
  ["max_findings_per_run", "Max findings per run", "number"],
  ["environment", "Environment", "text"],
  ["data_residency", "Data residency", "text"],
];

export default function SystemSettings() {
  const [cfg, setCfg] = useState(null);
  useEffect(() => { api.get("/system-settings").then(({ data }) => setCfg(data)); }, []);
  const save = async () => { await api.put("/system-settings", cfg); toast.success("System settings saved"); };
  if (!cfg) return null;

  return (
    <div>
      <PageHeader title="System Settings" subtitle="Platform-wide defaults and retention" icon={Settings}
        actions={<Button onClick={save} className="gap-1.5" data-testid="settings-save-button"><Save className="h-4 w-4" /> Save</Button>} />
      <Card className="max-w-xl p-5">
        <div className="space-y-3">
          {FIELDS.map(([k, label, type]) => (
            <div key={k}><Label className="text-[12px]">{label}</Label>
              <Input type={type} value={cfg[k] ?? ""} onChange={(e) => setCfg((p) => ({ ...p, [k]: type === "number" ? Number(e.target.value) : e.target.value }))} className="h-9" data-testid={`setting-${k}`} /></div>
          ))}
        </div>
      </Card>
    </div>
  );
}
