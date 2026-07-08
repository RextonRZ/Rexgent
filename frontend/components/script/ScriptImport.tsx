"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { UploadCloud, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useParseScript } from "@/hooks/useScript";
import { errText } from "@/lib/errText";

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
    <div className="space-y-4">
      {/* one frame: the dropzone IS the panel */}
      <div
        {...getRootProps()}
        className={`rounded-xl border-2 border-dashed px-8 py-14 text-center cursor-pointer transition-colors ${
          isDragActive
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50 hover:bg-secondary/30"
        }`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-3">
          <div
            className={`flex h-14 w-14 items-center justify-center rounded-full ${
              selectedFile ? "bg-primary/15" : "bg-secondary"
            }`}
          >
            {selectedFile ? (
              <FileText className="h-6 w-6 text-primary" />
            ) : (
              <UploadCloud className="h-6 w-6 text-muted-foreground" />
            )}
          </div>
          {selectedFile ? (
            <>
              <p className="text-sm font-medium">{selectedFile.name}</p>
              <p className="text-xs text-muted-foreground">
                Click to choose a different file
              </p>
            </>
          ) : (
            <>
              <p className="text-sm font-medium">
                {isDragActive
                  ? "Drop the script here"
                  : "Drag & drop your script"}
              </p>
              <p className="text-xs text-muted-foreground">
                or click to browse — PDF, DOCX, TXT
              </p>
            </>
          )}
        </div>
      </div>

      {/* imports need no extra settings: the script itself carries the story,
          tone and length; the genre, format and spend cap picked at creation
          still shape everything downstream */}
      <p className="text-center text-xs text-muted-foreground">
        No other settings needed. Your script sets the story and length; the
        genre, format and spend cap you picked at creation still apply.
      </p>

      {selectedFile && (
        <Button
          onClick={handleUpload}
          disabled={parseScript.isPending}
          className="w-full"
        >
          {parseScript.isPending ? "Parsing with Qwen-Max..." : "Parse Script"}
        </Button>
      )}
      {parseScript.isError && (
        <p className="text-sm text-bad">
          Error: {errText(parseScript.error)}
        </p>
      )}
    </div>
  );
}
