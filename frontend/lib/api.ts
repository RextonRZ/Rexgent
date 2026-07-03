import axios from "axios";
import { useAuthStore } from "@/store/auth";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  // Backstop so a slow/hung request surfaces as an error instead of hanging the
  // UI forever. Generous enough for the slowest inline calls (plate/voice gen).
  timeout: 120000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach the JWT to every request when the user is signed in.
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url: string = error.config?.url || "";
    const isAuthCall = url.includes("/api/auth/");
    // An expired/invalid session on a protected call: sign out and bounce to login.
    if (error.response?.status === 401 && !isAuthCall) {
      useAuthStore.getState().clear();
      if (
        typeof window !== "undefined" &&
        !window.location.pathname.startsWith("/login")
      ) {
        window.location.href = "/login";
      }
    }
    const message = error.response?.data?.detail || error.message;
    console.error("API Error:", message);
    return Promise.reject(error);
  }
);

export default api;
