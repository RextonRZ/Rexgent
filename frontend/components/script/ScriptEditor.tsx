"use client";

import { useState, useCallback } from "react";
import Editor from "@monaco-editor/react";
import { Button } from "@/components/ui/button";
import { useUpdateScript } from "@/hooks/useScript";

interface ScriptEditorProps {
  scriptId: string;
  initialContent: string;
  onTextChange?: (text: string) => void;
}

export function ScriptEditor({
  scriptId,
  initialContent,
  onTextChange,
}: ScriptEditorProps) {
  const [content, setContent] = useState(initialContent);
  const [savedContent, setSavedContent] = useState(initialContent);
  const [justSaved, setJustSaved] = useState(false);
  const updateScript = useUpdateScript();

  const hasChanges = content !== savedContent;

  const handleChange = useCallback(
    (value: string | undefined) => {
      if (value !== undefined) {
        setContent(value);
        setJustSaved(false);
        onTextChange?.(value);
      }
    },
    [onTextChange]
  );

  const handleSave = async () => {
    await updateScript.mutateAsync({ scriptId, rawText: content });
    setSavedContent(content);
    setJustSaved(true);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold">Script Editor</h3>
        <div className="flex items-center gap-2">
          {justSaved && (
            <span className="text-[11px] text-muted-foreground">
              Saved — re-run Characters/Storyboard to apply story changes
            </span>
          )}
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
      </div>
      <div className="border hairline rounded-lg overflow-hidden">
        <Editor
          height="500px"
          defaultLanguage="plaintext"
          theme="vs-dark"
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
