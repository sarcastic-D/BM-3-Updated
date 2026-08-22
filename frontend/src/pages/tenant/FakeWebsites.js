import React from "react";
import { FindingsPage } from "@/components/common/FindingsPage";
import { SeverityPill, StatusPill, RiskBar } from "@/components/common/Pills";
import { Badge } from "@/components/ui/badge";
import { Globe } from "lucide-react";

const DriftBadges = ({ e = {} }) => {
  const items = [];
  if (e.content_changed) items.push("Content");
  if (e.dns_changed) items.push("DNS");
  if (e.certificate_changed) items.push("Cert");
  if (!items.length) return <span className="text-[11px] text-muted-foreground">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((i) => (
        <Badge key={i} variant="outline" className="border-[hsl(var(--warning)/0.4)] bg-[hsl(var(--warning)/0.12)] text-[hsl(28_90%_38%)] text-[10px]">{i} ⚠</Badge>
      ))}
    </div>
  );
};

const columns = [
  { key: "domain", label: "Domain", sortable: true, render: (r) => <span className="font-mono text-[12.5px] font-medium">{r.domain}</span> },
  { key: "registrar", label: "Registrar", render: (r) => <span className="text-[12px] text-muted-foreground">{r.entities?.registrar || "—"}</span> },
  { key: "tld", label: "TLD", render: (r) => <span className="font-mono text-[12px]">.{r.entities?.tld}</span> },
  { key: "age", label: "Age (days)", render: (r) => <span className="tabular-nums text-[12px]">{r.entities?.domain_age_days ?? "—"}</span> },
  { key: "drift", label: "Drift", render: (r) => <DriftBadges e={r.entities} /> },
  { key: "severity", label: "Severity", sortable: true, render: (r) => <SeverityPill value={r.severity} /> },
  { key: "risk_score", label: "Risk", sortable: true, render: (r) => <RiskBar value={r.risk_score} /> },
  { key: "status", label: "Status", render: (r) => <StatusPill value={r.status} /> },
];

export default function FakeWebsites() {
  return (
    <FindingsPage
      module="fake_website" screen="fake_website" title="Fake Websites"
      subtitle="Typosquat & look-alike domains, enriched with RDAP + DNS"
      icon={Globe} columns={columns} platformOptions={["Web"]}
      moduleFilters={[
        { key: "registrar", label: "Registrar", facetKey: "registrar" },
        { key: "tld", label: "TLD", facetKey: "tld" },
      ]}
      booleanFilters={[
        { key: "content_changed", label: "Content Changed" },
        { key: "dns_changed", label: "DNS Changed" },
        { key: "certificate_changed", label: "Certificate Changed" },
      ]}
    />
  );
}
