"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

const ORDER = ["script", "characters", "storyboard", "generate", "export"];
const LABELS: Record<string, string> = {
  characters: "Characters",
  storyboard: "Storyboard",
  generate: "Generate",
  export: "Edit & Export",
};

/** Bottom-right "Next: <step> →" link so each pipeline page hands off to the next. */
export function NextStepButton({
  projectId,
  current,
}: {
  projectId: string;
  current: string;
}) {
  const next = ORDER[ORDER.indexOf(current) + 1];
  if (!next) return null;
  return (
    <div className="flex justify-end pt-2">
      <Link href={`/projects/${projectId}/${next}`}>
        <Button variant="outline">Next: {LABELS[next]} →</Button>
      </Link>
    </div>
  );
}
