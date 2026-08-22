import React from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

export const AppShell = ({ children }) => (
  <div className="flex h-screen w-full overflow-hidden bg-background">
    <Sidebar />
    <div className="flex flex-1 flex-col overflow-hidden">
      <TopBar />
      <main className="flex-1 overflow-y-auto">
        <div className="px-4 sm:px-6 lg:px-8 py-5">{children}</div>
      </main>
    </div>
  </div>
);
