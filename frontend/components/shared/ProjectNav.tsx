"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { label: "Script", path: "script" },
  { label: "Characters", path: "characters" },
  { label: "Storyboard", path: "storyboard" },
  { label: "Generate", path: "generate" },
  { label: "Edit", path: "edit" },
  { label: "Export", path: "export" },
];

export function ProjectNav({ projectId }: { projectId: string }) {
  const pathname = usePathname();

  return (
    <nav className="flex gap-1 border-b mb-6">
      {NAV_ITEMS.map((item) => {
        const href = `/projects/${projectId}/${item.path}`;
        const isActive = pathname?.includes(`/${item.path}`);
        return (
          <Link
            key={item.path}
            href={href}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
              isActive
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
