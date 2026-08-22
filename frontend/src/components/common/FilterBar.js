import React, { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Filter, RotateCcw, Search, Bookmark, BookmarkPlus, Download, FileText, Star, X } from "lucide-react";
import { toast } from "sonner";

const SEVERITIES = ["All", "Critical", "High", "Medium", "Low"];
const STATUSES = ["All", "Open", "Triage", "In Progress", "Resolved", "Closed", "Ignored"];

const defaultDraft = () => ({
  tenant_id: "All", date_from: "", date_to: "", severity: "All", status: "All",
  source: "All", platform: "All", risk: [0, 100], search: "",
});

export const FilterBar = ({
  screen = "findings", moduleFilters = [], booleanFilters = [], platformOptions,
  onApply, onExport, onExportPdf, defaultFilters = {},
}) => {
  const { selectedTenant, canWrite, isAdmin } = useAuth();
  const [draft, setDraft] = useState({ ...defaultDraft(), ...defaultFilters });
  const [facets, setFacets] = useState({});
  const [saved, setSaved] = useState([]);
  const [presets, setPresets] = useState([]);
  const [saveName, setSaveName] = useState("");
  const [saveOpen, setSaveOpen] = useState(false);

  const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }));

  const draftRef = useRef(draft);
  useEffect(() => { draftRef.current = draft; }, [draft]);

  const loadFacets = useCallback(async (tid) => {
    try {
      const { data } = await api.get("/findings/facets", { params: { tenant_id: tid === "All" ? undefined : tid } });
      setFacets(data);
    } catch (e) { /* ignore */ }
  }, []);

  const loadSaved = useCallback(async () => {
    try {
      const [s, p] = await Promise.all([
        api.get("/saved-filters", { params: { screen } }),
        api.get("/presets", { params: { screen } }),
      ]);
      setSaved(s.data); setPresets(p.data);
    } catch (e) { /* ignore */ }
  }, [screen]);

  // When the top-bar tenant switches (or on mount), sync tenant into the
  // draft, refresh facets/saved filters, and AUTO-APPLY so the listing
  // reflects the selected tenant immediately (preserving other filters).
  useEffect(() => {
    const nd = { ...draftRef.current, tenant_id: selectedTenant };
    setDraft(nd);
    onApply(buildParams(nd));
    loadFacets(selectedTenant);
    loadSaved();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTenant]);

  const buildParams = useCallback((d) => {
    const p = {};
    if (d.tenant_id && d.tenant_id !== "All") p.tenant_id = d.tenant_id;
    if (d.severity !== "All") p.severity = d.severity;
    if (d.status !== "All") p.status = d.status;
    if (d.source !== "All") p.source = d.source;
    if (d.platform !== "All") p.platform = d.platform;
    if (d.date_from) p.date_from = d.date_from;
    if (d.date_to) p.date_to = d.date_to;
    if (d.search) p.search = d.search;
    if (d.risk[0] > 0) p.risk_min = d.risk[0];
    if (d.risk[1] < 100) p.risk_max = d.risk[1];
    moduleFilters.forEach((mf) => { if (d[mf.key] && d[mf.key] !== "All") p[mf.key] = d[mf.key]; });
    booleanFilters.forEach((bf) => { if (d[bf.key] && d[bf.key] !== "All") p[bf.key] = d[bf.key]; });
    return p;
  }, [moduleFilters, booleanFilters]);

  const apply = (d = draft) => onApply(buildParams(d));

  const reset = () => {
    const d = { ...defaultDraft(), ...defaultFilters, tenant_id: selectedTenant };
    setDraft(d); apply(d);
  };

  const applyConditions = (cond) => {
    const d = { ...defaultDraft(), tenant_id: selectedTenant };
    Object.entries(cond).forEach(([k, v]) => {
      if (k === "risk_min") d.risk = [v, d.risk[1]];
      else if (k === "risk_max") d.risk = [d.risk[0], v];
      else d[k] = v;
    });
    setDraft(d); onApply({ ...buildParams(d), ...cond });
  };

  const saveFilter = async () => {
    if (!saveName.trim()) return;
    try {
      await api.post("/saved-filters", { screen, name: saveName, conditions: buildParams(draft) });
      toast.success("Filter saved");
      setSaveName(""); setSaveOpen(false); loadSaved();
    } catch (e) { toast.error("Could not save filter"); }
  };

  const deleteSaved = async (id) => { await api.delete(`/saved-filters/${id}`); loadSaved(); };

  const facetOpts = (key) => (facets[key] || []).filter(Boolean);
  const platforms = platformOptions || ["Instagram", "Facebook", "YouTube", "LinkedIn", "X", "Reddit", "Pastebin", "Scribd", "Web", "Telegram"];

  const activeChips = useMemo(() => {
    const chips = [];
    if (draft.severity !== "All") chips.push(["Severity", draft.severity, () => set("severity", "All")]);
    if (draft.status !== "All") chips.push(["Status", draft.status, () => set("status", "All")]);
    if (draft.source !== "All") chips.push(["Source", draft.source, () => set("source", "All")]);
    if (draft.platform !== "All") chips.push(["Platform", draft.platform, () => set("platform", "All")]);
    if (draft.risk[0] > 0 || draft.risk[1] < 100) chips.push(["Risk", `${draft.risk[0]}-${draft.risk[1]}`, () => set("risk", [0, 100])]);
    return chips;
  }, [draft]);

  return (
    <div data-testid="global-filter-bar" className="mb-4 rounded-[var(--radius)] border border-border bg-card p-3 shadow-[0_1px_0_rgba(15,23,42,0.04)]">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-12">
        <div className="col-span-2 md:col-span-3">
          <Label className="mb-1 block text-[11px] text-muted-foreground">Severity</Label>
          <Select value={draft.severity} onValueChange={(v) => set("severity", v)}>
            <SelectTrigger data-testid="global-filter-severity-select" className="h-9 text-[13px]"><SelectValue /></SelectTrigger>
            <SelectContent>{SEVERITIES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="col-span-2 md:col-span-3">
          <Label className="mb-1 block text-[11px] text-muted-foreground">Status</Label>
          <Select value={draft.status} onValueChange={(v) => set("status", v)}>
            <SelectTrigger data-testid="global-filter-status-select" className="h-9 text-[13px]"><SelectValue /></SelectTrigger>
            <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="col-span-1 md:col-span-3">
          <Label className="mb-1 block text-[11px] text-muted-foreground">Source</Label>
          <Select value={draft.source} onValueChange={(v) => set("source", v)}>
            <SelectTrigger data-testid="global-filter-source-select" className="h-9 text-[13px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="All">All Sources</SelectItem>
              {(facetOpts("source").length ? facetOpts("source") : ["Typosquat", "crt.sh", "RDAP", "DNS", "Search/Dorking"]).map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="col-span-1 md:col-span-3">
          <Label className="mb-1 block text-[11px] text-muted-foreground">Platform</Label>
          <Select value={draft.platform} onValueChange={(v) => set("platform", v)}>
            <SelectTrigger data-testid="global-filter-platform-select" className="h-9 text-[13px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="All">All Platforms</SelectItem>
              {platforms.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        {moduleFilters.map((mf) => (
          <div key={mf.key} className="col-span-1 md:col-span-3">
            <Label className="mb-1 block text-[11px] text-muted-foreground">{mf.label}</Label>
            <Select value={draft[mf.key] || "All"} onValueChange={(v) => set(mf.key, v)}>
              <SelectTrigger className="h-9 text-[13px]"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                {(mf.options || facetOpts(mf.facetKey || mf.key)).map((o) => {
                  const val = typeof o === "string" ? o : o.value;
                  const lab = typeof o === "string" ? o : o.label;
                  return <SelectItem key={val} value={val}>{lab}</SelectItem>;
                })}
              </SelectContent>
            </Select>
          </div>
        ))}
        {booleanFilters.map((bf) => (
          <div key={bf.key} className="col-span-1 md:col-span-3">
            <Label className="mb-1 block text-[11px] text-muted-foreground">{bf.label}</Label>
            <Select value={draft[bf.key] || "All"} onValueChange={(v) => set(bf.key, v)}>
              <SelectTrigger className="h-9 text-[13px]"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                <SelectItem value="yes">Yes</SelectItem>
                <SelectItem value="no">No</SelectItem>
              </SelectContent>
            </Select>
          </div>
        ))}

        <div className="col-span-1 md:col-span-3">
          <Label className="mb-1 block text-[11px] text-muted-foreground">First Seen From</Label>
          <Input type="date" value={draft.date_from} onChange={(e) => set("date_from", e.target.value)} data-testid="global-filter-date-from" className="h-9 text-[13px]" />
        </div>
        <div className="col-span-1 md:col-span-3">
          <Label className="mb-1 block text-[11px] text-muted-foreground">First Seen To</Label>
          <Input type="date" value={draft.date_to} onChange={(e) => set("date_to", e.target.value)} data-testid="global-filter-date-to" className="h-9 text-[13px]" />
        </div>
        <div className="col-span-2 md:col-span-3">
          <Label className="mb-1 block text-[11px] text-muted-foreground">Risk Score: {draft.risk[0]} – {draft.risk[1]}</Label>
          <div className="px-1 pt-3">
            <Slider data-testid="global-filter-risk-score-slider" value={draft.risk} min={0} max={100} step={5} onValueChange={(v) => set("risk", v)} />
          </div>
        </div>
        <div className="col-span-2 md:col-span-3">
          <Label className="mb-1 block text-[11px] text-muted-foreground">Search</Label>
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input data-testid="global-filter-search-input" value={draft.search} onChange={(e) => set("search", e.target.value)} onKeyDown={(e) => e.key === "Enter" && apply()} placeholder="domain / url / handle" className="h-9 pl-8 text-[13px]" />
          </div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button data-testid="global-filter-apply-button" onClick={() => apply()} className="h-9 gap-1.5"><Filter className="h-3.5 w-3.5" /> Apply</Button>
        <Button data-testid="global-filter-reset-button" variant="outline" onClick={reset} className="h-9 gap-1.5"><RotateCcw className="h-3.5 w-3.5" /> Reset</Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button data-testid="global-filter-saved-filters-menu" variant="outline" className="h-9 gap-1.5"><Bookmark className="h-3.5 w-3.5" /> Saved & Presets</Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-64">
            <DropdownMenuLabel className="flex items-center gap-1.5"><Star className="h-3.5 w-3.5" /> Global Presets</DropdownMenuLabel>
            {presets.length === 0 && <div className="px-2 py-1 text-[12px] text-muted-foreground">No presets</div>}
            {presets.map((p) => (
              <DropdownMenuItem key={p.id} onClick={() => applyConditions(p.conditions)}>{p.name}</DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuLabel>My Saved Filters</DropdownMenuLabel>
            {saved.length === 0 && <div className="px-2 py-1 text-[12px] text-muted-foreground">No saved filters</div>}
            {saved.map((s) => (
              <DropdownMenuItem key={s.id} className="flex items-center justify-between" onSelect={(e) => e.preventDefault()}>
                <span className="cursor-pointer" onClick={() => applyConditions(s.conditions)}>{s.name}</span>
                <X className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" onClick={() => deleteSaved(s.id)} />
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
          <DialogTrigger asChild>
            <Button data-testid="global-filter-save-button" variant="outline" className="h-9 gap-1.5"><BookmarkPlus className="h-3.5 w-3.5" /> Save Filter</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Save current filter</DialogTitle></DialogHeader>
            <Input placeholder="e.g. High Risk Fake Domains" value={saveName} onChange={(e) => setSaveName(e.target.value)} data-testid="save-filter-name-input" />
            <DialogFooter><Button onClick={saveFilter} data-testid="save-filter-confirm-button">Save</Button></DialogFooter>
          </DialogContent>
        </Dialog>

        {onExport && (
          <Button data-testid="global-filter-export-csv-button" variant="outline" onClick={onExport} className="h-9 gap-1.5"><Download className="h-3.5 w-3.5" /> Export CSV</Button>
        )}
        {onExportPdf && (
          <Button data-testid="global-filter-export-pdf-button" variant="outline" onClick={onExportPdf} className="h-9 gap-1.5"><FileText className="h-3.5 w-3.5" /> Export PDF</Button>
        )}

        {activeChips.length > 0 && <div className="ml-auto flex flex-wrap gap-1.5">
          {activeChips.map(([label, val, clear], i) => (
            <Badge key={i} variant="secondary" className="gap-1 pr-1">{label}: {val}
              <button onClick={() => { clear(); }} className="ml-0.5 rounded-full p-0.5 hover:bg-muted-foreground/20"><X className="h-3 w-3" /></button>
            </Badge>
          ))}
        </div>}
      </div>
    </div>
  );
};
