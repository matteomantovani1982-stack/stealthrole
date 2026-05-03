"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import {
  User,
  getMe,
  login as apiLogin,
  register as apiRegister,
  logoutServer,
  clearAllUserData,
  isAuthenticated,
  getCurrentUserId,
  setCurrentUserId,
} from "@/lib/api";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  login: async () => {},
  register: async () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    const finish = () => setLoading(false);

    if (isAuthenticated()) {
      // If the API is down / never answers, unblock the shell (don't spin forever)
      timeoutId = setTimeout(finish, 15000);

      getMe()
        .then((me) => {
          if (cancelled) return;
          // SECURITY: if the cached user_id doesn't match the API response,
          // a different user has logged in — wipe all cached data
          const cachedUserId = getCurrentUserId();
          if (cachedUserId && cachedUserId !== me.id) {
            clearAllUserData();
            window.location.href = "/login";
            return;
          }
          if (!cachedUserId) setCurrentUserId(me.id);
          setUser(me);
        })
        /**
         * On 401, request() already cleared tokens — do not clearAllUserData()
         * again (avoids duplicate sr-token-sync + extension churn).
         * On other errors keep session so user can retry.
         */
        .catch(() => setUser(null))
        .finally(() => {
          if (timeoutId) clearTimeout(timeoutId);
          finish();
        });
    } else {
      // Already logged out — do not clear storage (was spamming extension + console on every /login visit).
      setLoading(false);
    }

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await apiLogin(email, password);
      setUser(data.user);
      router.push("/");
    },
    [router]
  );

  const register = useCallback(
    async (email: string, password: string, name?: string) => {
      const data = await apiRegister(email, password, name);
      setUser(data.user);
      router.push("/");
    },
    [router]
  );

  const logout = useCallback(() => {
    // SECURITY: revoke refresh token server-side, then wipe all local data
    logoutServer(); // fire-and-forget — don't block UI
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
