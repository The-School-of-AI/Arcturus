import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Mic, Bot, User, ShieldCheck, ShieldOff, Loader2, PlayCircle, Clock, CheckCircle2, XCircle, Zap, Volume2, Radio } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import { startVoice } from '@/lib/voice';

const WAKE_POLL_URL = 'http://localhost:8000/api/voice/wake';
const PRIVACY_BASE_URL = 'http://localhost:8000/api/voice/privacy';
const PERSONA_BASE_URL = 'http://localhost:8000/api/voice/persona';
const PERSONAS_URL = 'http://localhost:8000/api/voice/personas';

// ── Source badge map ─────────────────────────────────────────────────────────
const SOURCE_LABEL: Record<string, string> = {
    answer: 'Answer',
    clarification: 'Clarification',
    navigation: 'Navigation',
    dictation: 'Dictation',
    agent: 'Arcturus',
};

interface ConversationEntry {
    id: string;
    role: 'user' | 'assistant';
    text: string;
    source?: string;
    ts: number;
}

interface PrivacyState {
    privacy_mode: boolean;
    stt_provider: string;
    tts_provider: string;
}

interface PersonaConfig {
    voice_name: string;
    rate: string;
    pitch: string;
    volume: string;
    description: string;
}

interface PersonasState {
    active: string;
    personas: Record<string, PersonaConfig>;
}

// ── Component ────────────────────────────────────────────────────────────────
export const EchoPanel: React.FC = () => {
    const events = useAppStore(state => state.events);
    const isStreaming = useAppStore(state => state.isStreaming);
    const startEventStream = useAppStore(state => state.startEventStream);
    const setSidebarTab = useAppStore(state => state.setSidebarTab);
    const sidebarTab = useAppStore(state => state.sidebarTab);
    const runs = useAppStore(state => state.runs);
    const setCurrentRun = useAppStore(state => state.setCurrentRun);

    const [isListening, setIsListening] = useState(false);
    const [statusText, setStatusText] = useState('Waiting for wake word...');
    const [liveTranscript, setLiveTranscript] = useState('');
    const [nexusRunActive, setNexusRunActive] = useState(false);
    const [conversation, setConversation] = useState<ConversationEntry[]>([]);
    // Track which tab user is viewing (conversation vs runs)
    const [activeView, setActiveView] = useState<'conversation' | 'runs'>('conversation');

    // ── Privacy ──────────────────────────────────────────────────────────────
    const [privacy, setPrivacy] = useState<PrivacyState | null>(null);
    const [privacyLoading, setPrivacyLoading] = useState(false);

    const fetchPrivacy = useCallback(async () => {
        try {
            const res = await fetch(PRIVACY_BASE_URL);
            if (res.ok) setPrivacy(await res.json());
        } catch { /* backend not ready */ }
    }, []);

    const togglePrivacy = async () => {
        if (privacyLoading || !privacy) return;
        setPrivacyLoading(true);
        try {
            const res = await fetch(PRIVACY_BASE_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: !privacy.privacy_mode }),
            });
            if (res.ok) {
                const data = await res.json();
                setPrivacy({
                    privacy_mode: data.privacy_mode,
                    stt_provider: data.privacy_mode ? 'whisper' : 'deepgram',
                    tts_provider: data.privacy_mode ? 'piper' : 'azure',
                });
                setConversation(c => [...c, {
                    id: `sys-${Date.now()}`,
                    role: 'assistant',
                    text: data.privacy_mode
                        ? `🔒 Privacy Mode ON — switched to ${data.stt} + ${data.tts}. No data leaves your device.`
                        : `☁️ Privacy Mode OFF — switched to ${data.stt} + ${data.tts}.`,
                    source: 'system',
                    ts: Date.now(),
                }]);
            }
        } catch (e) {
            console.error('Privacy toggle failed', e);
        } finally {
            setPrivacyLoading(false);
        }
    };

    // ── Personas ─────────────────────────────────────────────────────────────
    const [personasState, setPersonasState] = useState<PersonasState | null>(null);
    const [personaChanging, setPersonaChanging] = useState(false);

    const fetchPersonas = useCallback(async () => {
        try {
            const res = await fetch(PERSONAS_URL);
            if (res.ok) setPersonasState(await res.json());
        } catch { /* backend not ready */ }
    }, []);

    const handleResetConversation = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/voice/session', {
                method: 'DELETE',
            });
            if (res.ok) {
                setConversation([]);
                setStatusText('Conversation ended and cleared.');
                setLiveTranscript('');
                // Brief reassurance before returning to idle
                setTimeout(() => setStatusText('Waiting for wake word...'), 2000);
            }
        } catch (e) {
            console.error('Failed to end conversation', e);
        }
    };

    const changePersona = async (name: string) => {
        if (personaChanging || !personasState) return;
        if (name === personasState.active) return;
        setPersonaChanging(true);
        try {
            const res = await fetch(PERSONA_BASE_URL, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ persona: name }),
            });
            if (res.ok) {
                setPersonasState(prev => prev ? { ...prev, active: name } : prev);
                const desc = personasState.personas[name]?.description ?? '';
                setConversation(c => [...c, {
                    id: `sys-${Date.now()}`,
                    role: 'assistant',
                    text: `🎙️ Voice persona switched to "${name}"${desc ? ` — ${desc}` : ''}.`,
                    source: 'system',
                    ts: Date.now(),
                }]);
            }
        } catch (e) {
            console.error('Persona change failed', e);
        } finally {
            setPersonaChanging(false);
        }
    };

    // ── Refs ─────────────────────────────────────────────────────────────────
    const nexusRunRef = useRef(false);
    nexusRunRef.current = nexusRunActive;
    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto-scroll disabled for newest-at-top
    useEffect(() => {
        // We want the view to stay at the top where the new content appears
        // bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [conversation]);

    // Fetch privacy + personas on mount
    useEffect(() => { fetchPrivacy(); fetchPersonas(); }, [fetchPrivacy, fetchPersonas]);

    // Start SSE stream on mount
    useEffect(() => { startEventStream(); }, [startEventStream]);

    // ── Polling fallback ─────────────────────────────────────────────────────
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
                    setLiveTranscript('');
                    setNexusRunActive(false);
                    if (sidebarTab !== 'echo') setSidebarTab('echo');
                }
                const s = json.state;
                if (!json.wake && s) {
                    const nexusActive = nexusRunRef.current;
                    if (s === 'IDLE') {
                        setIsListening(false);
                        setStatusText('Waiting for wake word...');
                        setNexusRunActive(false);
                    } else if (s === 'THINKING') {
                        setIsListening(true);
                        setStatusText(nexusActive ? 'Processing with Nexus...' : 'Thinking...');
                    } else if (s === 'SPEAKING') {
                        if (!nexusActive) { setIsListening(true); setStatusText('Speaking...'); }
                    } else if (s === 'DICTATING') {
                        setIsListening(true);
                        setStatusText('Dictating — say "stop dictation" to finish.');
                    }
                }
            } catch { /* backend not up */ }
        }, 1000);
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [sidebarTab, setSidebarTab]);

    // ── SSE event handler (Robustly processes ALL new events) ────────────────
    const lastProcessedIndex = useRef(-1);
    useEffect(() => {
        if (!events || events.length === 0) {
            lastProcessedIndex.current = -1;
            return;
        }

        // Process all events from (lastProcessedIndex + 1) to the end
        const startIndex = lastProcessedIndex.current + 1;
        for (let i = startIndex; i < events.length; i++) {
            const ev = events[i];
            
            if (ev.type === 'voice_wake') {
                const isBargeIn = ev.data?.barge_in === true;
                setIsListening(true);
                setStatusText(isBargeIn ? '⚡ Barge-in detected!' : 'Listening...');
                setLiveTranscript('');
                setNexusRunActive(false);

                // Stop agent runs on wake
                useAppStore.getState().stopPolling();
                useAppStore.getState().setCurrentRun(null);

                if (isBargeIn) {
                    // Drop previous dialogues on barge-in as requested
                    setConversation([{
                        id: `sys-barge-${Date.now()}`,
                        role: 'assistant',
                        text: '⚡ Barge-in detected',
                        source: 'system',
                        ts: Date.now(),
                    }]);
                }

                if (sidebarTab !== 'echo') setSidebarTab('echo');
            } else if (ev.type === 'voice_stt') {
                if (ev.data?.full_text) setLiveTranscript(ev.data.full_text);
            } else if (ev.type === 'voice_nexus_run') {
                const active = ev.data?.active === true;
                setNexusRunActive(active);
                if (active) {
                    setIsListening(true);
                    setStatusText('Processing with Nexus...');
                    setLiveTranscript(prev => {
                        if (prev.trim()) {
                            setConversation(c => [...c, {
                                id: `u-${Date.now()}`,
                                role: 'user',
                                text: prev.trim(),
                                ts: Date.now(),
                            }]);
                        }
                        return '';
                    });
                }
            } else if (ev.type === 'voice_tts') {
                if (ev.data?.text?.trim()) {
                    setConversation(c => [...c, {
                        id: `a-${Date.now()}-${Math.random()}`,
                        role: 'assistant',
                        text: ev.data.text.trim(),
                        source: ev.data.source,
                        ts: Date.now(),
                    }]);
                }
            } else if (ev.type === 'voice_state') {
                const s = ev.data?.state;
                if (s === 'LISTENING') {
                    setIsListening(true); 
                    // Don't overwrite explicit barge-in text if we just set it
                    setStatusText(prev => prev === '⚡ Barge-in detected!' ? prev : 'Listening...'); 
                    setNexusRunActive(false);
                } else if (s === 'THINKING') {
                    setIsListening(true);
                    setStatusText(nexusRunRef.current ? 'Processing with Nexus...' : 'Thinking...');
                } else if (s === 'SPEAKING') {
                    if (!nexusRunRef.current) { setIsListening(true); setStatusText('Speaking...'); }
                } else if (s === 'DICTATING') {
                    setIsListening(true); setStatusText('Dictating — say "stop dictation" to finish.');
                } else if (s === 'IDLE') {
                    setIsListening(false); setStatusText('Waiting for wake word...'); setNexusRunActive(false);
                    setLiveTranscript(prev => {
                        if (prev.trim()) {
                            setConversation(c => [...c, {
                                id: `u-${Date.now()}`, role: 'user', text: prev.trim(), ts: Date.now(),
                            }]);
                        }
                        return '';
                    });
                }
            }
        }
        
        lastProcessedIndex.current = events.length - 1;
    }, [events, sidebarTab, setSidebarTab]);

    const handleStart = async () => {
        await startVoice();
        setIsListening(true);
        setStatusText('Listening...');
    };

    const isPrivate = privacy?.privacy_mode ?? false;

    // ── Runs (newest first, cap 10) ──────────────────────────────────────────
    const recentRuns = [...runs]
        .sort((a, b) => b.createdAt - a.createdAt)
        .slice(0, 10);

    // ── Render ───────────────────────────────────────────────────────────────
    return (
        <div className="flex flex-col h-full w-full bg-background text-foreground overflow-hidden">

            {/* ── Header ──────────────────────────────────────────────── */}
            <div className="p-3 border-b border-border/50 bg-muted/20 flex items-center justify-between shrink-0 gap-2">
                <div className="min-w-0">
                    <h2 className="text-base font-semibold text-primary/90 flex items-center gap-2 tracking-tight">
                        Echo
                        <span
                            title={isStreaming ? 'Event stream connected' : 'Event stream disconnected'}
                            className={`w-2 h-2 rounded-full shrink-0 ${isStreaming ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`}
                        />
                    </h2>
                    <p className="text-xs text-muted-foreground mt-0.5 truncate">Talk to Arcturus hands-free</p>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                    {/* Privacy toggle */}
                    <button
                        onClick={togglePrivacy}
                        disabled={privacyLoading || !privacy}
                        title={
                            !privacy
                                ? 'Loading privacy state...'
                                : isPrivate
                                    ? 'Privacy Mode ON — click to switch to cloud (Deepgram + Azure)'
                                    : 'Privacy Mode OFF — click to go fully local (Whisper + Piper)'
                        }
                        className={cn(
                            'relative flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 border',
                            isPrivate
                                ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/25'
                                : 'bg-muted/50 border-border/40 text-muted-foreground hover:text-foreground hover:bg-muted',
                            (privacyLoading || !privacy) && 'opacity-50 cursor-not-allowed'
                        )}
                    >
                        {privacyLoading ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : isPrivate ? (
                            <ShieldCheck className="w-3.5 h-3.5" />
                        ) : (
                            <ShieldOff className="w-3.5 h-3.5" />
                        )}
                        {isPrivate ? 'Private' : 'Cloud'}
                    </button>

                    {/* Manual mic trigger */}
                    <button
                        onClick={handleStart}
                        title="Start listening manually"
                        className="p-1.5 rounded-lg bg-primary/10 hover:bg-primary/20 transition text-primary"
                    >
                        <Mic className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* ── Privacy info strip ───────────────────────────────── */}
            {isPrivate && (
                <div className="shrink-0 flex items-center gap-2 px-3 py-1.5 bg-emerald-500/8 border-b border-emerald-500/20 text-emerald-400/80 text-[10px] font-medium">
                    <ShieldCheck className="w-3 h-3 shrink-0" />
                    <span>
                        STT: {privacy?.stt_provider === 'whisper' ? 'Whisper (local)' : privacy?.stt_provider}
                        {' · '}
                        TTS: {privacy?.tts_provider === 'piper' ? 'Piper (local)' : privacy?.tts_provider}
                    </span>
                </div>
            )}

            {/* ── Persona selector ─────────────────────────────────── */}
            {personasState && (
                <div
                    className={cn(
                        'shrink-0 flex items-center gap-2 px-3 py-2 border-b border-border/30 bg-muted/10 transition-opacity duration-200',
                        isPrivate && 'opacity-40 pointer-events-none'
                    )}
                    title={isPrivate ? 'Persona selection is unavailable in Privacy Mode (Piper TTS does not support Azure personas)' : ''}
                >
                    <span className="text-[10px] text-muted-foreground font-medium shrink-0 flex items-center gap-1">
                        {isPrivate && (
                            <svg className="w-2.5 h-2.5" viewBox="0 0 12 12" fill="currentColor">
                                <path d="M9 5V4a3 3 0 1 0-6 0v1H2v7h8V5H9zm-4-1a1 1 0 1 1 2 0v1H5V4zm1 5.5a1 1 0 1 1 0-2 1 1 0 0 1 0 2z" />
                            </svg>
                        )}
                        Voice
                    </span>
                    <div className="relative flex-1">
                        <select
                            value={personasState.active}
                            onChange={e => changePersona(e.target.value)}
                            disabled={personaChanging || isPrivate}
                            title={personasState.personas[personasState.active]?.description ?? ''}
                            className={cn(
                                'w-full appearance-none bg-muted/40 border border-border/40 rounded-md',
                                'text-xs text-foreground px-2.5 pr-7 py-1',
                                'hover:border-primary/40 focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30',
                                'transition-all duration-150',
                                (personaChanging || isPrivate) ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'
                            )}
                        >
                            {Object.entries(personasState.personas).map(([key, cfg]) => (
                                <option key={key} value={key} title={cfg.description}>
                                    {key.charAt(0).toUpperCase() + key.slice(1)}
                                </option>
                            ))}
                        </select>
                        <div className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground">
                            {personaChanging
                                ? <Loader2 className="w-3 h-3 animate-spin" />
                                : <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 4l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" /></svg>
                            }
                        </div>
                    </div>
                </div>
            )}

            {/* ── Mic status ───────────────────────────────────────── */}
            <div className="shrink-0 flex flex-col items-center gap-3 pt-4 pb-3 px-4 border-b border-border/30">
                <div className={cn(
                    'w-14 h-14 rounded-full flex items-center justify-center transition-all duration-300',
                    nexusRunActive
                        ? 'bg-violet-500/20 text-violet-400 shadow-[0_0_25px_rgba(139,92,246,0.35)] animate-pulse'
                        : isListening
                            ? 'bg-primary/20 text-primary shadow-[0_0_25px_rgba(56,189,248,0.3)] animate-pulse'
                            : 'bg-muted/50 text-muted-foreground'
                )}>
                    <Mic className={cn('w-6 h-6', isListening ? 'animate-bounce' : '')} />
                </div>

                <span className={cn(
                    'text-xs font-medium tracking-wide text-center',
                    nexusRunActive ? 'text-violet-400 animate-pulse'
                        : isListening ? 'text-foreground animate-pulse'
                            : 'text-muted-foreground'
                )}>
                    {statusText}
                </span>

                {nexusRunActive && (
                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-violet-500/15 border border-violet-500/30 text-violet-400 text-[10px] font-medium">
                        <span className="relative flex h-1.5 w-1.5">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75" />
                            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-violet-500" />
                        </span>
                        Nexus run in progress
                    </div>
                )}

                {isListening && (
                    <div className="flex items-end justify-center gap-[3px] h-5">
                        {[...Array(10)].map((_, i) => (
                            <div
                                key={i}
                                className={cn('w-1 rounded-full animate-pulse', nexusRunActive ? 'bg-violet-400/80' : 'bg-primary/80')}
                                style={{ height: `${20 + (i % 3) * 30}%`, animationDelay: `${i * 0.1}s`, animationDuration: '0.8s' }}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* ── Tab switcher: Conversation / Runs ────────────────── */}
            <div className="shrink-0 flex border-b border-border/30 bg-muted/10">
                <button
                    onClick={() => setActiveView('conversation')}
                    className={cn(
                        'flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-[11px] font-semibold tracking-wide transition-all duration-200 border-b-2',
                        activeView === 'conversation'
                            ? 'border-primary text-primary bg-primary/5'
                            : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/20'
                    )}
                >
                    <Volume2 className="w-3 h-3" />
                    Conversation
                </button>
                <button
                    onClick={() => setActiveView('runs')}
                    className={cn(
                        'flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-[11px] font-semibold tracking-wide transition-all duration-200 border-b-2',
                        activeView === 'runs'
                            ? 'border-primary text-primary bg-primary/5'
                            : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/20'
                    )}
                >
                    <Zap className="w-3 h-3" />
                    Runs
                    {nexusRunActive && (
                        <span className="relative flex h-1.5 w-1.5 ml-0.5">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75" />
                            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-violet-500" />
                        </span>
                    )}
                </button>
            </div>

            {/* ── Content area ─────────────────────────────────────── */}
            <div className="flex-1 overflow-hidden min-h-0">

                {/* Conversation view */}
                {activeView === 'conversation' && (
                    <div className="h-full overflow-y-auto px-3 py-3 flex flex-col gap-3">
                        {conversation.length > 0 && (
                            <div className="shrink-0 flex justify-end mb-1">
                                <button
                                    onClick={handleResetConversation}
                                    className="flex items-center gap-1.5 px-2 py-1 text-[9px] font-bold uppercase tracking-wider text-muted-foreground/60 hover:text-red-400 bg-muted/20 hover:bg-red-400/10 rounded-md border border-border/20 hover:border-red-400/30 transition-all duration-200"
                                >
                                    <XCircle className="w-3 h-3" />
                                    End Conversation
                                </button>
                            </div>
                        )}
                        {conversation.length === 0 && !liveTranscript && (
                            <div className="flex-1 flex flex-col items-center justify-center text-center gap-6 select-none py-6 px-4">
                                {/* Mic icon and Wake Word */}
                                <div className="space-y-3">
                                    <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                                        <Mic className="w-5 h-5 text-primary/50" />
                                    </div>
                                    <div className="space-y-1">
                                        <p className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground/50">Wake Word</p>
                                        <p className="text-sm font-semibold text-primary/90 italic">"Hey Arcturus"</p>
                                    </div>
                                </div>

                                {/* Examples */}
                                <div className="w-full max-w-[240px] space-y-3">
                                    <div className="flex items-center gap-2">
                                        <div className="h-px flex-1 bg-border/20" />
                                        <p className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground/50">Try Saying</p>
                                        <div className="h-px flex-1 bg-border/20" />
                                    </div>
                                    <div className="space-y-2 text-left">
                                        {[
                                            "What is Quantum Computing?",
                                            "Start transcribing",
                                            "Open the Explorer"
                                        ].map((example, i) => (
                                            <div key={i} className="flex items-center gap-2.5 group cursor-pointer" onClick={() => startVoice()}>
                                                <div className="w-1 h-1 rounded-full bg-primary/40 group-hover:bg-primary transition-colors" />
                                                <p className="text-[11px] text-muted-foreground/70 group-hover:text-foreground transition-colors italic leading-tight">
                                                    "{example}"
                                                </p>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <p className="text-[10px] text-muted-foreground/40 leading-relaxed max-w-[200px]">
                                    Or click the <Mic className="w-3 h-3 inline-block align-middle text-primary/50 mx-0.5" /> button above to start listening manually.
                                </p>
                            </div>
                        )}

                        {/* Live transcript bubble - Moved to top for "newest first" view */}
                        {liveTranscript && (
                            <div className="flex gap-2 items-start flex-row-reverse">
                                <div className="shrink-0 w-6 h-6 rounded-full flex items-center justify-center mt-0.5 bg-primary/20 text-primary">
                                    <User className="w-3 h-3" />
                                </div>
                                <div className="max-w-[82%] rounded-2xl rounded-tr-sm px-3 py-2 text-xs leading-relaxed bg-primary/10 border border-primary/20 border-dashed text-foreground/80 italic">
                                    {liveTranscript}
                                    <span className="ml-1 inline-block w-0.5 h-3 bg-primary/60 animate-pulse rounded-full align-middle" />
                                </div>
                            </div>
                        )}

                        {[...conversation].reverse().map(entry => (
                            <div
                                key={entry.id}
                                className={cn('flex gap-2 items-start', entry.role === 'user' ? 'flex-row-reverse' : 'flex-row')}
                            >
                                {entry.source === 'system' ? (
                                    <div className="w-full text-center">
                                        <span className="inline-block text-[10px] text-muted-foreground italic px-2 py-1 rounded-md bg-muted/30 border border-border/20">
                                            {entry.text}
                                        </span>
                                    </div>
                                ) : (
                                    <>
                                        <div className={cn(
                                            'shrink-0 w-6 h-6 rounded-full flex items-center justify-center mt-0.5',
                                            entry.role === 'user' ? 'bg-primary/20 text-primary' : 'bg-violet-500/20 text-violet-400'
                                        )}>
                                            {entry.role === 'user' ? <User className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
                                        </div>
                                        <div className={cn(
                                            'max-w-[82%] rounded-2xl px-3 py-2 text-xs leading-relaxed shadow-sm',
                                            entry.role === 'user'
                                                ? 'bg-primary/15 text-foreground rounded-tr-sm border border-primary/20'
                                                : 'bg-muted/40 text-foreground rounded-tl-sm border border-border/30'
                                        )}>
                                            {entry.role === 'assistant' && entry.source && entry.source !== 'agent' && (
                                                <span className={cn(
                                                    'inline-block mb-1 px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wide',
                                                    entry.source === 'answer' ? 'bg-emerald-500/15 text-emerald-400' :
                                                        entry.source === 'clarification' ? 'bg-amber-500/15 text-amber-400' :
                                                            entry.source === 'navigation' ? 'bg-sky-500/15 text-sky-400' :
                                                                entry.source === 'dictation' ? 'bg-pink-500/15 text-pink-400' :
                                                                    'bg-muted text-muted-foreground'
                                                )}>
                                                    {SOURCE_LABEL[entry.source] ?? entry.source}
                                                </span>
                                            )}
                                            <p className="whitespace-pre-wrap break-words">{entry.text}</p>
                                        </div>
                                    </>
                                )}
                            </div>
                        ))}

                        <div ref={bottomRef} />
                    </div>
                )}

                {/* Runs view */}
                {activeView === 'runs' && (
                    <div className="h-full overflow-y-auto">
                        {recentRuns.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full gap-3 opacity-40 select-none py-8">
                                <PlayCircle className="w-10 h-10 text-muted-foreground" />
                                <p className="text-xs text-muted-foreground text-center leading-relaxed">
                                    No runs yet.<br />Ask Arcturus something by voice to kick one off.
                                </p>
                            </div>
                        ) : (
                            <div className="divide-y divide-border/30">
                                {recentRuns.map(run => {
                                    const isStale = run.status === 'running' && (Date.now() - run.createdAt > 3_600_000);
                                    const status = isStale ? 'failed' : run.status;
                                    const isLive = status === 'running';

                                    return (
                                        <button
                                            key={run.id}
                                            onClick={() => {
                                                setCurrentRun(run.id);
                                                setSidebarTab('runs');
                                            }}
                                            className={cn(
                                                'w-full text-left px-4 py-3 group transition-all duration-150',
                                                'hover:bg-muted/30 focus:outline-none focus-visible:bg-muted/30',
                                                isLive && nexusRunActive && 'bg-violet-500/5 hover:bg-violet-500/10'
                                            )}
                                        >
                                            <div className="flex items-start gap-2.5">
                                                {/* Status icon */}
                                                <div className="shrink-0 mt-0.5">
                                                    {status === 'running' ? (
                                                        <Loader2 className={cn(
                                                            'w-3.5 h-3.5 animate-spin',
                                                            nexusRunActive ? 'text-violet-400' : 'text-orange-400'
                                                        )} />
                                                    ) : status === 'completed' ? (
                                                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                                                    ) : (
                                                        <XCircle className="w-3.5 h-3.5 text-red-400" />
                                                    )}
                                                </div>

                                                {/* Run info */}
                                                <div className="flex-1 min-w-0">
                                                    <p className={cn(
                                                        'text-xs font-medium leading-snug truncate',
                                                        status === 'failed' ? 'text-red-400/80' :
                                                            isLive && nexusRunActive ? 'text-violet-300' :
                                                                'text-foreground group-hover:text-foreground/90'
                                                    )}>
                                                        {run.name}
                                                    </p>
                                                    <div className="flex items-center gap-1.5 mt-0.5">
                                                        <Clock className="w-2.5 h-2.5 text-muted-foreground/50 shrink-0" />
                                                        <span className="text-[10px] text-muted-foreground/60">
                                                            {new Date(run.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                            {' · '}
                                                            {new Date(run.createdAt).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                                                        </span>
                                                    </div>
                                                </div>

                                                {/* Status pill */}
                                                <span className={cn(
                                                    'shrink-0 self-start px-1.5 py-0.5 rounded text-[9px] uppercase font-bold tracking-wide',
                                                    status === 'completed' && 'bg-emerald-500/10 text-emerald-400/80',
                                                    status === 'failed' && 'bg-red-500/10 text-red-400/80',
                                                    status === 'running' && nexusRunActive && 'bg-violet-500/15 text-violet-400 animate-pulse',
                                                    status === 'running' && !nexusRunActive && 'bg-orange-500/10 text-orange-400',
                                                )}>
                                                    {status === 'running' && nexusRunActive ? 'live' : status}
                                                </span>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
