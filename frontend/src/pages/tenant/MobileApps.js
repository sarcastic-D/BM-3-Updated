import React from "react";
import { FindingsPage } from "@/components/common/FindingsPage";
import { SeverityPill, StatusPill, RiskBar } from "@/components/common/Pills";
import { Badge } from "@/components/ui/badge";
import { Smartphone } from "lucide-react";

const columns = [
  { key: "title", label: "App", sortable: true, render: (r) => (
    <div className="max-w-[260px]">
      <div className="truncate text-[12.5px] font-medium">{r.title}</div>
      <div className="truncate font-mono text-[11px] text-muted-foreground">{r.entities?.package_name || "—"}</div>
    </div>) },
  { key: "developer", label: "Developer", render: (r) => <span className="text-[12px] text-muted-foreground">{r.entities?.developer || "—"}</span> },
  { key: "store", label: "Store", render: (r) => <span className="text-[12px]">{r.entities?.store || r.platform}</span> },
  { key: "signature", label: "Signature", render: (r) => {
      const s = r.entities?.signature_status;
      const tone = s === "Matched" ? "text-[hsl(var(--success))] border-[hsl(var(--success)/0.3)]" : s === "Unmatched" ? "text-[hsl(var(--destructive))] border-[hsl(var(--destructive)/0.3)]" : "text-muted-foreground";
      return <Badge variant="outline" className={tone}>{s || "Unknown"}</Badge>;
    } },
  { key: "similarity", label: "Brand Sim.", render: (r) => <span className="tabular-nums text-[12px]">{r.entities?.brand_similarity != null ? `${r.entities.brand_similarity}%` : "—"}</span> },
  { key: "severity", label: "Severity", sortable: true, render: (r) => <SeverityPill value={r.severity} /> },
  { key: "risk_score", label: "Risk", sortable: true, render: (r) => <RiskBar value={r.risk_score} /> },
  { key: "status", label: "Status", render: (r) => <StatusPill value={r.status} /> },
];

export default function MobileApps() {
  return (
    <FindingsPage
      module="mobile_app" screen="mobile_app" title="Mobile Applications"
      subtitle="Look-alike apps discovered on the Google Play store (free scraper, no API key)"
      icon={Smartphone} columns={columns}
      platformOptions={["Google Play", "Apple App Store", "APK Store"]}
      moduleFilters={[
        { key: "signature_status", label: "Signature", options: ["Matched", "Unmatched", "Unknown"] },
      ]}
      booleanFilters={[]}
    />
  );
}
