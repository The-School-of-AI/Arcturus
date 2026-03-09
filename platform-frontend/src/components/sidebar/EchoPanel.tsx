import React, { useState, useEffect, useRef } from 'react';
import { Mic } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import { startVoice } from '@/lib/voice';

const WAKE_POLL_URL = 'http://localhost:8000/api/voice/wake';


export const EchoPanel: React.FC = () => {
    const events = useAppStore(state => state.events);
    const isStreaming = useAppStore(state => state.isStreaming);
    const startEventStream = useAppStore(state => state.startEventStream);
    const setSidebarTab = useAppStore(state => state.setSidebarTab);
    const sidebarTab = useAppStore(state => state.sidebarTab);
    
    const [isListening, setIsListening] = useState(false);
    const [statusText, setStatusText] = useState("Waiting for wake word...");
    const [transcript, setTranscript] = useState("");

    // Belt-and-suspenders: ensure SSE is always open when this panel is mounted
    useEffect(() => {
        startEventStream();
        // No cleanup — AppLayout owns teardown
    }, [startEventStream]);

    // ── Polling fallback: GET /api/voice/wake every 1s ────────────────────
    // Completely bypasses the SSE / asyncio loop issues.
    // The endpoint is a plain synchronous flag read — zero async risk.
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    useEffect(() => {
        pollRef.current = setInterval(async () => {
            try {
                const res = await fetch(WAKE_POLL_URL);
                if (!res.ok) return;
                const json = await res.json();

                if (json.wake) {
                    setIsListening(true);
                    setStatusText('Listening...');
                    setTranscript('');
                    if (sidebarTab !== 'echo') setSidebarTab('echo');
                }

                // Sync state text from backend state
                const s = json.state;
                if (!json.wake && s) {
                    if (s === 'IDLE') { setIsListening(false); setStatusText('Waiting for wake word...'); }
                    else if (s === 'THINKING') { setIsListening(true); setStatusText('Thinking...'); }
                    else if (s === 'SPEAKING') { setIsListening(true); setStatusText('Speaking...'); }
                    else if (s === 'DICTATING') { setIsListening(true); setStatusText('Dictating — say "stop dictation" to finish.'); }
                }
            } catch { /* backend not up yet */ }
        }, 1000);
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [sidebarTab, setSidebarTab]);

    useEffect(() => {
        if (!events || events.length === 0) return;
        
        const latestEvent = events[events.length - 1];
        
        if (latestEvent.type === 'voice_wake') {
            setIsListening(true);
            setStatusText("Listening...");
            setTranscript("");
            if (sidebarTab !== 'echo') setSidebarTab('echo');
        } else if (latestEvent.type === 'voice_stt') {
            const data = latestEvent.data;
            if (data && data.full_text) setTranscript(data.full_text);
        } else if (latestEvent.type === 'voice_state') {
            const s = latestEvent.data?.state;
            if (s === 'LISTENING') { setIsListening(true); setStatusText("Listening..."); }
            else if (s === 'THINKING') { setIsListening(true); setStatusText("Thinking..."); }
            else if (s === 'SPEAKING') { setIsListening(true); setStatusText("Speaking..."); }
            else if (s === 'DICTATING') { setIsListening(true); setStatusText('Dictating — say "stop dictation" to finish.'); }
            else if (s === 'IDLE') { setIsListening(false); setStatusText("Waiting for wake word..."); }
        }
    }, [events, sidebarTab, setSidebarTab]);

    const handleStart = async () => {
        await startVoice();
        setIsListening(true);
        setStatusText("Listening...");
    };

    return (
        <div className="flex flex-col h-full bg-background border-r border-border/50 text-foreground overflow-hidden w-80 shrink-0">
            {/* Header */}
            <div className="p-4 border-b border-border/50 bg-muted/20 flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-primary/90 flex items-center gap-2 tracking-tight">
                        Echo
                        {/* SSE live indicator */}
                        <span
                            title={isStreaming ? "Event stream connected" : "Event stream disconnected — events won't arrive"}
                            className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`}
                        />
                    </h2>
                    <p className="text-sm text-muted-foreground mt-1">Talk to Arcturus hands-free</p>
                </div>
                <button
                    onClick={handleStart}
                    title="Start listening manually"
                    className="p-2 rounded-full bg-primary/10 hover:bg-primary/20 transition text-primary"
                >
                    <Mic className="w-5 h-5" />
                </button>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 overflow-y-auto p-4 flex flex-col items-center gap-6">
                
                {/* Mic Status Circle */}
                <div className="flex flex-col items-center mt-6 gap-4">
                    <div className={cn(
                        "w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300",
                        isListening
                            ? "bg-primary/20 text-primary shadow-[0_0_30px_rgba(56,189,248,0.3)] animate-pulse"
                            : "bg-muted/50 text-muted-foreground"
                    )}>
                        <Mic className={cn("w-8 h-8", isListening ? "animate-bounce" : "")} />
                    </div>

                    <div className="h-6 flex items-center justify-center">
                        <span className={cn("text-sm font-medium tracking-wide", isListening ? "text-foreground animate-pulse" : "text-muted-foreground")}>
                            {statusText}
                        </span>
                    </div>

                    {/* Audio Bars */}
                    {isListening && (
                        <div className="flex items-end justify-center gap-[3px] h-8 mt-2">
                            {[...Array(10)].map((_, i) => (
                                <div
                                    key={i}
                                    className="w-1.5 bg-primary/80 rounded-full animate-pulse"
                                    style={{
                                        height: `${20 + (i % 3) * 30}%`,
                                        animationDelay: `${i * 0.1}s`,
                                        animationDuration: '0.8s'
                                    }}
                                />
                            ))}
                        </div>
                    )}
                </div>

                {/* Live Transcript */}
                <div className="w-full mt-2 space-y-4">
                    <div className="pb-2 border-b border-border/30">
                        <h3 className="text-sm font-medium text-muted-foreground">Live Transcript</h3>
                    </div>
                    <div className="text-sm text-foreground italic opacity-90 min-h-[60px] p-3 rounded-md bg-muted/30 border border-border/20">
                        {transcript || <span className="opacity-50 text-muted-foreground">No turns yet. Say "Hey Arcturus" to start.</span>}
                    </div>
                </div>
            </div>
        </div>
    );
};
