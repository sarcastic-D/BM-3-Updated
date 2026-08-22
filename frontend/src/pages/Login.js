import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { ShieldHalf, Loader2 } from "lucide-react";
import { toast } from "sonner";

const demo = [
  ["Super Admin", "admin@brandshield.io", "Admin@123"],
  ["Tenant Admin", "tadmin@brandshield.io", "Tenant@123"],
  ["Analyst", "analyst@brandshield.io", "Analyst@123"],
  ["Viewer", "viewer@brandshield.io", "Viewer@123"],
];

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("admin@brandshield.io");
  const [password, setPassword] = useState("Admin@123");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await login(email, password);
      toast.success(`Welcome, ${u.name}`);
      nav(u.role === "super_admin" || u.role === "tenant_admin" ? "/admin" : "/dashboard");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Login failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-gradient-to-b from-[hsl(210_40%_98%)] to-[hsl(36_33%_97%)] px-4">
      <div className="w-full max-w-[880px] overflow-hidden rounded-2xl border border-border bg-card shadow-[0_10px_40px_rgba(15,23,42,0.08)] md:grid md:grid-cols-2">
        <div className="hidden flex-col justify-between bg-[hsl(var(--primary))] p-8 text-white md:flex">
          <div className="flex items-center gap-2">
            <ShieldHalf className="h-6 w-6" />
            <span className="text-lg font-bold">BrandShield</span>
          </div>
          <div>
            <h2 className="text-2xl font-bold leading-tight">Digital Risk Protection, governed centrally.</h2>
            <p className="mt-3 text-[13px] text-white/80">Admin-configured monitoring across domains, social, and the open web. Filter-first investigation for analysts, tenant-isolated by design.</p>
          </div>
          <div className="text-[11px] text-white/60">Certificate Transparency · RDAP · DNS · Typosquat · Search Dorking</div>
        </div>
        <div className="p-8">
          <div className="mb-6 flex items-center gap-2 md:hidden">
            <ShieldHalf className="h-6 w-6 text-[hsl(var(--primary))]" />
            <span className="text-lg font-bold">BrandShield</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight">Sign in</h1>
          <p className="mt-1 text-[13px] text-muted-foreground">Access the monitoring console</p>
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div>
              <Label className="text-[12px]">Email</Label>
              <Input data-testid="login-email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1" required />
            </div>
            <div>
              <Label className="text-[12px]">Password</Label>
              <Input data-testid="login-password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1" required />
            </div>
            <Button data-testid="login-submit-button" type="submit" className="w-full" disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Sign in"}
            </Button>
          </form>
          <div className="mt-6">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Demo accounts</div>
            <div className="mt-2 grid grid-cols-2 gap-1.5">
              {demo.map(([label, em, pw]) => (
                <button key={em} type="button" onClick={() => { setEmail(em); setPassword(pw); }}
                  className="rounded-lg border border-border bg-[hsl(var(--surface-2))] px-2.5 py-1.5 text-left text-[11px] transition-colors hover:border-[hsl(var(--ring))]">
                  <div className="font-semibold">{label}</div>
                  <div className="truncate text-muted-foreground">{em}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
