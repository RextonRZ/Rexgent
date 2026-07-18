"use client";

import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { UploadCloud, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useParseScript } from "@/hooks/useScript";
import { useProject, useUpdateProject } from "@/hooks/useProjects";
import { DramaLookFields } from "@/components/shared/DramaLookFields";
import { PHOTOREAL } from "@/lib/styles";
import type { VideoRatio } from "@/lib/types/project";
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
  const { data: project } = useProject(projectId);
  const updateProject = useUpdateProject();

  // local state answers clicks instantly; the effect re-seeds it whenever the
  // saved project changes (first load, or a PATCH round trip)
  const [genre, setGenre] = useState("sci-fi");
  const [visualStyle, setVisualStyle] = useState<string>(PHOTOREAL);
  const [ratio, setRatio] = useState<VideoRatio>("9:16");
  useEffect(() => {
    if (!project) return;
    setGenre(project.genre ?? "sci-fi");
    setVisualStyle(project.visual_style ?? PHOTOREAL);
    setRatio(project.video_ratio === "16:9" ? "16:9" : "9:16");
  }, [project]);

  // instant save: the backend PATCH validates the ratio and normalizes the
  // style ("photoreal" clears it to NULL, the classic cinematic look)
  const save = (body: {
    genre?: string;
    visual_style?: string;
    video_ratio?: VideoRatio;
  }) => updateProject.mutate({ projectId, ...body });

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
      "text/plain": [".txt", ".fountain"],
      "text/markdown": [".md"],
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
                or click to browse: PDF, DOCX, TXT, MD, Fountain
              </p>
            </>
          )}
        </div>
      </div>

      {/* the look picked at creation, editable here: an imported drama should
          not be stuck with rushed create-time defaults */}
      <DramaLookFields
        genre={genre}
        visualStyle={visualStyle}
        ratio={ratio}
        onGenre={(v) => {
          setGenre(v);
          save({ genre: v });
        }}
        onStyle={(v) => {
          setVisualStyle(v);
          save({ visual_style: v });
        }}
        onRatio={(v) => {
          setRatio(v);
          save({ video_ratio: v });
        }}
      />
      <p className="text-center text-xs text-muted-foreground">
        Your script sets the story and length. Genre, visual style and format
        save as you pick them. The spend cap still applies and can be changed
        on the storyboard page.
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
