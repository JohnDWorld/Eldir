/**
 * Hook : enregistre le service worker généré par vite-plugin-pwa.
 * Source : https://vite-pwa-org.netlify.app/frameworks/react.html
 */

import { useEffect, useState } from 'react';
import { registerSW } from 'virtual:pwa-register';

export interface SwState {
  needsRefresh: boolean;
  offlineReady: boolean;
  updateSW: ((reload?: boolean) => Promise<void>) | null;
}

export function useRegisterSw(): SwState {
  const [state, setState] = useState<SwState>({
    needsRefresh: false,
    offlineReady: false,
    updateSW: null,
  });

  useEffect(() => {
    const updateSW = registerSW({
      onNeedRefresh() {
        setState((s) => ({ ...s, needsRefresh: true }));
      },
      onOfflineReady() {
        setState((s) => ({ ...s, offlineReady: true }));
      },
    });
    setState((s) => ({ ...s, updateSW }));
  }, []);

  return state;
}
