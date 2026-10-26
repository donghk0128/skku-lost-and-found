import React, { createContext, useContext, useEffect, useState } from "react";
import { ApiError, authApi, type AuthResponse, type User } from "@/lib/auth-api";
import { readSession, writeSession } from "@/lib/session-storage";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  initializationError: string;
  signOut: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, nickname: string, password: string) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export default function AuthProvider({ children }: { children: React.ReactNode }) {
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
          setInitializationError(error instanceof Error ? error.message : "로그인 정보를 확인하지 못했습니다.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void initializeAuth();
    return () => { active = false; };
  }, []);

  async function acceptSession(response: AuthResponse) {
    await writeSession({ access_token: response.access_token, refresh_token: response.refresh_token });
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
    await writeSession(null);
    setInitializationError("");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, initializationError, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth는 AuthProvider 안에서 사용해야 합니다.");
  return context;
}
