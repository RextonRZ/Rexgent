import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface CostumeVariant {
  id: string;
  label: string;
  outfit_description: string | null;
  plate_image_url: string | null;
  is_default: boolean;
  plate_status: string;
}

export interface CastingCharacter {
  id: string;
  name: string;
  variants: CostumeVariant[];
}

export interface LocationPlate {
  id: string;
  location_key: string;
  description: string | null;
  plate_image_url: string | null;
}

export interface StylePreset {
  style_tags: string[];
  plate_image_url: string | null;
}

export interface Bible {
  auto_approve_casting: boolean;
  characters: CastingCharacter[];
  locations: LocationPlate[];
  style: StylePreset | null;
}

export function useBible(projectId: string) {
  return useQuery<Bible>({
    queryKey: ["bible", projectId],
    queryFn: async () => {
      const { data } = await api.get(`/api/casting/${projectId}`);
      return data;
    },
    enabled: !!projectId,
  });
}

export function useApproveCasting(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/api/casting/${projectId}/approve`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bible", projectId] });
    },
  });
}

export function useRegenerateVariant() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (variantId: string) => {
      const { data } = await api.post(
        `/api/casting/variant/${variantId}/regenerate`
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bible"] });
    },
  });
}

export function useRunCasting(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/api/casting/${projectId}/run`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bible", projectId] });
    },
  });
}

export function useOverrideVariant() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      variantId,
      file,
    }: {
      variantId: string;
      file: File;
    }) => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post(
        `/api/casting/variant/${variantId}/override`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bible"] });
    },
  });
}

export function useDesignVoice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      characterId,
      description,
    }: {
      characterId: string;
      description: string;
    }) => {
      const { data } = await api.post(
        `/api/casting/character/${characterId}/voice/design?description=${encodeURIComponent(
          description
        )}`
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bible"] });
    },
  });
}

export function useCloneVoice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      characterId,
      file,
    }: {
      characterId: string;
      file: File;
    }) => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post(
        `/api/casting/character/${characterId}/voice/clone`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bible"] });
    },
  });
}

/** Fetch a short voice preview; returns an object URL for an <audio> element. */
export async function previewVoice(characterId: string): Promise<string> {
  const { data } = await api.post(
    `/api/casting/character/${characterId}/voice/preview`,
    null,
    { responseType: "blob" }
  );
  return URL.createObjectURL(data as Blob);
}

export function useSetAutoApprove(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (enabled: boolean) => {
      const { data } = await api.patch(
        `/api/casting/${projectId}/auto-approve?enabled=${enabled}`
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bible", projectId] });
    },
  });
}
