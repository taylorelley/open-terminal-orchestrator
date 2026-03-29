import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Terminal, Eye, EyeOff, Shield } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { signIn, signUp, signInWithOIDC, authMethod, oidcConfigured } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const oidcError = searchParams.get('error');
  const showLocalAuth = authMethod !== 'oidc';
  const showOIDC = oidcConfigured && authMethod !== 'local';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const { error: authError } = isSignUp
      ? await signUp(email, password)
      : await signIn(email, password);

    if (authError) {
      setError(authError.message);
      setLoading(false);
    } else {
      navigate('/admin');
    }
  };

  const oidcErrorMessage = oidcError
    ? { oidc_not_configured: 'SSO is not configured.', oidc_denied: 'Authentication was denied by the provider.', oidc_invalid: 'Invalid authentication response.', oidc_failed: 'Authentication failed. Please try again.' }[oidcError] || 'Authentication error.'
    : null;

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-teal-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-sky-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 bg-teal-500 rounded-xl flex items-center justify-center mb-4 shadow-lg shadow-teal-500/20">
            <Terminal className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-xl font-bold text-white">Open Terminal Orchestrator</h1>
          <p className="text-sm text-zinc-500 mt-1">Sandbox Management Console</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4">
          {(error || oidcErrorMessage) && (
            <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error || oidcErrorMessage}
            </p>
          )}

          {showOIDC && (
            <>
              <button
                type="button"
                onClick={signInWithOIDC}
                className="w-full flex items-center justify-center gap-2 py-2.5 bg-sky-600 hover:bg-sky-500 text-white text-sm font-medium rounded-lg transition-colors"
              >
                <Shield className="w-4 h-4" />
                Sign in with SSO
              </button>

              {showLocalAuth && (
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-px bg-zinc-800" />
                  <span className="text-xs text-zinc-600">or</span>
                  <div className="flex-1 h-px bg-zinc-800" />
                </div>
              )}
            </>
          )}

          {showLocalAuth && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:border-teal-500 transition-all"
                  placeholder="admin@example.com"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-3 py-2 pr-10 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:border-teal-500 transition-all"
                    placeholder="Enter password"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Please wait...' : isSignUp ? 'Create Account' : 'Sign In'}
              </button>

              <button
                type="button"
                onClick={() => { setIsSignUp(!isSignUp); setError(''); }}
                className="w-full text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                {isSignUp ? 'Already have an account? Sign in' : 'Need an account? Create one'}
              </button>
            </form>
          )}
        </div>

        <p className="text-center text-[11px] text-zinc-600 mt-6">
          Secure Terminal Sandboxes for Open WebUI
        </p>
      </div>
    </div>
  );
}
