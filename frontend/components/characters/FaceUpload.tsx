"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useUploadFace } from "@/hooks/useFaceEmbed";

interface FaceUploadProps {
  characterId: string;
  hasReference: boolean;
}

export function FaceUpload({ characterId, hasReference }: FaceUploadProps) {
  const [preview, setPreview] = useState<string | null>(null);
  const uploadFace = useUploadFace();

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        const file = acceptedFiles[0];
        setPreview(URL.createObjectURL(file));
        uploadFace.mutate({ characterId, file });
      }
    },
    [characterId, uploadFace]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp"] },
    maxFiles: 1,
  });

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-lg p-3 text-center cursor-pointer text-xs transition-colors ${
        isDragActive
          ? "border-primary bg-primary/5"
          : "border-muted-foreground/25 hover:border-primary/50"
      }`}
    >
      <input {...getInputProps()} />
      {uploadFace.isPending ? (
        <span className="text-primary">Embedding with Qwen-VL...</span>
      ) : preview ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={preview}
          alt="reference preview"
          className="h-16 mx-auto rounded object-cover"
        />
      ) : hasReference ? (
        <span className="text-green-600">Reference set — drop to replace</span>
      ) : (
        <span className="text-muted-foreground">
          Drop a reference photo to lock this face
        </span>
      )}
      {uploadFace.isError && (
        <p className="text-destructive mt-1">
          {(uploadFace.error as Error).message}
        </p>
      )}
    </div>
  );
}
