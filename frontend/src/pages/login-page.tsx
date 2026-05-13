/**
 * LoginPage — formulaire mono-user (V1).
 * Style cockpit, mobile-first (centré, plein écran).
 */

import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';

import { ApiError } from '@/lib/api/client';
import { useLogin, useMe } from '@/lib/api/queries';
import { APP_NAME } from '@/lib/constants';
import { useAuthStore } from '@/lib/store/auth';
import { loginSchema } from '@/lib/validation/auth';

export function LoginPage(): JSX.Element {
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const setToken = useAuthStore((s) => s.setToken);
  const me = useMe(Boolean(token));
  const login = useLogin();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (token && me.data) {
    return <Navigate to="/" replace />;
  }

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    const parsed = loginSchema.safeParse({ email, password });
    if (!parsed.success) {
      setError('Email ou mot de passe invalides.');
      return;
    }
    try {
      const res = await login.mutateAsync(parsed.data);
      setToken(res.access_token);
      navigate('/', { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Connexion impossible.');
      }
    }
  };

  return (
    <main className="flex h-full items-center justify-center bg-eldir-paper p-4">
      <div className="w-full max-w-sm rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-6 md:p-8">
        <header className="mb-6 text-center">
          <div className="font-mono text-base font-bold tracking-wider">
            {APP_NAME.toUpperCase()}
            <span className="text-eldir-orange">·</span>CTL
          </div>
          <div className="eldir-caps mt-1">Mission Control · login</div>
        </header>

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <label className="block">
            <span className="eldir-caps mb-1 block">Email</span>
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
            />
          </label>

          <label className="block">
            <span className="eldir-caps mb-1 block">Mot de passe</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
            />
          </label>

          {error && (
            <div className="rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-xs text-eldir-red">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={login.isPending}
            className="rounded-eldir bg-eldir-orange px-4 py-3 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
          >
            {login.isPending ? 'connexion…' : 'se connecter'}
          </button>
        </form>
      </div>
    </main>
  );
}
