"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useProjects, useCreateProject } from "@/hooks/useProjects";

export default function HomePage() {
  const router = useRouter();
  const { data } = useProjects();
  const createProject = useCreateProject();
  const [title, setTitle] = useState("");

  const handleCreate = async () => {
    const project = await createProject.mutateAsync({
      title: title || "Untitled Drama",
    });
    router.push(`/projects/${project.id}/script`);
  };

  const projects = data?.projects || [];

  return (
    <main className="max-w-2xl mx-auto p-8 space-y-8">
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-bold">Rexgent</h1>
        <p className="text-muted-foreground">
          Give me a story idea. I&apos;ll hand you back a short drama.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6 flex gap-2">
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="New project title"
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          <Button onClick={handleCreate} disabled={createProject.isPending}>
            {createProject.isPending ? "Creating..." : "New Project"}
          </Button>
        </CardContent>
      </Card>

      {projects.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-muted-foreground">
            Your projects
          </h2>
          {projects.map((p) => (
            <Link key={p.id} href={`/projects/${p.id}/script`}>
              <Card className="hover:shadow-md transition-shadow">
                <CardContent className="py-3 flex items-center justify-between">
                  <span className="font-medium">{p.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {p.genre || "—"}
                  </span>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
