import React from "react";
import { FindingsPage } from "@/components/common/FindingsPage";
import { UserRound } from "lucide-react";

export default function Executive() {
  return (
    <FindingsPage
      module="executive" screen="executive" title="Executive Monitoring"
      subtitle="Impersonation of key executives (add executives in the tenant wizard to enable)"
      icon={UserRound} platformOptions={["LinkedIn", "X", "Instagram", "Facebook"]}
      moduleFilters={[{ key: "category", label: "Finding Type", facetKey: "category" }]}
    />
  );
}
