import { useEffect, useState, useCallback, useRef } from "react"
import { useAppStore } from "@/store"
import { startVoice, getVoiceSession } from "../lib/voice"

export default function useVoice() {
    const events = useAppStore(state => state.events)
    const isStreaming = useAppStore(state => state.isStreaming)
    const startEventStream = useAppStore(state => state.startEventStream)
    const setSidebarTab = useAppStore(state => state.setSidebarTab)
    const sidebarTab = useAppStore(state => state.sidebarTab)

    const [state, setState] = useState<"idle" | "listening" | "dictating">("idle")
    const [transcript, setTranscript] = useState("")
    const [lastResponse, setLastResponse] = useState("")
    const [turns, setTurns] = useState(0)

    // Ensure SSE is open
    useEffect(() => {
        startEventStream()
    }, [startEventStream])

    // Sync turns from backend session
    useEffect(() => {
        getVoiceSession()
            .then((session: any) => {
                if (session?.turn_count !== undefined) {
                    setTurns(session.turn_count)
                }
            })
            .catch(() => {})
    }, [])

    // ── SSE handler (Robustly processes ALL new events) ──────────────────────
    const lastProcessedIndex = useRef(-1);
    useEffect(() => {
        if (!events || events.length === 0) {
            lastProcessedIndex.current = -1;
            return;
        }

        const startIndex = lastProcessedIndex.current + 1;
        for (let i = startIndex; i < events.length; i++) {
            const latestEvent = events[i];

            if (latestEvent.type === 'voice_wake') {
                setState("listening")
                setTranscript("")
                // Stop agent runs on wake (barge-in)
                useAppStore.getState().stopPolling();
                useAppStore.getState().setCurrentRun(null);
                
                if (sidebarTab !== 'echo') {
                    setSidebarTab('echo')
                }
            } else if (latestEvent.type === 'voice_stt') {
                const data = latestEvent.data;
                if (data && data.full_text) {
                    setTranscript(data.full_text)
                }
            } else if (latestEvent.type === 'voice_tts') {
                const data = latestEvent.data;
                if (data && data.text) {
                    setLastResponse(data.text);
                    setTurns(prev => prev + 1);
                }
            } else if (latestEvent.type === 'voice_state') {
                const serverState = latestEvent.data?.state;
                if (serverState === 'LISTENING' || serverState === 'THINKING' || serverState === 'SPEAKING') {
                    setState("listening")
                } else if (serverState === 'DICTATING') {
                    setState("dictating")
                } else if (serverState === 'IDLE') {
                    setState("idle")
                }
            } else if (latestEvent.type === 'voice_note_saved') {
                useAppStore.getState().fetchNotesFiles();
            } else if (latestEvent.type === 'navigation') {
                const targetTab = latestEvent.data?.tab;
                if (targetTab && targetTab !== sidebarTab) {
                    setSidebarTab(targetTab);
                }
            } else if (latestEvent.type === 'voice_nexus_run') {
                const runId = latestEvent.data?.run_id;
                const active = latestEvent.data?.active;
                
                // Refresh runs list after a delay to ensure the run status is updated
                setTimeout(() => {
                    useAppStore.getState().fetchRuns();
                }, 2000);
                
                if (active && runId) {
                    // Set current run so the graph and inspector can show it
                    useAppStore.getState().setCurrentRun(runId);
                    
                    // Start polling for graph updates
                    setTimeout(() => {
                        useAppStore.getState().startPolling(runId);
                    }, 1000);
                }
            }
        }
        lastProcessedIndex.current = events.length - 1;
    }, [events, sidebarTab, setSidebarTab])

    const start = useCallback(async () => {
        await startVoice()
        setState("listening")
    }, [])

    return {
        state,
        transcript,
        lastResponse,
        turns,
        isStreaming,
        start,
    }
}