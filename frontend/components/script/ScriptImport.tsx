"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useParseScript } from "@/hooks/useScript";

interface ScriptImportProps {
  projectId: string;
  onSuccess: (data: {
    script_id: string;
    raw_text: string;
    structured_json: Record<string, unknown>;
    characters_mentioned: string[];
  }) => void;
}

export function ScriptImport({ projectId, onSuccess }: ScriptImportProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const parseScript = useParseScript();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setSelectedFile(acceptedFiles[0]);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        [".docx"],
      "text/plain": [".txt"],
    },
    maxFiles: 1,
  });

  const handleUpload = async () => {
    if (!selectedFile) return;
    const result = await parseScript.mutateAsync({
      file: selectedFile,
      projectId,
    });
    onSuccess(result);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Import Script</CardTitle>
      </CardHeader>
      <CardContent>
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            isDragActive
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-primary/50"
          }`}
        >
          <input {...getInputProps()} />
          {selectedFile ? (
            <p className="text-sm">{selectedFile.name}</p>
          ) : isDragActive ? (
            <p className="text-sm text-primary">Drop the script here...</p>
          ) : (
            <div>
              <p className="text-sm text-muted-foreground">
                Drag & drop a script file here, or click to browse
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Supports PDF, DOCX, TXT
              </p>
            </div>
          )}
        </div>
        {selectedFile && (
          <Button
            onClick={handleUpload}
            disabled={parseScript.isPending}
            className="mt-4 w-full"
          >
            {parseScript.isPending
              ? "Parsing with Qwen-Max..."
              : "Parse Script"}
          </Button>
        )}
        {parseScript.isError && (
          <p className="text-sm text-destructive mt-2">
            Error: {(parseScript.error as Error).message}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
