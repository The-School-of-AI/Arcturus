import { useState, useEffect, useCallback } from 'react';
import { voiceApi, type VoiceState } from '../api';

const POLL_MS = 400;

export function useVoiceState(active: boolean) {
  const [state, setState] = useState<VoiceState>('IDLE');
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const res = await voiceApi.getState();
    setState(res.state);
    if (res.state === 'unavailable') setError('Voice unavailable. Check backend and mic.');
    else setError(null);
  }, []);

  useEffect(() => {
    if (!active) return;
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [active, refresh]);

  return { state, error, refresh };
}
