"use client";

import { ExportEditor } from "@/components/export/ExportEditor";

export default function ExportPage({ params }: { params: { id: string } }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Edit &amp; Export</h1>
        <p className="text-sm text-muted-foreground">
          Arrange your shots, AI-edit any take (click a clip → ✏️), preview the
          cut, then render the final film.
        </p>
      </div>
      <ExportEditor projectId={params.id} />
    </div>
  );
}
