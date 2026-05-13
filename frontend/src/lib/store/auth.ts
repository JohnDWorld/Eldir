/**
 * Zustand — auth store (token JWT + persistance localStorage).
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { setAuthToken } from '@/lib/api/client';

interface AuthState {
  token: string | null;
  setToken: (token: string | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      setToken: (token) => {
        setAuthToken(token);
        set({ token });
      },
      logout: () => {
        setAuthToken(null);
        set({ token: null });
      },
    }),
    {
      name: 'eldir.auth',
      onRehydrateStorage: () => (state) => {
        if (state?.token) setAuthToken(state.token);
      },
    },
  ),
);
