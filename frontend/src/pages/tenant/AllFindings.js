import React from "react";
import { FindingsPage } from "@/components/common/FindingsPage";
import { ListFilter } from "lucide-react";

export default function AllFindings() {
  return (
    <FindingsPage
      screen="findings"
      title="All Findings"
      subtitle="Centralized investigation across every monitoring source"
      icon={ListFilter}
      moduleFilters={[
        { key: "category", label: "Category", facetKey: "category" },
      ]}
    />
  );
}
