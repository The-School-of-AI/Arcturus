import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { useAppStore } from '@/store';

// ── Types ────────────────────────────────────────────────────────────────────

export interface ConversationEntry {
    id: string;
    role: 'user' | 'assistant';
    text: string;
    source?: string;
    ts: number;
}

export interface EchoSession {
    id: string;
    title: string;
    conversation: ConversationEntry[];
    createdAt: number;
}

export type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'dictating';

// ── Store interface ──────────────────────────────────────────────────────────

interface EchoStore {
    // Persisted
    sessions: EchoSession[];
    activeSessionId: string | null;

    // Volatile (reset on reload)
    voiceState: VoiceState;
    statusText: string;
    liveTranscript: string;
    nexusRunActive: boolean;
    lastProcessedEventIndex: number;
    wakeCount: number;

    // Actions
    createSession: () => string;
    switchSession: (id: string) => void;
    endSession: () => Promise<void>;
    clearAllSessions: () => void;
    addMessage: (entry: ConversationEntry) => void;
    processEvents: (events: any[]) => void;
    setVoiceState: (vs: VoiceState) => void;
    setStatusText: (t: string) => void;
    setLiveTranscript: (t: string) => void;
    setNexusRunActive: (a: boolean) => void;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const makeId = () => `s-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

const deriveTitle = (conv: ConversationEntry[]): string => {
    const first = conv.find(e => e.role === 'user');
    if (!first) return 'New Session';
    const t = first.text.trim();
    return t.length > 40 ? t.slice(0, 40) + '\u2026' : t;
};

// ── Store ────────────────────────────────────────────────────────────────────

export const useEchoStore = create<EchoStore>()(
    persist(
        (set, get) => ({
            // State
            sessions: [],
            activeSessionId: null,
            voiceState: 'idle' as VoiceState,
            statusText: 'Ready',
            liveTranscript: '',
            nexusRunActive: false,
            lastProcessedEventIndex: -1,
            wakeCount: 0,

            // ── Session management ───────────────────────────────────

            createSession: () => {
                const id = makeId();
                const session: EchoSession = { id, title: 'New Session', conversation: [], createdAt: Date.now() };
                set(s => ({
                    sessions: [session, ...s.sessions].slice(0, 20),
                    activeSessionId: id,
                }));
                return id;
            },

            switchSession: (id) => set({ activeSessionId: id }),

            endSession: async () => {
                try {
                    await fetch('http://localhost:8000/api/voice/session', { method: 'DELETE' });
                } catch { /* backend may be down */ }
                get().createSession();
                set({ voiceState: 'idle', statusText: 'Ready', liveTranscript: '', nexusRunActive: false });
            },

            clearAllSessions: () => {
                const id = makeId();
                const session: EchoSession = { id, title: 'New Session', conversation: [], createdAt: Date.now() };
                set({
                    sessions: [session],
                    activeSessionId: id,
                    voiceState: 'idle',
                    statusText: 'Ready',
                    liveTranscript: '',
                    nexusRunActive: false,
                    lastProcessedEventIndex: -1,
                });
            },

            addMessage: (entry) => {
                set(s => {
                    const sessions = s.sessions.map(sess => {
                        if (sess.id !== s.activeSessionId) return sess;
                        const conv = [...sess.conversation, entry];
                        return {
                            ...sess,
                            conversation: conv,
                            title: sess.title === 'New Session' ? deriveTitle(conv) : sess.title,
                        };
                    });
                    return { sessions };
                });
            },

            // ── Volatile state setters ───────────────────────────────

            setVoiceState: (vs) => set({ voiceState: vs }),
            setStatusText: (t) => set({ statusText: t }),
            setLiveTranscript: (t) => set({ liveTranscript: t }),
            setNexusRunActive: (a) => set({ nexusRunActive: a }),

            // ── SSE event processing (idempotent) ────────────────────

            processEvents: (events) => {
                const state = get();

                if (!events || events.length === 0) {
                    if (state.lastProcessedEventIndex !== -1) set({ lastProcessedEventIndex: -1 });
                    return;
                }

                const startIdx = state.lastProcessedEventIndex + 1;
                if (startIdx >= events.length) return;

                // Ensure active session exists
                let sessions = [...state.sessions];
                let activeSessionId = state.activeSessionId;
                if (!activeSessionId || !sessions.find(s => s.id === activeSessionId)) {
                    const id = makeId();
                    sessions = [{ id, title: 'New Session', conversation: [], createdAt: Date.now() }, ...sessions].slice(0, 20);
                    activeSessionId = id;
                }

                // Local tracking through the event batch
                let voiceState = state.voiceState;
                let statusText = state.statusText;
                let liveTranscript = state.liveTranscript;
                let nexusRunActive = state.nexusRunActive;
                let wakeCount = state.wakeCount;
                const newMsgs: ConversationEntry[] = [];

                for (let i = startIdx; i < events.length; i++) {
                    const ev = events[i];

                    if (ev.type === 'voice_wake') {
                        const barge = ev.data?.barge_in === true;
                        voiceState = 'listening';
                        statusText = barge ? '\u26A1 Barge-in detected!' : 'Listening...';
                        liveTranscript = '';
                        nexusRunActive = false;
                        wakeCount++;
                        if (barge) {
                            newMsgs.push({ id: `sys-barge-${Date.now()}-${i}`, role: 'assistant', text: '\u26A1 Barge-in detected', source: 'system', ts: Date.now() });
                        }
                        // Side effect: stop any active agent runs
                        try {
                            useAppStore.getState().stopPolling();
                            useAppStore.getState().setCurrentRun(null);
                        } catch { /* ok */ }

                    } else if (ev.type === 'voice_stt') {
                        if (ev.data?.full_text) liveTranscript = ev.data.full_text;

                    } else if (ev.type === 'voice_nexus_run') {
                        const active = ev.data?.active === true;
                        nexusRunActive = active;
                        if (active) {
                            voiceState = 'thinking';
                            statusText = 'Processing...';
                            const t = liveTranscript.trim();
                            liveTranscript = '';
                            if (t) newMsgs.push({ id: `u-${Date.now()}-${i}`, role: 'user', text: t, ts: Date.now() });
                        }

                    } else if (ev.type === 'voice_tts') {
                        if (ev.data?.text?.trim()) {
                            newMsgs.push({ id: `a-${Date.now()}-${i}`, role: 'assistant', text: ev.data.text.trim(), source: ev.data.source, ts: Date.now() });
                        }

                    } else if (ev.type === 'voice_state') {
                        const s = ev.data?.state;
                        if (s === 'LISTENING') {
                            voiceState = 'listening';
                            if (statusText !== '\u26A1 Barge-in detected!') statusText = 'Listening...';
                            nexusRunActive = false;
                        } else if (s === 'THINKING') {
                            voiceState = 'thinking';
                            statusText = nexusRunActive ? 'Processing with Nexus...' : 'Thinking...';
                            const t = liveTranscript.trim();
                            liveTranscript = '';
                            if (t) newMsgs.push({ id: `u-${Date.now()}-${i}`, role: 'user', text: t, ts: Date.now() });
                        } else if (s === 'SPEAKING') {
                            voiceState = 'speaking';
                            if (!nexusRunActive) statusText = 'Speaking...';
                        } else if (s === 'DICTATING') {
                            voiceState = 'dictating';
                            statusText = 'Dictating \u2014 say "stop dictation" to finish.';
                        } else if (s === 'IDLE') {
                            voiceState = 'idle';
                            statusText = 'Ready';
                            nexusRunActive = false;
                            const t = liveTranscript.trim();
                            liveTranscript = '';
                            if (t) newMsgs.push({ id: `u-${Date.now()}-${i}`, role: 'user', text: t, ts: Date.now() });
                        }
                    }
                }

                // Apply messages to active session
                if (newMsgs.length > 0) {
                    sessions = sessions.map(s => {
                        if (s.id !== activeSessionId) return s;
                        const conv = [...s.conversation, ...newMsgs];
                        return { ...s, conversation: conv, title: s.title === 'New Session' ? deriveTitle(conv) : s.title };
                    });
                }

                set({
                    sessions, activeSessionId,
                    voiceState, statusText, liveTranscript, nexusRunActive,
                    lastProcessedEventIndex: events.length - 1,
                    wakeCount,
                });
            },
        }),
        {
            name: 'arcturus-echo-sessions',
            partialize: (state) => ({
                sessions: state.sessions,
                activeSessionId: state.activeSessionId,
            }),
        }
    )
);
