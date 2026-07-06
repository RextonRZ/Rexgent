"use client";

import { ExportEditor } from "@/components/export/ExportEditor";
import { PageHeader } from "@/components/shared/PageHeader";

export default function ExportPage({ params }: { params: { id: string } }) {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Edit & Export"
        sub="Arrange your shots, fix any take with AI, preview the cut in a phone frame, then render the episode."
      />
      <ExportEditor projectId={params.id} />
    </div>
  );
}
