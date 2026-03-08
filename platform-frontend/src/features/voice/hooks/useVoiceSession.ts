import { useState, useEffect, useCallback } from 'react';
import { voiceApi, type VoiceSessionResponse } from '../api';

const SESSION_POLL_MS = 2500;

export function useVoiceSession(active: boolean) {
  const [session, setSession] = useState<VoiceSessionResponse | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await voiceApi.getSession();
      setSession(data);
    } catch {
      setSession(null);
    }
  }, []);

  useEffect(() => {
    if (!active) return;
    refresh();
    const id = setInterval(refresh, SESSION_POLL_MS);
    return () => clearInterval(id);
  }, [active, refresh]);

  return { session, refresh };
}
