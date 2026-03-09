import { useEffect, useState } from "react"
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
    const [turns, setTurns] = useState(0)

    // Belt-and-suspenders: ensure SSE is open whenever this hook is mounted.
    // AppLayout is the primary owner, but this guarantees reconnection even
    // if AppLayout's effect hasn't fired yet or the stream dropped.
    useEffect(() => {
        startEventStream()
        // Intentionally no cleanup — AppLayout owns teardown
    }, [startEventStream])

    // Hydrate turn count from the backend session on mount
    useEffect(() => {
        getVoiceSession()
            .then((session: any) => {
                if (session?.turn_count !== undefined) {
                    setTurns(session.turn_count)
                }
            })
            .catch(() => { /* backend may not be running yet */ })
    }, [])

    useEffect(() => {
        if (!events || events.length === 0) return;
        
        const latestEvent = events[events.length - 1];
        
        if (latestEvent.type === 'voice_wake') {
            setState("listening")
            setTranscript("")
            
            // Auto open the panel
            if (sidebarTab !== 'echo') {
                setSidebarTab('echo')
            }
        } else if (latestEvent.type === 'voice_stt') {
            const data = latestEvent.data;
            if (data && data.full_text) {
                setTranscript(data.full_text)
                // Increment turns each time a complete utterance is transcribed
                setTurns(prev => prev + 1)
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
        }
    }, [events, sidebarTab, setSidebarTab])

    const start = async () => {
        await startVoice()
        setState("listening")
    }

    return { state, transcript, turns, start, isStreaming }
}