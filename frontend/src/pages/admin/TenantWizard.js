import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/common/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import { SlidersHorizontal, ChevronLeft, ChevronRight, CheckCircle2, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";

const STEPS = ["Brand", "Domains", "Social", "Executives", "Apps", "Email", "Telegram", "Search/Dorking", "Schedules", "Risk Policy", "Notifications", "Activate"];

const Toggle = ({ label, checked, onChange }) => (
  <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2.5">
    <span className="text-[13px] capitalize">{label.replace(/_/g, " ")}</span>
    <Switch checked={checked} onCheckedChange={onChange} />
  </div>
);

export default function TenantWizard() {
  const { id } = useParams();
  const nav = useNavigate();
  const { loadTenants } = useAuth();
  const [t, setT] = useState(null);
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [detecting, setDetecting] = useState(false);

  const load = useCallback(async () => {
    const { data } = await api.get(`/tenants/${id}`);
    setT(data); setStep(Math.min((data.wizard_step || 1) - 1, 11));
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const patch = (obj) => setT((p) => ({ ...p, ...obj }));
  const patchId = (key, val) => setT((p) => ({ ...p, identity: { ...(p.identity || {}), [key]: val } }));
  const patchHandle = (plat, val) => setT((p) => ({
    ...p, identity: { ...(p.identity || {}), social_handles: { ...((p.identity || {}).social_handles || {}), [plat]: val } },
  }));
  const parseCsv = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);

  const autoDetect = async () => {
    if (!t?.primary_domain) { toast.error("Set the primary domain first (Domains step)"); return; }
    setDetecting(true);
    try {
      const { data } = await api.get("/tools/analyze-domain", { params: { domain: t.primary_domain } });
      if (data.error && !data.brand_names.length) { toast.error("Could not analyze domain"); return; }
      const handles = { ...((t.identity || {}).social_handles || {}), ...(data.social_handles || {}) };
      patch({
        brand_names: data.brand_names.length ? data.brand_names : t.brand_names,
        products: data.products.length ? data.products.slice(0, 12) : t.products,
        identity: {
          ...(t.identity || {}),
          social_handles: handles,
          email_domains: (data.email_domains && data.email_domains.length) ? data.email_domains : (t.identity || {}).email_domains || [],
        },
      });
      const nHandles = Object.values(data.social_handles || {}).filter(Boolean).length;
      toast.success(`Detected ${data.brand_names.length} brand(s), ${data.products.length} product(s), ${nHandles} social handle(s)`);
    } catch (e) { toast.error("Domain analysis failed"); }
    finally { setDetecting(false); }
  };

  const patchMon = (path, val) => setT((p) => {
    const mc = JSON.parse(JSON.stringify(p.monitoring_config));
    const parts = path.split(".");
    let cur = mc; for (let i = 0; i < parts.length - 1; i++) cur = cur[parts[i]];
    cur[parts[parts.length - 1]] = val;
    return { ...p, monitoring_config: mc };
  });

  const save = async (extra = {}) => {
    setSaving(true);
    try {
      await api.put(`/tenants/${id}`, {
        name: t.name, primary_domain: t.primary_domain,
        additional_domains: t.additional_domains, brand_names: t.brand_names,
        products: t.products, executives: t.executives, identity: t.identity,
        industry: t.industry, country: t.country, timezone: t.timezone,
        monitoring_config: t.monitoring_config, risk_policy: t.risk_policy,
        notifications: t.notifications, schedule: t.schedule,
        wizard_step: step + 1, ...extra,
      });
    } finally { setSaving(false); }
  };

  const next = async () => { await save(); if (step < 11) setStep(step + 1); };
  const prev = () => setStep(Math.max(0, step - 1));
  const activate = async () => {
    await save({ wizard_complete: true });
    await api.post(`/tenants/${id}/activate`);
    await api.post(`/tenants/${id}/run`);
    toast.success("Tenant activated — monitoring started");
    await loadTenants();
    nav("/admin/tenants");
  };

  if (!t) return <div className="flex h-64 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  const mc = t.monitoring_config;
  const idt = t.identity || {};
  const sh = idt.social_handles || {};

  return (
    <div>
      <PageHeader title={`Configure: ${t.name}`} subtitle={`${t.tenant_id} · Step ${step + 1} of 12 — ${STEPS[step]}`} icon={SlidersHorizontal}
        actions={<Button variant="outline" onClick={() => nav("/admin/tenants")}>Back to Tenants</Button>} />
      <Progress value={((step + 1) / 12) * 100} className="mb-4" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        <Card className="p-2 lg:col-span-1">
          {STEPS.map((s, i) => (
            <button key={s} onClick={() => setStep(i)} data-testid={`wizard-step-${i + 1}`}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[12.5px] transition-colors ${i === step ? "bg-[hsl(var(--accent))] font-semibold text-[hsl(var(--accent-foreground))]" : "text-muted-foreground hover:bg-[hsl(var(--surface-3))]"}`}>
              <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] ${i < step ? "bg-[hsl(var(--success))] text-white" : i === step ? "bg-[hsl(var(--primary))] text-white" : "bg-[hsl(var(--surface-3))]"}`}>{i < step ? "✓" : i + 1}</span>
              {s}
            </button>
          ))}
        </Card>
        <Card className="p-5 lg:col-span-3">
          {step === 0 && (<div className="space-y-3">
            <div className="flex items-center justify-between rounded-lg border border-dashed border-[hsl(var(--primary)/0.4)] bg-[hsl(var(--accent)/0.4)] px-3 py-2">
              <div className="text-[12px] text-muted-foreground">Auto-fill brand aliases & products by analyzing <span className="font-mono">{t.primary_domain}</span></div>
              <Button type="button" variant="outline" size="sm" onClick={autoDetect} disabled={detecting} className="gap-1.5" data-testid="wizard-autodetect-button">
                {detecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Auto-detect
              </Button>
            </div>
            <div><Label className="text-[12px]">Brand Name</Label><Input value={t.name} onChange={(e) => patch({ name: e.target.value })} data-testid="wizard-brand-name" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-[12px]">Legal Name</Label><Input value={idt.legal_name || ""} onChange={(e) => patchId("legal_name", e.target.value)} placeholder="Acme Corporation Ltd." data-testid="wizard-legal-name" /></div>
              <div><Label className="text-[12px]">Trading Names (comma separated)</Label><Input value={(idt.trading_names || []).join(", ")} onChange={(e) => patchId("trading_names", parseCsv(e.target.value))} /></div>
            </div>
            <div><Label className="text-[12px]">Brand Aliases (comma separated)</Label><Input value={(t.brand_names || []).join(", ")} onChange={(e) => patch({ brand_names: parseCsv(e.target.value) })} /></div>
            <div><Label className="text-[12px]">Monitoring Keywords (comma separated)</Label><Input value={(idt.keywords || []).join(", ")} onChange={(e) => patchId("keywords", parseCsv(e.target.value))} placeholder="brand terms, campaign names, taglines" data-testid="wizard-keywords" /></div>
            <div><Label className="text-[12px]">Products (comma separated)</Label><Input value={(t.products || []).join(", ")} onChange={(e) => patch({ products: parseCsv(e.target.value) })} /></div>
            <div className="grid grid-cols-2 gap-3"><div><Label className="text-[12px]">Industry</Label><Input value={t.industry || ""} onChange={(e) => patch({ industry: e.target.value })} /></div><div><Label className="text-[12px]">Country</Label><Input value={t.country || ""} onChange={(e) => patch({ country: e.target.value })} /></div></div>
          </div>)}
          {step === 1 && (<div className="space-y-3">
            <div><Label className="text-[12px]">Primary Domain</Label><Input value={t.primary_domain} onChange={(e) => patch({ primary_domain: e.target.value })} data-testid="wizard-primary-domain" /></div>
            <div><Label className="text-[12px]">Additional Domains (comma separated)</Label><Input value={(t.additional_domains || []).join(", ")} onChange={(e) => patch({ additional_domains: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-[12px]">Marketing Domains</Label><Input value={(idt.marketing_domains || []).join(", ")} onChange={(e) => patchId("marketing_domains", parseCsv(e.target.value))} placeholder="promo.acme.com" /></div>
              <div><Label className="text-[12px]">Regional Domains</Label><Input value={(idt.regional_domains || []).join(", ")} onChange={(e) => patchId("regional_domains", parseCsv(e.target.value))} placeholder="acme.co.uk, acme.in" /></div>
            </div>
            <p className="text-[11px] text-muted-foreground">Official domains form the trusted baseline — look-alikes are compared against them and used to detect external-link mismatches.</p>
            <div className="grid grid-cols-2 gap-2 pt-1">
              <Toggle label="typosquat" checked={mc.domains.typosquat} onChange={(v) => patchMon("domains.typosquat", v)} />
              <Toggle label="certificate_transparency" checked={mc.domains.certificate_transparency} onChange={(v) => patchMon("domains.certificate_transparency", v)} />
              <Toggle label="rdap" checked={mc.domains.rdap} onChange={(v) => patchMon("domains.rdap", v)} />
              <Toggle label="dns" checked={mc.domains.dns} onChange={(v) => patchMon("domains.dns", v)} />
              <Toggle label="content_monitoring" checked={mc.domains.content_monitoring} onChange={(v) => patchMon("domains.content_monitoring", v)} />
            </div>
          </div>)}
          {step === 2 && (<div className="space-y-4">
            <div>
              <Label className="text-[12px] font-semibold">Official Handles (trusted identity)</Label>
              <p className="mb-2 text-[11px] text-muted-foreground">Used to verify accounts — a matching handle is marked legitimate, a mismatch raises impersonation confidence.</p>
              <div className="grid grid-cols-2 gap-2">
                {["x", "instagram", "linkedin", "facebook", "youtube"].map((p) => (
                  <div key={p}>
                    <Label className="text-[11px] capitalize">{p}</Label>
                    <Input value={sh[p] || ""} onChange={(e) => patchHandle(p, e.target.value)} placeholder={`@official${p === "x" ? "" : ""}`} data-testid={`wizard-handle-${p}`} />
                  </div>
                ))}
              </div>
            </div>
            <div>
              <Label className="text-[12px] font-semibold">Platforms to monitor</Label>
              <div className="mt-1 grid grid-cols-2 gap-2">{Object.keys(mc.social).map((k) => <Toggle key={k} label={k} checked={mc.social[k]} onChange={(v) => patchMon(`social.${k}`, v)} />)}</div>
            </div>
          </div>)}
          {step === 3 && (<div className="space-y-3"><Label className="text-[12px]">Executives to monitor (comma separated)</Label><Input value={(t.executives || []).join(", ")} onChange={(e) => patch({ executives: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} placeholder="Jane Doe, John Smith" /><Toggle label="executive_monitoring" checked={mc.executive_monitoring} onChange={(v) => patchMon("executive_monitoring", v)} /></div>)}
          {step === 4 && (<div className="space-y-3">
            <div><Label className="text-[12px]">Official App IDs / Package Names (comma separated)</Label><Input value={(idt.official_app_ids || []).join(", ")} onChange={(e) => patchId("official_app_ids", parseCsv(e.target.value))} placeholder="com.acme.app" data-testid="wizard-official-apps" /><p className="mt-1 text-[11px] text-muted-foreground">Look-alike apps are compared against these to flag unauthorized clones.</p></div>
            <div className="grid grid-cols-2 gap-2">{Object.keys(mc.mobile_apps).map((k) => <Toggle key={k} label={k} checked={mc.mobile_apps[k]} onChange={(v) => patchMon(`mobile_apps.${k}`, v)} />)}</div>
          </div>)}
          {step === 5 && (<div className="space-y-3"><div><Label className="text-[12px]">Official Email Domains (comma separated)</Label><Input value={(idt.email_domains || []).join(", ")} onChange={(e) => patchId("email_domains", parseCsv(e.target.value))} placeholder="acme.com, mail.acme.com" data-testid="wizard-email-domains" /></div><Toggle label="email_impersonation" checked={mc.email_impersonation} onChange={(v) => patchMon("email_impersonation", v)} /><p className="mt-1 text-[12px] text-muted-foreground">Monitors look-alike email domains (uses domain intelligence + MX detection).</p></div>)}
          {step === 6 && (<div><Toggle label="telegram" checked={mc.social.telegram} onChange={(v) => patchMon("social.telegram", v)} /><p className="mt-2 text-[12px] text-muted-foreground">Requires a Telegram API credential in Intelligence Sources.</p></div>)}
          {step === 7 && (<div><Toggle label="dorking" checked={mc.domains.dorking} onChange={(v) => patchMon("domains.dorking", v)} /><p className="mt-2 text-[12px] text-muted-foreground">Search-engine dorking across social & paste sites via the configured search provider.</p></div>)}
          {step === 8 && (<div className="space-y-3"><Label className="text-[12px]">Scan interval (hours)</Label><Input type="number" value={t.schedule?.interval_hours || 24} onChange={(e) => patch({ schedule: { ...t.schedule, interval_hours: Number(e.target.value) } })} /><Toggle label="schedule enabled" checked={t.schedule?.enabled} onChange={(v) => patch({ schedule: { ...t.schedule, enabled: v } })} /></div>)}
          {step === 9 && (<div className="space-y-3">{["critical_threshold", "high_threshold", "medium_threshold", "similarity_threshold"].map((k) => (<div key={k}><Label className="text-[12px] capitalize">{k.replace(/_/g, " ")}</Label><Input type="number" value={t.risk_policy?.[k] ?? 0} onChange={(e) => patch({ risk_policy: { ...t.risk_policy, [k]: Number(e.target.value) } })} /></div>))}</div>)}
          {step === 10 && (<div className="space-y-3"><div><Label className="text-[12px]">Alert email</Label><Input value={t.notifications?.email || ""} onChange={(e) => patch({ notifications: { ...t.notifications, email: e.target.value } })} /></div><div><Label className="text-[12px]">Webhook URL</Label><Input value={t.notifications?.webhook || ""} onChange={(e) => patch({ notifications: { ...t.notifications, webhook: e.target.value } })} /></div></div>)}
          {step === 11 && (<div className="text-center py-8"><CheckCircle2 className="mx-auto h-12 w-12 text-[hsl(var(--success))]" /><h3 className="mt-3 text-lg font-semibold">Ready to activate</h3><p className="mt-1 text-[13px] text-muted-foreground">Activating enables monitoring and runs the first scan immediately.</p><Button className="mt-4" onClick={activate} data-testid="wizard-activate-button">Activate & Run First Scan</Button></div>)}

          <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
            <Button variant="outline" onClick={prev} disabled={step === 0} className="gap-1.5"><ChevronLeft className="h-4 w-4" /> Back</Button>
            {step < 11 && <Button onClick={next} disabled={saving} className="gap-1.5" data-testid="wizard-next-button">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Save & Next <ChevronRight className="h-4 w-4" /></>}</Button>}
          </div>
        </Card>
      </div>
    </div>
  );
}
