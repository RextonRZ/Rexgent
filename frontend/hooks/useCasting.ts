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
