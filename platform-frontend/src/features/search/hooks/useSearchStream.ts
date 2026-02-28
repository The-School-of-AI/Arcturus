/**
 * Hook for subscribing to deep research SSE events.
 * Uses fetch + ReadableStream (not EventSource) because
 * we need to POST with a JSON body.
 */
import { useCallback, useRef, useState } from 'react';
import { API_BASE } from '@/lib/api';
import type { DeepSearchEvent } from '../types/search-types';

const SEARCH_DEEP_URL = `${API_BASE}/search/deep`;

interface UseSearchStreamReturn {
  /** Start a deep research stream */
  startStream: (query: string, focusMode?: string, maxIterations?: number) => void;
  /** Stop the current stream */
  stopStream: () => void;
  /** All events received so far */
  events: DeepSearchEvent[];
  /** The latest event */
  latestEvent: DeepSearchEvent | null;
  /** Whether the stream is active */
  isStreaming: boolean;
  /** Error message if the stream failed */
  error: string | null;
}

export function useSearchStream(): UseSearchStreamReturn {
  const [events, setEvents] = useState<DeepSearchEvent[]>([]);
  const [latestEvent, setLatestEvent] = useState<DeepSearchEvent | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const stopStream = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  }, []);

  const startStream = useCallback(
    (query: string, focusMode = 'web', maxIterations = 3) => {
      // Abort any existing stream
      abortRef.current?.abort();

      const controller = new AbortController();
      abortRef.current = controller;

      setEvents([]);
      setLatestEvent(null);
      setError(null);
      setIsStreaming(true);

      (async () => {
        try {
          const response = await fetch(SEARCH_DEEP_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              query,
              focus_mode: focusMode,
              max_iterations: maxIterations,
            }),
            signal: controller.signal,
          });

          if (!response.ok || !response.body) {
            throw new Error(`Stream failed: ${response.status}`);
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Parse SSE lines
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer

            for (const line of lines) {
              if (!line.startsWith('data: ')) continue;
              try {
                const event: DeepSearchEvent = JSON.parse(line.slice(6));
                setEvents((prev) => [...prev, event]);
                setLatestEvent(event);

                if (event.type === 'done' || event.type === 'error') {
                  setIsStreaming(false);
                  if (event.type === 'error') {
                    setError(event.error || 'Unknown error');
                  }
                }
              } catch {
                // Skip malformed lines
              }
            }
          }
        } catch (err: any) {
          if (err.name !== 'AbortError') {
            setError(err.message || 'Stream failed');
          }
        } finally {
          setIsStreaming(false);
        }
      })();
    },
    [],
  );

  return { startStream, stopStream, events, latestEvent, isStreaming, error };
}
