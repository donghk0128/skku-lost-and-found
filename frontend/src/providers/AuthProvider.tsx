import React, { createContext, useContext, useEffect, useState } from "react";
import {
  ApiError,
  authApi,
  type AuthResponse,
  type User,
} from "@/lib/auth-api";
import { readSession, writeSession } from "@/lib/session-storage";
import { t } from "@/i18n";
import { clearPush } from "@/lib/push-client";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  initializationError: string;
  signOut: () => Promise<void>;
  clearAccount: () => Promise<void>;
  updateUser: (user: User) => void;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, nickname: string, password: string) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export default function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [initializationError, setInitializationError] = useState("");

  useEffect(() => {
    let active = true;
    async function initializeAuth() {
      try {
        const session = await readSession();
        if (!session) return;
        let restoredUser: User;
        try {
          restoredUser = await authApi.me(session.access_token);
        } catch (error) {
          if (!(error instanceof ApiError) || error.status !== 401) throw error;
          const refreshed = await authApi.refresh(session.refresh_token);
          session.access_token = refreshed.access_token;
          restoredUser = await authApi.me(session.access_token);
          if (active) await writeSession(session);
        }
        if (active) setUser(restoredUser);
      } catch (error) {
        if (active) {
          if (error instanceof ApiError && error.status === 401) {
            await writeSession(null).catch(() => undefined);
          }
          setInitializationError(
            error instanceof Error
              ? error.message
              : t("auth.restoreFailed"),
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void initializeAuth();
    return () => {
      active = false;
    };
  }, []);

  async function acceptSession(response: AuthResponse) {
    await clearPush().catch(() => undefined);
    await writeSession({
      access_token: response.access_token,
      refresh_token: response.refresh_token,
    });
    setInitializationError("");
    setUser(response.user);
  }

  async function signIn(email: string, password: string) {
    await acceptSession(await authApi.signIn(email, password));
  }

  async function signUp(email: string, nickname: string, password: string) {
    await acceptSession(await authApi.signUp(email, nickname, password));
  }

  async function signOut() {
    const session = await readSession();
    if (session) {
      try {
        await authApi.signOut(session.refresh_token);
      } catch (error) {
        // Invalid or expired refresh tokens are already unusable.
        if (!(error instanceof ApiError) || error.status !== 401) throw error;
      }
    }
    await clearPush().catch(() => undefined);
    await writeSession(null);
    setInitializationError("");
    setUser(null);
  }

  async function clearAccount() {
    try { await clearPush().catch(() => undefined); await writeSession(null); }
    finally { setUser(null); setInitializationError(""); }
  }

  return (
    <AuthContext.Provider
      value={{ user, loading, initializationError, signIn, signUp, signOut, clearAccount, updateUser: setUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context)
    throw new Error(t("auth.providerRequired"));
  return context;
}
