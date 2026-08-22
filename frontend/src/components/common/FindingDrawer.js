import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { SeverityPill, StatusPill, RiskBar, ConfidencePill } from "@/components/common/Pills";
import { ExternalLink, FolderPlus, Loader2, Camera, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

const STATUSES = ["Open", "Triage", "In Progress", "Resolved", "Closed", "Ignored"];

const KV = ({ k, v }) => (
  <div className="flex items-start justify-between gap-3 border-b border-border/60 py-2 last:border-0">
    <span className="text-[12px] text-muted-foreground">{k}</span>
    <span className="text-right text-[12.5px] font-medium font-mono break-all">{v == null || v === "" ? "—" : String(v)}</span>
  </div>
);

export const FindingDrawer = ({ findingId, open, onOpenChange, onUpdated }) => {
  const { canWrite } = useAuth();
  const [f, setF] = useState(null);
  const [loading, setLoading] = useState(false);
  const [caseOpen, setCaseOpen] = useState(false);
  const [caseTitle, setCaseTitle] = useState("");
  const [casePriority, setCasePriority] = useState("Medium");
  const [capturing, setCapturing] = useState(false);

  useEffect(() => {
    if (open && findingId) {
      setLoading(true);
      api.get(`/findings/${findingId}`).then(({ data }) => setF(data)).finally(() => setLoading(false));
    } else if (!open) { setF(null); }
  }, [open, findingId]);

  const captureShot = async () => {
    setCapturing(true);
    try {
      const { data } = await api.post(`/findings/${findingId}/screenshot`);
      setF((p) => ({ ...p, entities: { ...p.entities, screenshot_url: data.screenshot_url }, screenshot_captured_at: new Date().toISOString() }));
      toast.success("Screenshot captured");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Capture failed");
    } finally { setCapturing(false); }
  };

  const updateStatus = async (status) => {
    await api.put(`/findings/${findingId}`, { status });
    setF((p) => ({ ...p, status }));
    toast.success(`Status → ${status}`);
    onUpdated && onUpdated();
  };

  const createCase = async () => {
    if (!caseTitle.trim()) return;
    await api.post("/cases", { tenant_id: f.tenant_id, title: caseTitle, priority: casePriority, finding_ids: [findingId] });
    toast.success("Case created");
    setCaseOpen(false); setCaseTitle("");
    onUpdated && onUpdated();
  };

  const ent = f?.entities || {};
  const ev = f?.evidence || {};
  const shotUrl = ent.screenshot_url ? `${process.env.REACT_APP_BACKEND_URL}${ent.screenshot_url}` : null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent data-testid="finding-detail-drawer" className="w-full sm:max-w-[560px] overflow-y-auto p-0">
        {loading || !f ? (
          <div className="flex h-full items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
        ) : (
          <div>
            <SheetHeader className="border-b border-border p-5">
              <div className="flex items-center gap-2">
                <SeverityPill value={f.severity} />
                <StatusPill value={f.status} />
                <span className="ml-auto"><RiskBar value={f.risk_score} /></span>
              </div>
              <SheetTitle className="mt-2 break-all text-left text-[16px] font-mono">{f.title}</SheetTitle>
              <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
                <span>{f.category}</span> · <span>{f.platform}</span> · <span>{f.source}</span>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Select value={f.status} onValueChange={updateStatus} disabled={!canWrite}>
                  <SelectTrigger data-testid="finding-detail-status-select" className="h-9 w-[150px] text-[13px]"><SelectValue /></SelectTrigger>
                  <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select>
                {f.url && (
                  <Button variant="outline" className="h-9 gap-1.5" asChild>
                    <a href={f.url} target="_blank" rel="noreferrer"><ExternalLink className="h-3.5 w-3.5" /> Open</a>
                  </Button>
                )}
                {canWrite && (
                  <Dialog open={caseOpen} onOpenChange={setCaseOpen}>
                    <DialogTrigger asChild>
                      <Button data-testid="finding-detail-create-case-button" className="h-9 gap-1.5"><FolderPlus className="h-3.5 w-3.5" /> Create Case</Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader><DialogTitle>Create case from finding</DialogTitle></DialogHeader>
                      <Label className="text-[12px]">Case Title</Label>
                      <Input value={caseTitle} onChange={(e) => setCaseTitle(e.target.value)} placeholder="e.g. Investigate typosquat phishing" data-testid="case-title-input" />
                      <Label className="text-[12px]">Priority</Label>
                      <Select value={casePriority} onValueChange={setCasePriority}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>{["Low", "Medium", "High", "Critical"].map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                      </Select>
                      <DialogFooter><Button onClick={createCase} data-testid="create-case-confirm-button">Create Case</Button></DialogFooter>
                    </DialogContent>
                  </Dialog>
                )}
              </div>
            </SheetHeader>

            <Tabs defaultValue="evidence" className="p-5">
              <TabsList data-testid="finding-detail-tabs">
                <TabsTrigger value="evidence">Evidence</TabsTrigger>
                <TabsTrigger value="verification">Verification</TabsTrigger>
                <TabsTrigger value="entities">Entities</TabsTrigger>
                <TabsTrigger value="screenshot">Screenshot</TabsTrigger>
                <TabsTrigger value="changes">Changes</TabsTrigger>
                <TabsTrigger value="timeline">Timeline</TabsTrigger>
              </TabsList>
              <TabsContent value="evidence" className="mt-4">
                <div className="rounded-lg border border-border bg-[hsl(var(--surface-2))] p-3">
                  {ev.query && <KV k="Query" v={ev.query} />}
                  {ev.snippet && <KV k="Snippet" v={ev.snippet} />}
                  {ev.engine && <KV k="Engine" v={ev.engine} />}
                  {ev.typo_kind && <KV k="Typo Kind" v={ev.typo_kind} />}
                  {ev.base_domain && <KV k="Base Domain" v={ev.base_domain} />}
                  {ev.ips && <KV k="Resolved IPs" v={(ev.ips || []).join(", ")} />}
                  {ev.http_status != null && <KV k="HTTP Status" v={ev.http_status} />}
                  {ev.page_title && <KV k="Page Title" v={ev.page_title} />}
                  {ev.issuer && <KV k="Certificate Issuer" v={ev.issuer} />}
                  {ev.dns && Object.entries(ev.dns).map(([k, v]) => (v?.length ? <KV key={k} k={`DNS ${k}`} v={v.join(", ")} /> : null))}
                </div>
              </TabsContent>
              <TabsContent value="verification" className="mt-4">
                {ev.verification_signals ? (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 rounded-lg border border-border bg-[hsl(var(--surface-2))] p-3">
                      <ShieldCheck className="h-4 w-4 text-muted-foreground" />
                      <span className="text-[12px] text-muted-foreground">Impersonation assessment</span>
                      <span className="ml-auto"><ConfidencePill value={ent.impersonation_classification} score={ent.impersonation_confidence} /></span>
                    </div>
                    <div className="rounded-lg border border-border bg-[hsl(var(--surface-2))] p-3" data-testid="verification-signals">
                      <KV k="Username similarity" v={ev.verification_signals.username_similarity} />
                      <KV k="Display name similarity" v={ev.verification_signals.display_name_similarity} />
                      <KV k="Official wording" v={ev.verification_signals.official_wording} />
                      <KV k="Suspicious wording" v={ev.verification_signals.suspicious_wording} />
                      <KV k="External domain" v={ev.verification_signals.external_domain} />
                      <KV k="Official link mismatch" v={ev.verification_signals.official_link_mismatch} />
                      <KV k="Account age" v={ev.verification_signals.account_age} />
                      <KV k="Followers" v={ev.verification_signals.followers} />
                      <KV k="Follower pattern" v={ev.verification_signals.follower_pattern} />
                    </div>
                    <p className="text-[11px] text-muted-foreground">Deterministic, heuristic assessment. Follower/age metrics require a connected platform API.</p>
                  </div>
                ) : ev.typo_pipeline ? (
                  <div className="space-y-3">
                    <div className="rounded-lg border border-border bg-[hsl(var(--surface-2))] p-3" data-testid="typo-pipeline">
                      <div className="mb-2 text-[12px] font-semibold">Typosquat validation pipeline</div>
                      <KV k="Generation type" v={ev.typo_pipeline.generated_kind} />
                      <KV k="DNS exists" v={ev.typo_pipeline.dns_ok ? "Yes" : "No"} />
                      <KV k="HTTP live" v={ev.typo_pipeline.http_ok ? "Yes" : "No"} />
                      <KV k="Brand similarity" v={ev.typo_pipeline.brand_similarity != null ? `${ev.typo_pipeline.brand_similarity}%` : "—"} />
                      <KV k="Content similarity" v={ev.typo_pipeline.content_similarity != null ? `${ev.typo_pipeline.content_similarity}%` : "Not measured"} />
                      <KV k="Infrastructure flags" v={(ev.typo_pipeline.infra_flags || []).length ? ev.typo_pipeline.infra_flags.join(", ") : "None"} />
                    </div>
                  </div>
                ) : (
                  <div className="rounded-lg border border-border bg-[hsl(var(--surface-2))] p-3 py-6 text-center text-[12px] text-muted-foreground">No verification data for this finding type.</div>
                )}
              </TabsContent>
              <TabsContent value="entities" className="mt-4">
                <div className="rounded-lg border border-border bg-[hsl(var(--surface-2))] p-3">
                  {Object.entries(ent).map(([k, v]) => (
                    <KV key={k} k={k.replace(/_/g, " ")} v={Array.isArray(v) ? v.join(", ") : (typeof v === "boolean" ? (v ? "Yes" : "No") : v)} />
                  ))}
                </div>
              </TabsContent>
              <TabsContent value="screenshot" className="mt-4">
                <div className="rounded-lg border border-border bg-[hsl(var(--surface-2))] p-3">
                  {shotUrl ? (
                    <div className="space-y-2">
                      <img src={shotUrl} alt="capture" className="w-full rounded-md border border-border" data-testid="finding-screenshot-img" />
                      <div className="text-[11px] text-muted-foreground">Captured {f.screenshot_captured_at?.slice(0, 19).replace("T", " ")}</div>
                    </div>
                  ) : (
                    <div className="py-6 text-center text-[12px] text-muted-foreground">No screenshot captured yet.</div>
                  )}
                  {canWrite && f.url && (
                    <Button className="mt-3 gap-1.5" onClick={captureShot} disabled={capturing} data-testid="finding-capture-screenshot-button">
                      {capturing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />}
                      {shotUrl ? "Re-capture screenshot" : "Capture screenshot"}
                    </Button>
                  )}
                  <p className="mt-2 text-[11px] text-muted-foreground">Live headless-browser capture of the public page. Some platforms (e.g. Instagram/X) may show a login wall.</p>
                </div>
              </TabsContent>
              <TabsContent value="changes" className="mt-4">
                <div className="rounded-lg border border-border bg-[hsl(var(--surface-2))] p-3">
                  {(f.changes && f.changes.length) ? (
                    <div className="space-y-2">
                      {f.changes.slice().reverse().map((ch, i) => (
                        <div key={i} className="flex items-start gap-2 border-b border-border/60 pb-2 last:border-0">
                          <span className="mt-0.5 inline-flex items-center rounded-full bg-[hsl(var(--warning)/0.15)] px-1.5 py-0.5 text-[10px] font-semibold uppercase text-[hsl(28_90%_38%)]">{ch.type}</span>
                          <div><div className="text-[12.5px]">{ch.detail}</div><div className="text-[11px] text-muted-foreground">{ch.ts?.slice(0, 19).replace("T", " ")}</div></div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="py-4 text-center text-[12px] text-muted-foreground">
                      No changes detected yet.{f.snapshot ? " A baseline snapshot is being monitored." : " Enable Content Monitoring to track drift."}
                    </div>
                  )}
                  {f.snapshot && (
                    <div className="mt-3 border-t border-border pt-2">
                      <KV k="Last checked" v={f.snapshot.checked_at?.slice(0, 19).replace("T", " ")} />
                      <KV k="HTTP status" v={f.snapshot.http_status} />
                      <KV k="Content hash" v={f.snapshot.content_hash?.slice(0, 24) + "…"} />
                      <KV k="Cert fingerprint" v={f.snapshot.cert_fp ? f.snapshot.cert_fp.slice(0, 24) + "…" : "—"} />
                    </div>
                  )}
                </div>
              </TabsContent>
              <TabsContent value="timeline" className="mt-4">
                <div className="rounded-lg border border-border bg-[hsl(var(--surface-2))] p-3">
                  <KV k="First Seen" v={f.first_seen?.slice(0, 19).replace("T", " ")} />
                  <KV k="Last Seen" v={f.last_seen?.slice(0, 19).replace("T", " ")} />
                  <KV k="Module" v={f.module} />
                  <KV k="Case" v={f.case?.case_number} />
                </div>
              </TabsContent>
            </Tabs>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};
