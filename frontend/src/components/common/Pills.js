import React from "react";
import { AlertTriangle, Flame, ShieldAlert, ShieldCheck, CircleDot } from "lucide-react";

const sevStyles = {
  Critical: "bg-[hsl(var(--severity-critical)/0.12)] text-[hsl(var(--severity-critical))] border-[hsl(var(--severity-critical)/0.25)]",
  High: "bg-[hsl(var(--severity-high)/0.12)] text-[hsl(var(--severity-high))] border-[hsl(var(--severity-high)/0.25)]",
  Medium: "bg-[hsl(var(--severity-medium)/0.16)] text-[hsl(28_90%_38%)] border-[hsl(var(--severity-medium)/0.30)]",
  Low: "bg-[hsl(var(--severity-low)/0.12)] text-[hsl(var(--severity-low))] border-[hsl(var(--severity-low)/0.25)]",
};
const sevIcon = { Critical: Flame, High: ShieldAlert, Medium: AlertTriangle, Low: ShieldCheck };

export const SeverityPill = ({ value }) => {
  const Icon = sevIcon[value] || CircleDot;
  return (
    <span data-testid={`severity-pill-${value}`} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium border ${sevStyles[value] || sevStyles.Low}`}>
      <Icon className="h-3 w-3" /> {value}
    </span>
  );
};

const statusStyles = {
  Open: "bg-[hsl(var(--status-open)/0.12)] text-[hsl(var(--status-open))] border-[hsl(var(--status-open)/0.25)]",
  Triage: "bg-[hsl(var(--status-triage)/0.16)] text-[hsl(28_90%_38%)] border-[hsl(var(--status-triage)/0.30)]",
  "In Progress": "bg-[hsl(var(--status-triage)/0.16)] text-[hsl(28_90%_38%)] border-[hsl(var(--status-triage)/0.30)]",
  Resolved: "bg-[hsl(var(--status-resolved)/0.12)] text-[hsl(var(--status-resolved))] border-[hsl(var(--status-resolved)/0.25)]",
  Closed: "bg-[hsl(var(--status-ignored)/0.12)] text-[hsl(var(--status-ignored))] border-[hsl(var(--status-ignored)/0.25)]",
  Ignored: "bg-[hsl(var(--status-ignored)/0.12)] text-[hsl(var(--status-ignored))] border-[hsl(var(--status-ignored)/0.25)]",
  Waiting: "bg-[hsl(var(--status-triage)/0.16)] text-[hsl(28_90%_38%)] border-[hsl(var(--status-triage)/0.30)]",
};

export const StatusPill = ({ value }) => (
  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium border ${statusStyles[value] || statusStyles.Open}`}>
    <CircleDot className="h-3 w-3" /> {value}
  </span>
);

const healthStyles = {
  healthy: "bg-[hsl(var(--health-healthy)/0.12)] text-[hsl(var(--health-healthy))] border-[hsl(var(--health-healthy)/0.25)]",
  degraded: "bg-[hsl(var(--health-degraded)/0.16)] text-[hsl(28_90%_38%)] border-[hsl(var(--health-degraded)/0.30)]",
  failed: "bg-[hsl(var(--health-failed)/0.12)] text-[hsl(var(--health-failed))] border-[hsl(var(--health-failed)/0.25)]",
  running: "bg-[hsl(var(--info)/0.12)] text-[hsl(var(--info))] border-[hsl(var(--info)/0.25)]",
};

export const HealthPill = ({ value }) => (
  <span data-testid="monitoring-health-status-pill" className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[12px] font-medium border capitalize ${healthStyles[value] || healthStyles.degraded}`}>
    <span className="h-2 w-2 rounded-full" style={{ background: "currentColor" }} /> {value}
  </span>
);

// Impersonation confidence classification (shown alongside severity on social findings)
const confStyles = {
  "HIGH-CONFIDENCE IMPERSONATION": "bg-[hsl(var(--severity-critical)/0.12)] text-[hsl(var(--severity-critical))] border-[hsl(var(--severity-critical)/0.25)]",
  "LIKELY IMPERSONATION": "bg-[hsl(var(--severity-high)/0.12)] text-[hsl(var(--severity-high))] border-[hsl(var(--severity-high)/0.25)]",
  "SUSPICIOUS": "bg-[hsl(var(--severity-medium)/0.16)] text-[hsl(28_90%_38%)] border-[hsl(var(--severity-medium)/0.30)]",
  "LIKELY LEGITIMATE": "bg-[hsl(var(--info)/0.12)] text-[hsl(var(--info))] border-[hsl(var(--info)/0.25)]",
  "LEGITIMATE": "bg-[hsl(var(--severity-low)/0.12)] text-[hsl(var(--severity-low))] border-[hsl(var(--severity-low)/0.25)]",
};
const confShort = {
  "HIGH-CONFIDENCE IMPERSONATION": "High-Conf Impersonation",
  "LIKELY IMPERSONATION": "Likely Impersonation",
  "SUSPICIOUS": "Suspicious",
  "LIKELY LEGITIMATE": "Likely Legit",
  "LEGITIMATE": "Legitimate",
};

export const ConfidencePill = ({ value, score }) => {
  if (!value) return <span className="text-[12px] text-muted-foreground">—</span>;
  return (
    <span data-testid="confidence-pill" className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11.5px] font-medium border ${confStyles[value] || confStyles.LEGITIMATE}`}>
      {confShort[value] || value}{score != null ? ` · ${score}%` : ""}
    </span>
  );
};

export const RiskBar = ({ value }) => {
  const color = value >= 80 ? "var(--severity-critical)" : value >= 60 ? "var(--severity-high)" : value >= 35 ? "var(--severity-medium)" : "var(--severity-low)";
  return (
    <div className="flex items-center gap-2 min-w-[90px]">
      <div className="h-1.5 w-14 rounded-full bg-[hsl(var(--surface-3))] overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${value}%`, background: `hsl(${color})` }} />
      </div>
      <span className="text-[12px] font-semibold tabular-nums">{value}</span>
    </div>
  );
};