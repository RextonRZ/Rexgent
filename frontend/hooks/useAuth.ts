import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { useAuthStore, type AuthUser } from "@/store/auth";

interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

interface RegisterBody {
  email: string;
  password: string;
  full_name?: string;
  persona?: string;
}

/** Current auth state (token + user) read from the persisted store. */
export function useAuth() {
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  return { token, user, isAuthenticated: Boolean(token) };
}

export function useLogin() {
  const setAuth = useAuthStore((s) => s.setAuth);
  return useMutation({
    mutationFn: async (body: { email: string; password: string }) => {
      const { data } = await api.post<AuthResponse>("/api/auth/login", body);
      return data;
    },
    onSuccess: (data) => {
      // a fresh login re-arms the "connect your key" prompt for this session
      if (typeof window !== "undefined")
        sessionStorage.removeItem("byok-prompt-dismissed");
      setAuth(data.access_token, data.user);
    },
  });
}

export function useRegister() {
  const setAuth = useAuthStore((s) => s.setAuth);
  return useMutation({
    mutationFn: async (body: RegisterBody) => {
      const { data } = await api.post<AuthResponse>("/api/auth/register", body);
      return data;
    },
    onSuccess: (data) => {
      if (typeof window !== "undefined")
        sessionStorage.removeItem("byok-prompt-dismissed");
      setAuth(data.access_token, data.user);
    },
  });
}

export function useLogout() {
  const clear = useAuthStore((s) => s.clear);
  const queryClient = useQueryClient();
  const router = useRouter();
  return () => {
    clear();
    queryClient.clear();
    router.push("/login");
  };
}
