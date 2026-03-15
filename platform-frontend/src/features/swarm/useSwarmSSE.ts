// features/swarm/useSwarmSSE.ts
// Custom hook that connects to /api/swarm/{runId}/events SSE stream
// and dispatches SwarmEvents to the provided callback.

import { useEffect, useRef } from 'react';
import { API_BASE } from '@/lib/api';
import type { SwarmEvent } from './types';

export function useSwarmSSE(
    runId: string | null,
    onEvent: (event: SwarmEvent) => void
) {
    const esRef = useRef<EventSource | null>(null);

    useEffect(() => {
        if (!runId) return;

        const url = `${API_BASE}/swarm/${runId}/events`;
        const es = new EventSource(url);
        esRef.current = es;

        es.onmessage = (e) => {
            try {
                const event: SwarmEvent = JSON.parse(e.data);
                onEvent(event);
            } catch {
                // ignore malformed events
            }
        };

        // Named event types from the backend
        const eventTypes = ['task_progress', 'task_done', 'swarm_done', 'intervention_ack', 'heartbeat'];
        eventTypes.forEach(type => {
            es.addEventListener(type, (e: MessageEvent) => {
                try {
                    const event: SwarmEvent = JSON.parse(e.data);
                    onEvent(event);
                } catch {
                    // ignore
                }
            });
        });

        es.onerror = () => {
            es.close();
        };

        return () => {
            es.close();
        };
    }, [runId, onEvent]);

    return () => esRef.current?.close();
}
