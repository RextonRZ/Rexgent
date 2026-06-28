"use client";

import { useState } from "react";
import { ScriptImport } from "@/components/script/ScriptImport";

export default function ScriptPage({ params }: { params: { id: string } }) {
  const [parsedData, setParsedData] = useState<Record<
    string,
    unknown
  > | null>(null);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Script</h1>
      {!parsedData ? (
        <ScriptImport
          projectId={params.id}
          onSuccess={(data) => setParsedData(data.structured_json)}
        />
      ) : (
        <pre className="bg-muted p-4 rounded-lg text-sm overflow-auto max-h-96">
          {JSON.stringify(parsedData, null, 2)}
        </pre>
      )}
    </div>
  );
}
