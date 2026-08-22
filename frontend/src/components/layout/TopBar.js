import React from "react";
import { useAuth } from "@/context/AuthContext";
import { roleLabels } from "@/constants/navConfig";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { LogOut, ChevronDown, Building2, ShieldHalf } from "lucide-react";

export const TopBar = () => {
  const { user, logout, tenants, selectedTenant, setSelectedTenant } = useAuth();
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-border bg-card/95 px-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="md:hidden flex items-center gap-2">
          <ShieldHalf className="h-5 w-5 text-[hsl(var(--primary))]" />
          <span className="font-bold">BrandShield</span>
        </div>
        <div className="flex items-center gap-2">
          <Building2 className="h-4 w-4 text-muted-foreground" />
          <Select value={selectedTenant} onValueChange={setSelectedTenant}>
            <SelectTrigger data-testid="tenant-switcher-button" className="h-9 w-[220px] text-[13px]">
              <SelectValue placeholder="Select tenant" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="All">All Tenants</SelectItem>
              {tenants.map((t) => (
                <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="hidden sm:inline-flex border-[hsl(var(--success)/0.4)] bg-[hsl(var(--success)/0.1)] text-[hsl(var(--success))]">Production</Badge>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="h-9 gap-2 px-2" data-testid="user-menu-button">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[hsl(var(--primary))] text-[12px] font-semibold text-white">
                {user?.name?.[0]}
              </div>
              <span className="hidden sm:block text-[13px] font-medium">{user?.name}</span>
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="font-semibold">{user?.name}</div>
              <div className="text-[11px] font-normal text-muted-foreground">{user?.email}</div>
              <div className="mt-1 text-[11px] font-medium text-[hsl(var(--primary))]">{roleLabels[user?.role]}</div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem data-testid="logout-button" onClick={logout} className="text-[hsl(var(--destructive))]">
              <LogOut className="mr-2 h-4 w-4" /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
};
