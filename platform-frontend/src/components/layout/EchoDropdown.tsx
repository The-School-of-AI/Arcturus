import React, { useState, useEffect, useRef } from 'react';
import { Mic, Square, Bot, User, Loader2, Volume2, X, Plus, ChevronDown, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import { useEchoStore } from '@/features/echo/useEchoStore';
import { startVoice, stopVoice } from '@/lib/voice';

// ── Helpers ──────────────────────────────────────────────────────────────────

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

export const EchoDropdown: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [showSessions, setShowSessions] = useState(false);

    const events = useAppStore(s => s.events);
    const isStreaming = useAppStore(s => s.isStreaming);
    const sidebarTab = useAppStore(s => s.sidebarTab);

    const {
        voiceState, statusText, liveTranscript, nexusRunActive,
        sessions, activeSessionId, wakeCount,
        processEvents, createSession, switchSession,
    } = useEchoStore();

    const activeSession = sessions.find(s => s.id === activeSessionId);
    const conversation = activeSession?.conversation ?? [];

    const bottomRef = useRef<HTMLDivElement>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const prevWakeCount = useRef(wakeCount);

    // Process SSE events through shared store
    useEffect(() => { processEvents(events); }, [events, processEvents]);

    // Auto-scroll
    useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [conversation, liveTranscript]);

    // Auto-open on wake when not on Echo tab
    useEffect(() => {
        if (wakeCount > prevWakeCount.current && sidebarTab !== 'echo') {
            setIsOpen(true);
        }
        prevWakeCount.current = wakeCount;
    }, [wakeCount, sidebarTab]);

    // Close on outside click
    useEffect(() => {
        if (!isOpen) return;
        const handler = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setIsOpen(false);
                setShowSessions(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [isOpen]);

    // Close on Escape
    useEffect(() => {
        if (!isOpen) return;
        const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') { setIsOpen(false); setShowSessions(false); } };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [isOpen]);

    const handleMicToggle = async () => {
        if (voiceState === 'listening' || voiceState === 'dictating') {
            await stopVoice();
            useEchoStore.getState().setStatusText(voiceState === 'dictating' ? 'Stopping dictation...' : 'Processing...');
        } else if (voiceState === 'idle') {
            await startVoice();
            useEchoStore.getState().setVoiceState('listening');
            useEchoStore.getState().setStatusText('Listening...');
            setIsOpen(true);
        }
    };

    const handleNewSession = () => { createSession(); setShowSessions(false); };
    const handleSwitchSession = (id: string) => { switchSession(id); setShowSessions(false); };

    const isActive = voiceState !== 'idle';
    const recentSessions = sessions.slice(0, 6);

    return (
        <div ref={dropdownRef} className="relative">
            {/* Trigger button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={cn(
                    'relative p-1.5 rounded-md transition-all',
                    isOpen || isActive
                        ? 'bg-violet-500/15 text-violet-400'
                        : 'hover:bg-accent text-muted-foreground hover:text-foreground'
                )}
                title="Echo Voice (global)"
            >
                <Mic className="w-4 h-4" />
                {isActive && (
                    <span className={cn(
                        'absolute top-0.5 right-0.5 w-2 h-2 rounded-full',
                        voiceState === 'listening' ? 'bg-red-400 animate-pulse' :
                        voiceState === 'thinking' ? 'bg-amber-400 animate-pulse' :
                        voiceState === 'dictating' ? 'bg-emerald-400 animate-pulse' :
                        'bg-violet-400 animate-pulse'
                    )} />
                )}
            </button>

            {/* Dropdown panel */}
            {isOpen && (
                <div className="absolute right-0 top-full mt-1.5 w-[340px] max-h-[460px] bg-card border border-border rounded-xl shadow-2xl shadow-black/25 overflow-hidden flex flex-col z-[100] animate-content-in">
                    {/* Header */}
                    <div className="px-3 py-2 border-b border-border/50 bg-muted/20 flex items-center justify-between shrink-0">
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                            <span className="text-sm font-semibold text-foreground shrink-0">Echo</span>
                            <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', isStreaming ? 'bg-green-400' : 'bg-red-500')} />

                            {/* Session selector */}
                            <div className="relative ml-1">
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
                                        <div className="absolute left-0 top-full mt-1 w-[220px] bg-popover border border-border rounded-lg shadow-xl z-50 py-1 animate-content-in">
                                            <button
                                                onClick={handleNewSession}
                                                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-primary hover:bg-primary/10 transition-colors"
                                            >
                                                <Plus className="w-3 h-3" />
                                                New Session
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
                        </div>

                        <div className="flex items-center gap-1 shrink-0">
                            <button onClick={handleNewSession} className="p-1 rounded hover:bg-muted/40 text-muted-foreground hover:text-foreground transition-colors" title="New session">
                                <Plus className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => setIsOpen(false)} className="p-1 rounded hover:bg-muted/40 text-muted-foreground hover:text-foreground transition-colors">
                                <X className="w-3.5 h-3.5" />
                            </button>
                        </div>
                    </div>

                    {/* Mic + status row */}
                    <div className="shrink-0 flex items-center gap-3 px-3 py-2.5 border-b border-border/30">
                        <button
                            onClick={handleMicToggle}
                            disabled={voiceState === 'thinking' || voiceState === 'speaking'}
                            className={cn(
                                'relative w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 shrink-0',
                                voiceState === 'listening'
                                    ? 'bg-red-500/20 text-red-400 shadow-[0_0_20px_rgba(239,68,68,0.3)]'
                                    : voiceState === 'thinking'
                                        ? 'bg-amber-500/20 text-amber-400'
                                        : voiceState === 'speaking'
                                            ? 'bg-violet-500/20 text-violet-400'
                                            : voiceState === 'dictating'
                                                ? 'bg-emerald-500/20 text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.3)]'
                                                : 'bg-muted/50 text-muted-foreground hover:bg-primary/15 hover:text-primary',
                                (voiceState === 'thinking' || voiceState === 'speaking') && 'cursor-not-allowed'
                            )}
                        >
                            {voiceState === 'listening' && <span className="absolute inset-0 rounded-full border-2 border-red-400/50 animate-ping" />}
                            {voiceState === 'dictating' && <span className="absolute inset-0 rounded-full border-2 border-emerald-400/40 animate-pulse" />}
                            {voiceState === 'listening' ? <Square className="w-4 h-4 relative z-10" /> :
                             voiceState === 'thinking' ? <Loader2 className="w-4 h-4 relative z-10 animate-spin" /> :
                             voiceState === 'speaking' ? <Volume2 className="w-4 h-4 relative z-10 animate-pulse" /> :
                             voiceState === 'dictating' ? <Square className="w-4 h-4 relative z-10" /> :
                             <Mic className="w-4 h-4 relative z-10" />}
                        </button>

                        <div className="flex-1 min-w-0">
                            <span className={cn(
                                'text-xs font-semibold block',
                                voiceState === 'listening' ? 'text-red-400' :
                                voiceState === 'thinking' ? 'text-amber-400' :
                                voiceState === 'speaking' ? 'text-violet-400' :
                                voiceState === 'dictating' ? 'text-emerald-400' :
                                'text-muted-foreground'
                            )}>
                                {statusText}
                            </span>
                            <span className="text-2xs text-muted-foreground/50">Say "Hey Arcturus" or tap the mic</span>
                        </div>

                        {nexusRunActive && (
                            <span className="shrink-0 relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75" />
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500" />
                            </span>
                        )}
                    </div>

                    {/* Conversation — scrollable */}
                    <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2 min-h-0">
                        {conversation.length === 0 && !liveTranscript && (
                            <div className="flex flex-col items-center justify-center py-10 gap-2 select-none">
                                <Mic className="w-6 h-6 text-muted-foreground/20" />
                                <p className="text-xs text-muted-foreground/40 text-center">Voice conversation will appear here</p>
                            </div>
                        )}

                        {conversation.map(entry => (
                            <div key={entry.id} className={cn('flex gap-1.5 items-start', entry.role === 'user' ? 'flex-row-reverse' : 'flex-row')}>
                                {entry.source === 'system' ? (
                                    <div className="w-full text-center">
                                        <span className="text-2xs text-muted-foreground/60 italic">{entry.text}</span>
                                    </div>
                                ) : (
                                    <>
                                        <div className={cn(
                                            'shrink-0 w-5 h-5 rounded-full flex items-center justify-center mt-0.5',
                                            entry.role === 'user' ? 'bg-primary/20 text-primary' : 'bg-violet-500/20 text-violet-400'
                                        )}>
                                            {entry.role === 'user' ? <User className="w-2.5 h-2.5" /> : <Bot className="w-2.5 h-2.5" />}
                                        </div>
                                        <div className={cn(
                                            'max-w-[80%] rounded-xl px-2.5 py-1.5 text-xs leading-relaxed',
                                            entry.role === 'user'
                                                ? 'bg-primary/15 text-foreground rounded-tr-sm border border-primary/20'
                                                : 'bg-muted/40 text-foreground rounded-tl-sm border border-border/30'
                                        )}>
                                            <p className="whitespace-pre-wrap break-words">{entry.text}</p>
                                        </div>
                                    </>
                                )}
                            </div>
                        ))}

                        {liveTranscript && (
                            <div className="flex gap-1.5 items-start flex-row-reverse">
                                <div className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center mt-0.5 bg-primary/20 text-primary">
                                    <User className="w-2.5 h-2.5" />
                                </div>
                                <div className="max-w-[80%] rounded-xl rounded-tr-sm px-2.5 py-1.5 text-xs bg-primary/10 border border-primary/20 border-dashed text-foreground/80 italic">
                                    {liveTranscript}
                                    <span className="ml-1 inline-block w-0.5 h-3 bg-primary/60 animate-pulse rounded-full align-middle" />
                                </div>
                            </div>
                        )}

                        <div ref={bottomRef} />
                    </div>
                </div>
            )}
        </div>
    );
};
