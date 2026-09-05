import { create } from "zustand";
import { authApi, setAccessToken } from "../services/api";
import type { AccountType, User } from "../types";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  connectionError: string | null;
  login: (accountType: AccountType, username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  fetchMe: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null, isLoading: true, isAuthenticated: false, connectionError: null,
  login: async (accountType, username, password) => {
    const token = await authApi.login(accountType, username, password);
    setAccessToken(token.access_token);
    const user = await authApi.me();
    set({ user, isAuthenticated: true, isLoading: false, connectionError: null });
  },
  logout: async () => {
    try { await authApi.logout(); } catch { /* Always clear local in-memory auth state. */ }
    setAccessToken(null);
    set({ user: null, isAuthenticated: false, isLoading: false, connectionError: null });
  },
  fetchMe: async () => {
    set({ isLoading: true });
    try {
      const token = await authApi.refresh();
      if (!token) {
        setAccessToken(null);
        set({ user: null, isAuthenticated: false, isLoading: false, connectionError: null });
        return;
      }
      const user = await authApi.me();
      set({ user, isAuthenticated: true, isLoading: false, connectionError: null });
    } catch {
      set({ isLoading: false, connectionError: "Backend is temporarily unavailable. Your session has not been cleared." });
    }
  },
}));
