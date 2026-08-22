import React from "react";

export const PageHeader = ({ title, subtitle, actions, icon: Icon }) => (
  <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
    <div className="flex items-start gap-3">
      {Icon && (
        <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-xl bg-[hsl(var(--accent))] text-[hsl(var(--accent-foreground))]">
          <Icon className="h-5 w-5" />
        </div>
      )}
      <div>
        <h1 className="text-xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-0.5 text-[13px] text-muted-foreground">{subtitle}</p>}
      </div>
    </div>
    {actions && <div className="flex items-center gap-2">{actions}</div>}
  </div>
);
