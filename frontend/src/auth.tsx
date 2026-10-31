import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { Theme, User } from "./types";

type AuthValue = {
  user: User | null;
  ready: boolean;
  setUser: (user: User | null) => void;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  async function refresh() {
    try {
      setUser(await api<User>("/api/me"));
    } catch {
      setUser(null);
    } finally {
      setReady(true);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      ready,
      setUser,
      refresh,
      logout: async () => {
        await api("/api/auth/logout", { method: "POST" });
        setUser(null);
      },
    }),
    [user, ready],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("Auth is unavailable");
  return value;
}

export function useThemeMode(theme: Theme | null) {
  useEffect(() => {
    const stored = (localStorage.getItem("top25-theme") as Theme | null) ?? "system";
    const choice = theme ?? stored;
    const apply = () => {
      const dark = choice === "dark" || (choice === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
      document.documentElement.dataset.theme = dark ? "dark" : "light";
    };
    apply();
    if (choice !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
}
