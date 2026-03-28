import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';

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

  useEffect(() => {
    // Check both Supabase auth and OIDC session in parallel.
    const checkAuth = async () => {
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

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
    });

    return () => subscription.unsubscribe();
  }, []);

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return { error: error as Error | null };
  };

  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({ email, password });
    return { error: error as Error | null };
  };

  const signInWithOIDC = () => {
    window.location.href = '/admin/api/auth/oidc/login';
  };

  const signOut = async () => {
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

  const isAuthenticated = !!(session?.user || oidcSession);

  return (
    <AuthContext.Provider
      value={{
        session,
        user: session?.user ?? null,
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
