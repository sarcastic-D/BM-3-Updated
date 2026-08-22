import React from "react";
import { FindingsPage } from "@/components/common/FindingsPage";
import { Send } from "lucide-react";

export default function Telegram() {
  return (
    <FindingsPage
      module="telegram" screen="telegram" title="Telegram Monitoring"
      subtitle="Channels & groups (configure Telegram API in Intelligence Sources to enable)"
      icon={Send} platformOptions={["Telegram"]}
      moduleFilters={[{ key: "category", label: "Finding Type", facetKey: "category" }]}
    />
  );
}
