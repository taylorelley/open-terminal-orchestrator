import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase, isLocalMode } from '../lib/supabase';
import {
  localSignIn,
  localSignUp,
  localSession,
  authConfig,
  getLocalToken,
  setLocalToken,
  clearLocalToken,
} from '../lib/api';

interface OIDCSession {
  sub: string;
  email: string;
  name: string;
  groups: string[];
}

interface AuthContextType {
  session: Session | null;
  user: User | null;
  oidcSession: OIDCSession | null;
  loading: boolean;
  authMethod: 'local' | 'oidc' | 'both';
  oidcConfigured: boolean;
  isAuthenticated: boolean;
  signIn: (email: string, password: string) => Promise<{ error: Error | null }>;
  signUp: (email: string, password: string) => Promise<{ error: Error | null }>;
  signInWithOIDC: () => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [oidcSession, setOidcSession] = useState<OIDCSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [authMethod, setAuthMethod] = useState<'local' | 'oidc' | 'both'>('local');
  const [oidcConfigured, setOidcConfigured] = useState(false);

  // Local-mode synthetic user object used to satisfy `isAuthenticated`.
  const [localUser, setLocalUser] = useState<{ id: string; email: string } | null>(null);

  useEffect(() => {
    const checkAuth = async () => {
      if (isLocalMode) {
        // ---- Local mode: validate stored token via backend ----
        const token = getLocalToken();
        if (token) {
          try {
            const info = await localSession();
            if (info.authenticated) {
              setLocalUser({ id: info.sub!, email: info.email! });
            } else {
              clearLocalToken();
            }
          } catch {
            clearLocalToken();
          }
        }

        // Fetch auth config from backend (may provide OIDC info even in local mode).
        try {
          const cfg = await authConfig();
          setAuthMethod(cfg.auth_method as 'local' | 'oidc' | 'both');
          setOidcConfigured(cfg.oidc_configured);
        } catch {
          // Backend might be unreachable; keep defaults.
        }

        setLoading(false);
        return;
      }

      // ---- Supabase mode ----
      const [supabaseResult, authConfigResult, oidcSessionResult] = await Promise.allSettled([
        supabase.auth.getSession(),
        fetch('/admin/api/auth/config').then(r => r.ok ? r.json() : null),
        fetch('/admin/api/auth/session').then(r => r.ok ? r.json() : null),
      ]);

      if (supabaseResult.status === 'fulfilled') {
        setSession(supabaseResult.value.data.session);
      }

      if (authConfigResult.status === 'fulfilled' && authConfigResult.value) {
        setAuthMethod(authConfigResult.value.auth_method || 'local');
        setOidcConfigured(authConfigResult.value.oidc_configured || false);
      }

      if (oidcSessionResult.status === 'fulfilled' && oidcSessionResult.value?.authenticated) {
        setOidcSession({
          sub: oidcSessionResult.value.sub,
          email: oidcSessionResult.value.email,
          name: oidcSessionResult.value.name,
          groups: oidcSessionResult.value.groups,
        });
      }

      setLoading(false);
    };

    checkAuth();

    if (!isLocalMode) {
      const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
        setSession(s);
      });
      return () => subscription.unsubscribe();
    }
  }, []);

  const signIn = async (email: string, password: string) => {
    if (isLocalMode) {
      try {
        const res = await localSignIn(email, password);
        setLocalToken(res.token);
        setLocalUser(res.user);
        return { error: null };
      } catch (e) {
        return { error: e as Error };
      }
    }
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return { error: error as Error | null };
  };

  const signUp = async (email: string, password: string) => {
    if (isLocalMode) {
      try {
        const res = await localSignUp(email, password);
        setLocalToken(res.token);
        setLocalUser(res.user);
        return { error: null };
      } catch (e) {
        return { error: e as Error };
      }
    }
    const { error } = await supabase.auth.signUp({ email, password });
    return { error: error as Error | null };
  };

  const signInWithOIDC = () => {
    window.location.href = '/admin/api/auth/oidc/login';
  };

  const signOut = async () => {
    if (isLocalMode) {
      clearLocalToken();
      setLocalUser(null);
      return;
    }

    // Sign out of both Supabase and OIDC.
    if (oidcSession) {
      try {
        const resp = await fetch('/admin/api/auth/oidc/logout', { method: 'POST' });
        const data = await resp.json();
        setOidcSession(null);
        if (data.logout_url) {
          window.location.href = data.logout_url;
          return;
        }
      } catch {
        // Fall through to Supabase signout.
      }
    }
    await supabase.auth.signOut();
  };

  const isAuthenticated = !!(session?.user || oidcSession || localUser);

  return (
    <AuthContext.Provider
      value={{
        session,
        user: session?.user ?? (localUser ? { id: localUser.id, email: localUser.email } as unknown as User : null),
        oidcSession,
        loading,
        authMethod,
        oidcConfigured,
        isAuthenticated,
        signIn,
        signUp,
        signInWithOIDC,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
