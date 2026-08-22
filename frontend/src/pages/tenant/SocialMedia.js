import React from "react";
import { FindingsPage } from "@/components/common/FindingsPage";
import { SeverityPill, StatusPill, RiskBar, ConfidencePill } from "@/components/common/Pills";
import { Search } from "lucide-react";

const columns = [
  { key: "account", label: "Account Name", sortable: false, render: (r) => (
    <div className="max-w-[220px]">
      <div className="truncate text-[12.5px] font-medium">{r.entities?.account_name || r.title}</div>
      <div className="truncate font-mono text-[11px] text-muted-foreground">@{r.entities?.username || "—"}</div>
    </div>) },
  { key: "platform", label: "Platform", render: (r) => <span className="text-[12.5px]">{r.platform}</span> },
  { key: "category", label: "Type", render: (r) => <span className="text-[12.5px]">{r.category}</span> },
  { key: "confidence", label: "Verification", sortable: false, render: (r) => (
    <ConfidencePill value={r.entities?.impersonation_classification} score={r.entities?.impersonation_confidence} />) },
  { key: "description", label: "Description", render: (r) => <span className="line-clamp-2 block max-w-[240px] text-[11.5px] text-muted-foreground">{r.entities?.description || "—"}</span> },
  { key: "severity", label: "Severity", sortable: true, render: (r) => <SeverityPill value={r.severity} /> },
  { key: "risk_score", label: "Risk", sortable: true, render: (r) => <RiskBar value={r.risk_score} /> },
  { key: "status", label: "Status", render: (r) => <StatusPill value={r.status} /> },
];

export default function SocialMedia() {
  return (
    <FindingsPage
      module="social" screen="social" title="Social Media"
      subtitle="Impersonation & brand mentions — scored with an Impersonation Confidence classification"
      icon={Search} columns={columns}
      platformOptions={["Instagram", "Facebook", "X", "Twitter", "YouTube", "LinkedIn", "TikTok", "Threads", "Pinterest", "Telegram", "Reddit", "Pastebin", "Scribd"]}
      moduleFilters={[
        { key: "category", label: "Finding Type", facetKey: "category" },
        { key: "impersonation_classification", label: "Verification", options: ["HIGH-CONFIDENCE IMPERSONATION", "LIKELY IMPERSONATION", "SUSPICIOUS", "LIKELY LEGITIMATE", "LEGITIMATE"] },
      ]}
    />
  );
}
