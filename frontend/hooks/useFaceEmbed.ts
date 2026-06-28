import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export function useUploadFace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      characterId,
      file,
    }: {
      characterId: string;
      file: File;
    }) => {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await api.post(
        `/api/characters/${characterId}/face`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["characters"] });
    },
  });
}

export function useGenerateAppearance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (characterId: string) => {
      const { data } = await api.post(
        `/api/characters/${characterId}/generate-appearance`
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["characters"] });
    },
  });
}
