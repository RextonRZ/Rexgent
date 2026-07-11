import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import api from "@/lib/api";
import { getSocket } from "@/lib/websocket";
import type { Script } from "@/lib/types";

export function useScript(scriptId: string | null) {
  return useQuery<Script>({
    queryKey: ["script", scriptId],
    queryFn: async () => {
      const { data } = await api.get(`/api/script/${scriptId}`);
      return data;
    },
    enabled: !!scriptId,
  });
}

/** The project's most recent script, so opening an existing project resumes into
 *  the editor. 404 (no script yet) is expected for brand-new projects.
 *  Self-healing: a finished script stage refetches this over the websocket, so
 *  the editor gets the new draft even when the HTTP request that wrote it
 *  died mid-flight (proxy drop, backend restart, long generation). */
export function useLatestScript(projectId: string) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!projectId) return;
    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });
    const onStage = (p: { stage?: string; status?: string }) => {
      if (p.stage === "script" && p.status === "completed") {
        queryClient.invalidateQueries({ queryKey: ["latest-script", projectId] });
      }
    };
    socket.on("stage:progress", onStage);
    return () => {
      socket.off("stage:progress", onStage);
    };
  }, [projectId, queryClient]);

  return useQuery<Script>({
    queryKey: ["latest-script", projectId],
    queryFn: async () => {
      const { data } = await api.get(
        `/api/script/project/${projectId}/latest`
      );
      return data;
    },
    enabled: !!projectId,
    retry: false,
  });
}

/** Write (or rewrite) the screenplay. `notes` carries the judge's critique on
 *  a rewrite pass so the new draft actually fixes what failed. */
export function useGenerateScript() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: {
      project_id: string;
      premise: string;
      genre: string;
      tone?: string;
      episode_count?: number;
      target_length?: number;
      notes?: string;
      language?: string;
    }) => {
      const { data } = await api.post("/api/script/generate", params, {
        timeout: 420000,
      });
      return data as {
        script_id: string;
        raw_text: string;
      };
    },
    onSuccess: (_data, params) => {
      queryClient.invalidateQueries({
        queryKey: ["latest-script", params.project_id],
      });
      queryClient.invalidateQueries({
        queryKey: ["progress", params.project_id],
      });
    },
  });
}

export function useUpdateScript() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      scriptId,
      rawText,
    }: {
      scriptId: string;
      rawText: string;
    }) => {
      const { data } = await api.patch(`/api/script/${scriptId}`, {
        raw_text: rawText,
      });
      return data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["script", variables.scriptId],
      });
    },
  });
}

export function useParseScript() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      projectId,
    }: {
      file: File;
      projectId: string;
    }) => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("project_id", projectId);

      const { data } = await api.post("/api/script/parse", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["script"] });
    },
  });
}
