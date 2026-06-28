"use client";

import { useState, useCallback } from "react";
import Editor from "@monaco-editor/react";
import { Button } from "@/components/ui/button";
import { useUpdateScript } from "@/hooks/useScript";

interface ScriptEditorProps {
  scriptId: string;
  initialContent: string;
}

export function ScriptEditor({ scriptId, initialContent }: ScriptEditorProps) {
  const [content, setContent] = useState(initialContent);
  const [hasChanges, setHasChanges] = useState(false);
  const updateScript = useUpdateScript();

  const handleChange = useCallback(
    (value: string | undefined) => {
      if (value !== undefined) {
        setContent(value);
        setHasChanges(value !== initialContent);
      }
    },
    [initialContent]
  );

  const handleSave = async () => {
    await updateScript.mutateAsync({ scriptId, rawText: content });
    setHasChanges(false);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Script Editor</h3>
        <Button
          onClick={handleSave}
          disabled={!hasChanges || updateScript.isPending}
          size="sm"
          variant={hasChanges ? "default" : "outline"}
        >
          {updateScript.isPending
            ? "Saving..."
            : hasChanges
            ? "Save Changes"
            : "Saved"}
        </Button>
      </div>
      <div className="border rounded-lg overflow-hidden">
        <Editor
          height="500px"
          defaultLanguage="plaintext"
          value={content}
          onChange={handleChange}
          options={{
            minimap: { enabled: false },
            wordWrap: "on",
            fontSize: 14,
            lineNumbers: "on",
            scrollBeyondLastLine: false,
          }}
        />
      </div>
    </div>
  );
}
