import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, getToken, setToken } from "../api/client";
import type { Me, Role, TokenOut } from "../api/types";

interface AuthApi {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string, role?: Role) => Promise<Me>;
  register: (data: Record<string, unknown>) => Promise<Me>;
  switchRole: (role: Role) => Promise<Me>;
  logout: () => void;
}

const AuthContext = createContext<AuthApi | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState<boolean>(getToken() !== null);
  const queryClient = useQueryClient();

  const loadMe = useCallback(async () => {
    const data = await api<Me>("/auth/me");
    setMe(data);
    return data;
  }, []);

  useEffect(() => {
    if (!getToken()) return;
    loadMe()
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, [loadMe]);

  useEffect(() => {
    const onExpired = () => {
      setMe(null);
      queryClient.clear();
    };
    window.addEventListener("fsp-auth-expired", onExpired);
    return () => window.removeEventListener("fsp-auth-expired", onExpired);
  }, [queryClient]);

  const finish = useCallback(
    async (token: TokenOut) => {
      setToken(token.access_token);
      queryClient.clear();
      return loadMe();
    },
    [loadMe, queryClient],
  );

  const value = useMemo<AuthApi>(
    () => ({
      me,
      loading,
      login: async (email, password, role) => finish(await api<TokenOut>("/auth/login", { method: "POST", body: { email, password, role } })),
      register: async (data) => finish(await api<TokenOut>("/auth/register", { method: "POST", body: data })),
      switchRole: async (role) => finish(await api<TokenOut>("/auth/switch-role", { method: "POST", body: { role } })),
      logout: () => {
        setToken(null);
        setMe(null);
        queryClient.clear();
      },
    }),
    [me, loading, finish, queryClient],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthApi {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("AuthProvider отсутствует");
  return ctx;
}
