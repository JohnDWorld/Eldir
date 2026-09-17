/**
 * Thème clair / sombre.
 *
 * Trois préférences : suivre le système (défaut), forcer clair, forcer
 * sombre. Retenue par appareil dans localStorage, pas sur le compte : le
 * téléphone le soir et l'écran du bureau n'ont pas les mêmes besoins.
 *
 * La classe `dark` est posée sur <html> une première fois par le script
 * inline d'index.html, avant le premier affichage, sinon l'appli s'ouvre en
 * clair puis bascule (le flash blanc au lancement de la PWA). Ce module
 * prend ensuite le relais : changement de préférence, et suivi du système
 * quand la préférence est « système ».
 */

import { useEffect } from 'react';
import { create } from 'zustand';

export type ThemePreference = 'system' | 'light' | 'dark';

export const THEME_STORAGE_KEY = 'eldir.theme';

const DARK_QUERY = '(prefers-color-scheme: dark)';

// Barre d'état de la PWA : orange en clair (comme avant), couleur de la
// topbar en sombre pour ne pas plaquer un bandeau vif au-dessus d'une appli
// sombre.
const THEME_COLOR = { light: '#D97757', dark: '#262422' } as const;

export function readThemePreference(): ThemePreference {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY);
    return value === 'light' || value === 'dark' ? value : 'system';
  } catch {
    return 'system';
  }
}

function systemPrefersDark(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia(DARK_QUERY).matches;
}

export function applyTheme(preference: ThemePreference): void {
  const dark = preference === 'dark' || (preference === 'system' && systemPrefersDark());
  document.documentElement.classList.toggle('dark', dark);
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', dark ? THEME_COLOR.dark : THEME_COLOR.light);
}

interface ThemeState {
  preference: ThemePreference;
  setPreference: (next: ThemePreference) => void;
}

/**
 * Une seule source pour la préférence : la page Réglages l'écrit, l'appli
 * l'applique. Deux `useState` séparés divergeaient, et le suivi du système
 * pouvait écraser un choix forcé.
 */
export const useThemeStore = create<ThemeState>((set) => ({
  preference: readThemePreference(),
  setPreference: (next) => {
    try {
      if (next === 'system') localStorage.removeItem(THEME_STORAGE_KEY);
      else localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Stockage indisponible (navigation privée) : le choix vaut pour la
      // session en cours seulement.
    }
    set({ preference: next });
  },
}));

/** À monter une fois, en haut de l'appli. */
export function useThemeSync(): void {
  const preference = useThemeStore((s) => s.preference);
  useEffect(() => {
    applyTheme(preference);
    if (preference !== 'system' || typeof window.matchMedia !== 'function') return;
    // En mode système, le thème suit l'OS en direct (passage automatique en
    // sombre le soir) sans recharger la page.
    const query = window.matchMedia(DARK_QUERY);
    const onChange = () => applyTheme('system');
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, [preference]);
}
