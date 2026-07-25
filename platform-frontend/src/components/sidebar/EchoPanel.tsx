import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Mic, Square, Bot, User, ShieldCheck, Loader2, PlayCircle, Clock, CheckCircle2, XCircle, Zap, Volume2, Plus, ChevronDown, FileText, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import { useEchoStore } from '@/features/echo/useEchoStore';
import { startVoice, stopVoice } from '@/lib/voice';

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

function formatTimeAgo(ts: number): string {
    const diff = Date.now() - ts;
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'now';
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    return `${Math.floor(hrs / 24)}d`;
}

// ── Component ────────────────────────────────────────────────────────────────
export const EchoPanel: React.FC = () => {
    const events = useAppStore(s => s.events);
    const isStreaming = useAppStore(s => s.isStreaming);
    const startEventStream = useAppStore(s => s.startEventStream);
    const setSidebarTab = useAppStore(s => s.setSidebarTab);
    const runs = useAppStore(s => s.runs);
    const setCurrentRun = useAppStore(s => s.setCurrentRun);

    // Shared echo store — voice state, sessions, conversation
    const {
        voiceState, statusText, liveTranscript, nexusRunActive,
        sessions, activeSessionId,
        processEvents, createSession, switchSession, endSession, clearAllSessions, addMessage,
        setVoiceState, setStatusText, setLiveTranscript, setNexusRunActive,
    } = useEchoStore();

    const activeSession = sessions.find(s => s.id === activeSessionId);
    const conversation = activeSession?.conversation ?? [];

    const [activeView, setActiveView] = useState<'conversation' | 'runs'>('conversation');
    const [showSessions, setShowSessions] = useState(false);

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
                addMessage({
                    id: `sys-${Date.now()}`,
                    role: 'assistant',
                    text: data.privacy_mode
                        ? `Privacy Mode ON \u2014 switched to ${data.stt} + ${data.tts}. No data leaves your device.`
                        : `Privacy Mode OFF \u2014 switched to ${data.stt} + ${data.tts}.`,
                    source: 'system',
                    ts: Date.now(),
                });
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

    const changePersona = async (name: string) => {
        if (personaChanging || !personasState || name === personasState.active) return;
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
                addMessage({
                    id: `sys-${Date.now()}`,
                    role: 'assistant',
                    text: `Voice persona switched to "${name}"${desc ? ` \u2014 ${desc}` : ''}.`,
                    source: 'system',
                    ts: Date.now(),
                });
            }
        } catch (e) {
            console.error('Persona change failed', e);
        } finally {
            setPersonaChanging(false);
        }
    };

    // ── Refs ─────────────────────────────────────────────────────────────────
    const bottomRef = useRef<HTMLDivElement>(null);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Auto-scroll
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [conversation, liveTranscript]);

    // Fetch privacy + personas on mount
    useEffect(() => { fetchPrivacy(); fetchPersonas(); }, [fetchPrivacy, fetchPersonas]);

    // Start SSE
    useEffect(() => { startEventStream(); }, [startEventStream]);

    // Process SSE events through shared store
    useEffect(() => { processEvents(events); }, [events, processEvents]);

    // ── Polling fallback ─────────────────────────────────────────────────────
    useEffect(() => {
        pollRef.current = setInterval(async () => {
            try {
                const res = await fetch(WAKE_POLL_URL);
                if (!res.ok) return;
                const json = await res.json();
                if (json.wake) {
                    setVoiceState('listening');
                    setStatusText('Listening...');
                    setLiveTranscript('');
                    setNexusRunActive(false);
                }
                const s = json.state;
                if (!json.wake && s) {
                    const echoState = useEchoStore.getState();
                    if (s === 'IDLE') {
                        setVoiceState('idle');
                        setStatusText('Ready');
                        setNexusRunActive(false);
                    } else if (s === 'THINKING') {
                        setVoiceState('thinking');
                        setStatusText(echoState.nexusRunActive ? 'Processing with Nexus...' : 'Thinking...');
                    } else if (s === 'SPEAKING') {
                        setVoiceState('speaking');
                        if (!echoState.nexusRunActive) setStatusText('Speaking...');
                    } else if (s === 'DICTATING') {
                        setVoiceState('dictating');
                        setStatusText('Dictating \u2014 say "stop dictation" to finish.');
                    }
                }
            } catch { /* backend not up */ }
        }, 1000);
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [setVoiceState, setStatusText, setLiveTranscript, setNexusRunActive]);

    // ── Handlers ─────────────────────────────────────────────────────────────

    const handleMicToggle = async () => {
        if (voiceState === 'listening' || voiceState === 'dictating') {
            await stopVoice();
            setStatusText(voiceState === 'dictating' ? 'Stopping dictation...' : 'Processing...');
        } else if (voiceState === 'idle') {
            await startVoice();
            setVoiceState('listening');
            setStatusText('Listening...');
        }
    };

    const handleNewSession = () => { createSession(); setShowSessions(false); };
    const handleSwitchSession = (id: string) => { switchSession(id); setShowSessions(false); };

    const isPrivate = privacy?.privacy_mode ?? false;
    const recentSessions = sessions.slice(0, 6);

    // Runs (newest first, cap 10)
    const recentRuns = [...runs]
        .sort((a, b) => b.createdAt - a.createdAt)
        .slice(0, 10);

    // ── Render ───────────────────────────────────────────────────────────────
    return (
        <div className="flex flex-col h-full w-full bg-background text-foreground overflow-hidden">

            {/* ── Header ──────────────────────────────────────────────── */}
            <div className="px-3 py-2.5 border-b border-border/50 bg-muted/20 shrink-0 space-y-1.5">
                <div className="flex items-center justify-between">
                    <h2 className="text-base font-semibold text-primary/90 flex items-center gap-2 tracking-tight shrink-0">
                        Echo
                        <span
                            title={isStreaming ? 'Event stream connected' : 'Event stream disconnected'}
                            className={`w-2 h-2 rounded-full shrink-0 ${isStreaming ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`}
                        />
                    </h2>

                    <div className="flex items-center gap-1">
                        {/* Session selector */}
                        <div className="relative">
                            <button
                                onClick={() => setShowSessions(!showSessions)}
                                className="flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs text-muted-foreground hover:text-foreground hover:bg-muted/40 transition-colors max-w-[120px]"
                            >
                                <span className="truncate">{activeSession?.title || 'New Session'}</span>
                                <ChevronDown className="w-2.5 h-2.5 shrink-0" />
                            </button>
                            {showSessions && (
                                <>
                                    <div className="fixed inset-0 z-40" onClick={() => setShowSessions(false)} />
                                    <div className="absolute right-0 top-full mt-1 w-[240px] bg-popover border border-border rounded-lg shadow-xl z-50 py-1 animate-content-in">
                                        <button
                                            onClick={handleNewSession}
                                            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-primary hover:bg-primary/10 transition-colors"
                                        >
                                            <Plus className="w-3 h-3" />
                                            New Session
                                        </button>
                                        <button
                                            onClick={() => { clearAllSessions(); setShowSessions(false); }}
                                            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-400/80 hover:bg-red-400/10 transition-colors"
                                        >
                                            <Trash2 className="w-3 h-3" />
                                            Clear All Sessions
                                        </button>
                                        {recentSessions.length > 0 && <div className="h-px bg-border/50 my-1" />}
                                        {recentSessions.map(s => (
                                            <button
                                                key={s.id}
                                                onClick={() => handleSwitchSession(s.id)}
                                                className={cn(
                                                    'w-full flex items-center gap-2 px-3 py-1.5 text-xs transition-colors text-left',
                                                    s.id === activeSessionId
                                                        ? 'bg-primary/10 text-primary'
                                                        : 'text-muted-foreground hover:text-foreground hover:bg-muted/30'
                                                )}
                                            >
                                                <FileText className="w-3 h-3 shrink-0" />
                                                <span className="truncate flex-1">{s.title}</span>
                                                <span className="text-2xs text-muted-foreground/50 shrink-0">
                                                    {formatTimeAgo(s.createdAt)}
                                                </span>
                                            </button>
                                        ))}
                                    </div>
                                </>
                            )}
                        </div>
                        <button onClick={handleNewSession} className="shrink-0 p-1 rounded hover:bg-muted/40 text-muted-foreground hover:text-primary transition-colors" title="New session">
                            <Plus className="w-3.5 h-3.5" />
                        </button>
                    </div>
                </div>

                {/* Compact provider info + persona — single row */}
                <div className="flex items-center gap-2">
                    <button
                        onClick={togglePrivacy}
                        disabled={privacyLoading || !privacy}
                        title={isPrivate ? 'Local mode \u2014 click for cloud' : 'Cloud mode \u2014 click for local'}
                        className={cn(
                            'shrink-0 flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs font-medium transition-all border',
                            isPrivate
                                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400/80 hover:bg-emerald-500/20'
                                : 'bg-muted/30 border-border/30 text-muted-foreground hover:text-foreground',
                            (privacyLoading || !privacy) && 'opacity-50 cursor-not-allowed'
                        )}
                    >
                        {privacyLoading ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <ShieldCheck className="w-2.5 h-2.5" />}
                        {privacy?.stt_provider ?? 'stt'} · {privacy?.tts_provider ?? 'tts'}
                    </button>

                    <div className="h-3 w-px bg-border/30" />

                    {/* Persona selector — always enabled (Kokoro supports personas) */}
                    {personasState && (
                        <div className="relative flex-1 min-w-0">
                            <select
                                value={personasState.active}
                                onChange={e => changePersona(e.target.value)}
                                disabled={personaChanging}
                                title={personasState.personas[personasState.active]?.description ?? ''}
                                className={cn(
                                    'w-full appearance-none bg-muted/30 border border-border/30 rounded',
                                    'text-2xs text-foreground/80 px-2 pr-5 py-0.5',
                                    'hover:border-primary/40 focus:outline-none focus:border-primary/50',
                                    'transition-all duration-150',
                                    personaChanging ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'
                                )}
                            >
                                {Object.keys(personasState.personas).map(key => (
                                    <option key={key} value={key}>
                                        {key.charAt(0).toUpperCase() + key.slice(1)}
                                    </option>
                                ))}
                            </select>
                            <div className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground/50">
                                {personaChanging
                                    ? <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                    : <svg className="w-2.5 h-2.5" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 4l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" /></svg>
                                }
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* ── Mic button + status ──────────────────────────────── */}
            <div className="shrink-0 flex flex-col items-center gap-2 pt-4 pb-3 px-4 border-b border-border/30">
                <button
                    onClick={handleMicToggle}
                    disabled={voiceState === 'thinking' || voiceState === 'speaking'}
                    className={cn(
                        'relative w-16 h-16 rounded-full flex items-center justify-center transition-all duration-300 cursor-pointer',
                        'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-primary',
                        voiceState === 'listening'
                            ? 'bg-red-500/20 text-red-400 shadow-[0_0_40px_rgba(239,68,68,0.4)] scale-105'
                            : voiceState === 'thinking'
                                ? 'bg-amber-500/20 text-amber-400 shadow-[0_0_30px_rgba(245,158,11,0.3)]'
                                : voiceState === 'speaking'
                                    ? 'bg-violet-500/20 text-violet-400 shadow-[0_0_30px_rgba(139,92,246,0.35)]'
                                    : voiceState === 'dictating'
                                        ? 'bg-emerald-500/20 text-emerald-400 shadow-[0_0_40px_rgba(16,185,129,0.4)] scale-105'
                                        : 'bg-muted/50 text-muted-foreground hover:bg-primary/15 hover:text-primary hover:shadow-[0_0_20px_rgba(56,189,248,0.2)] hover:scale-105',
                        (voiceState === 'thinking' || voiceState === 'speaking') && 'cursor-not-allowed'
                    )}
                >
                    {voiceState === 'listening' && (
                        <>
                            <span className="absolute inset-0 rounded-full border-2 border-red-400/60 animate-ping" />
                            <span className="absolute inset-0 rounded-full border-2 border-red-400/40" />
                        </>
                    )}
                    {voiceState === 'thinking' && (
                        <span className="absolute inset-0 rounded-full border-2 border-amber-400/40 animate-pulse" />
                    )}
                    {voiceState === 'speaking' && (
                        <span className="absolute inset-0 rounded-full border-2 border-violet-400/40 animate-pulse" />
                    )}
                    {voiceState === 'dictating' && (
                        <span className="absolute inset-0 rounded-full border-2 border-emerald-400/40 animate-pulse" />
                    )}

                    {voiceState === 'listening' ? (
                        <Square className="w-6 h-6 relative z-10" />
                    ) : voiceState === 'thinking' ? (
                        <Loader2 className="w-6 h-6 relative z-10 animate-spin" />
                    ) : voiceState === 'speaking' ? (
                        <Volume2 className="w-6 h-6 relative z-10 animate-pulse" />
                    ) : voiceState === 'dictating' ? (
                        <Square className="w-6 h-6 relative z-10" />
                    ) : (
                        <Mic className="w-6 h-6 relative z-10" />
                    )}
                </button>

                {/* Status */}
                <span className={cn(
                    'text-xs font-semibold tracking-wide text-center transition-colors duration-200',
                    voiceState === 'listening' ? 'text-red-400'
                        : voiceState === 'thinking' ? 'text-amber-400'
                            : voiceState === 'speaking' ? 'text-violet-400'
                                : voiceState === 'dictating' ? 'text-emerald-400'
                                    : 'text-muted-foreground'
                )}>
                    {statusText}
                </span>

                {nexusRunActive && (
                    <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-violet-500/15 border border-violet-500/30 text-violet-400 text-2xs font-medium">
                        <span className="relative flex h-1.5 w-1.5">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75" />
                            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-violet-500" />
                        </span>
                        Nexus run in progress
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
                                    onClick={() => endSession()}
                                    className="flex items-center gap-1.5 px-2 py-1 text-2xs font-bold uppercase tracking-wider text-muted-foreground/60 hover:text-red-400 bg-muted/20 hover:bg-red-400/10 rounded-md border border-border/20 hover:border-red-400/30 transition-all duration-200"
                                >
                                    <XCircle className="w-3 h-3" />
                                    End Conversation
                                </button>
                            </div>
                        )}
                        {conversation.length === 0 && !liveTranscript && (
                            <div className="flex-1 flex flex-col items-center justify-center text-center gap-5 select-none py-6 px-4">
                                <div className="w-full max-w-[240px] space-y-3">
                                    <div className="flex items-center gap-2">
                                        <div className="h-px flex-1 bg-border/20" />
                                        <p className="text-xs uppercase font-bold tracking-wide text-muted-foreground/50">Try Saying</p>
                                        <div className="h-px flex-1 bg-border/20" />
                                    </div>
                                    <div className="space-y-2 text-left">
                                        {[
                                            "What is Quantum Computing?",
                                            "Summarize this project",
                                            "Open the Explorer"
                                        ].map((example, i) => (
                                            <div key={i} className="flex items-center gap-2.5 group cursor-pointer" onClick={handleMicToggle}>
                                                <div className="w-1 h-1 rounded-full bg-primary/40 group-hover:bg-primary transition-colors" />
                                                <p className="text-[11px] text-muted-foreground/70 group-hover:text-foreground transition-colors italic leading-tight">
                                                    "{example}"
                                                </p>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <p className="text-xs text-muted-foreground/40 leading-relaxed max-w-[200px]">
                                    Tap the mic button above, speak, then tap again to send.
                                    Or say <span className="italic text-primary/60">"Hey Arcturus"</span>.
                                </p>
                            </div>
                        )}

                        {conversation.map(entry => (
                            <div
                                key={entry.id}
                                className={cn('flex gap-2 items-start', entry.role === 'user' ? 'flex-row-reverse' : 'flex-row')}
                            >
                                {entry.source === 'system' ? (
                                    <div className="w-full text-center">
                                        <span className="inline-block text-xs text-muted-foreground italic px-2 py-1 rounded-md bg-muted/30 border border-border/20">
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
                                                    'inline-block mb-1 px-1.5 py-0.5 rounded text-2xs font-semibold uppercase tracking-wide',
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

                        {/* Live transcript bubble — at the bottom (latest) */}
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
                                                        <span className="text-xs text-muted-foreground/60">
                                                            {new Date(run.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                            {' \u00B7 '}
                                                            {new Date(run.createdAt).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                                                        </span>
                                                    </div>
                                                </div>
                                                <span className={cn(
                                                    'shrink-0 self-start px-1.5 py-0.5 rounded text-2xs uppercase font-bold tracking-wide',
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
