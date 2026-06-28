import { Badge } from "@/components/ui/badge";

const TIER_LABEL: Record<string, string> = {
  wan: "Wan 2.7",
  happyhorse: "HappyHorse 1.1",
  happyhorse_fast: "HappyHorse fast",
};

const TIER_COLOR: Record<string, string> = {
  wan: "bg-amber-500",
  happyhorse: "bg-slate-400",
  happyhorse_fast: "bg-slate-300",
};

export function QualityTierBadge({ tier }: { tier: string }) {
  return (
    <Badge className={TIER_COLOR[tier] || "bg-slate-400"}>
      {TIER_LABEL[tier] || tier}
    </Badge>
  );
}
