import React from "react";
import { FindingsPage } from "@/components/common/FindingsPage";
import { RiskBar } from "@/components/common/Pills";
import { Radar } from "lucide-react";

const columns = [
  { key: "domain", label: "Domain / Host", sortable: true, render: (r) => <span className="font-mono text-[12.5px] font-medium">{r.domain}</span> },
  { key: "registrar", label: "Registrar", render: (r) => <span className="text-[12px] text-muted-foreground">{r.entities?.registrar || "—"}</span> },
  { key: "issuer", label: "Cert Issuer", render: (r) => <span className="truncate text-[11.5px] text-muted-foreground max-w-[200px] inline-block">{r.entities?.certificate_issuer || "—"}</span> },
  { key: "source", label: "Source", render: (r) => <span className="text-[12px]">{r.source}</span> },
  { key: "risk_score", label: "Risk", sortable: true, render: (r) => <RiskBar value={r.risk_score} /> },
  { key: "first_seen", label: "Discovered", sortable: true, render: (r) => <span className="text-[12px] text-muted-foreground">{r.first_seen?.slice(0, 10)}</span> },
];

export default function DomainIntel() {
  return (
    <FindingsPage
      module="domain_intel" screen="domain_intel" title="Domain Intelligence"
      subtitle="Subdomains & registration data from Certificate Transparency, RDAP & DNS"
      icon={Radar} columns={columns} platformOptions={["Web"]}
      moduleFilters={[
        { key: "registrar", label: "Registrar", facetKey: "registrar" },
        { key: "tld", label: "TLD", facetKey: "tld" },
        { key: "certificate_issuer", label: "Cert Issuer", facetKey: "certificate_issuer" },
      ]}
    />
  );
}
