"use client";

import { useState } from "react";
import { ScriptImport } from "@/components/script/ScriptImport";
import { ScriptGenerate } from "@/components/script/ScriptGenerate";
import { ScriptEditor } from "@/components/script/ScriptEditor";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function ScriptPage({ params }: { params: { id: string } }) {
  const [scriptData, setScriptData] = useState<{
    script_id: string;
    raw_text: string;
  } | null>(null);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Script</h1>

      {!scriptData ? (
        <Tabs defaultValue="generate">
          <TabsList>
            <TabsTrigger value="generate">Write from Scratch</TabsTrigger>
            <TabsTrigger value="import">Import Script</TabsTrigger>
          </TabsList>
          <TabsContent value="generate">
            <ScriptGenerate
              projectId={params.id}
              onSuccess={(data) =>
                setScriptData({
                  script_id: data.script_id,
                  raw_text: data.raw_text,
                })
              }
            />
          </TabsContent>
          <TabsContent value="import">
            <ScriptImport
              projectId={params.id}
              onSuccess={(data) =>
                setScriptData({
                  script_id: data.script_id,
                  raw_text: data.raw_text,
                })
              }
            />
          </TabsContent>
        </Tabs>
      ) : (
        <ScriptEditor
          scriptId={scriptData.script_id}
          initialContent={scriptData.raw_text}
        />
      )}
    </div>
  );
}
