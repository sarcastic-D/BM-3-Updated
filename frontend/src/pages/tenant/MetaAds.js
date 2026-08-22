import React from "react";
import { FindingsPage } from "@/components/common/FindingsPage";
import { Megaphone } from "lucide-react";

export default function MetaAds() {
  return (
    <FindingsPage
      module="meta_ads" screen="meta_ads" title="Meta Ads"
      subtitle="Unauthorized ads impersonating your brand (configure Meta API in Intelligence Sources)"
      icon={Megaphone} platformOptions={["Facebook", "Instagram"]}
      moduleFilters={[{ key: "unauthorized", label: "Unauthorized", options: ["Yes", "No", "Unknown"] }]}
    />
  );
}
