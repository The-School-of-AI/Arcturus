import React, { useEffect, useState, useCallback } from 'react';
import { Mic, MicOff, Loader2, User, Bot } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { voiceApi, type VoiceState, type VoicePersonasResponse } from '../api';
import { useVoiceState } from '../hooks/useVoiceState';
import { useVoiceSession } from '../hooks/useVoiceSession';
import { WaveformBars } from './WaveformBars';

const STATE_LABELS: Record<VoiceState, string> = {
  IDLE: "Idle — Say 'Hey Arcturus' or tap to start",
  LISTENING: 'Listening…',
  THINKING: 'Thinking…',
  SPEAKING: 'Speaking',
  unavailable: 'Voice unavailable',
};

export const VoicePanel: React.FC = () => {
  const [panelActive, setPanelActive] = useState(true);
  const { state, error, refresh } = useVoiceState(panelActive);
  const { session, refresh: refreshSession } = useVoiceSession(panelActive);
  const [personas, setPersonas] = useState<VoicePersonasResponse | null>(null);
  const [personaLoading, setPersonaLoading] = useState(false);
  const [startPending, setStartPending] = useState(false);
  const [clearPending, setClearPending] = useState(false);

  const loadPersonas = useCallback(async () => {
    try {
      const data = await voiceApi.getPersonas();
      setPersonas(data);
    } catch {
      setPersonas(null);
    }
  }, []);

  useEffect(() => {
    loadPersonas();
  }, [loadPersonas]);

  const handleStart = async () => {
    if (state === 'unavailable') return;
    setStartPending(true);
    try {
      await voiceApi.startListening();
      refresh();
    } catch (e) {
      console.error('Voice start failed', e);
    } finally {
      setStartPending(false);
    }
  };

  const handleClearSession = async () => {
    setClearPending(true);
    try {
      await voiceApi.clearSession();
      refreshSession();
    } finally {
      setClearPending(false);
    }
  };

  const handlePersonaChange = async (persona: string) => {
    setPersonaLoading(true);
    try {
      await voiceApi.setPersona(persona);
      await loadPersonas();
    } finally {
      setPersonaLoading(false);
    }
  };

  const isActive = state === 'LISTENING' || state === 'SPEAKING';
  const showWaveform = (state === 'LISTENING' || state === 'SPEAKING') && state !== 'unavailable';

  return (
    <div className="flex flex-col h-full bg-background/95 text-foreground overflow-hidden">
      {/* Header */}
      <div className="shrink-0 px-4 py-3 border-b border-border/50">
        <h2 className="text-sm font-semibold text-cyan-400 tracking-tight">Voice</h2>
        <p className="text-xs text-muted-foreground mt-0.5">Talk to Arcturus hands-free</p>
      </div>

      {/* Control bar */}
      <div className="shrink-0 p-4 space-y-3">
        {error && (
          <p className="text-xs text-amber-500 bg-amber-500/10 rounded-md px-2 py-1.5" role="alert">
            {error}
          </p>
        )}
        <div className="flex flex-col items-center gap-2">
          <Button
            onClick={handleStart}
            disabled={state === 'unavailable' || startPending}
            aria-label="Start listening"
            className={cn(
              'h-14 w-14 rounded-full transition-all',
              isActive
                ? 'bg-cyan-500/20 text-cyan-400 ring-2 ring-cyan-400/50 animate-pulse'
                : 'bg-muted hover:bg-cyan-500/20 hover:text-cyan-400'
            )}
          >
            {startPending ? (
              <Loader2 className="h-6 w-6 animate-spin" />
            ) : (
              <Mic className={cn('h-6 w-6', isActive && 'text-cyan-400')} />
            )}
          </Button>
          <span className="text-xs font-medium text-muted-foreground">
            {STATE_LABELS[state]}
          </span>
          {showWaveform && <WaveformBars active className="mt-1" />}
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleClearSession}
            disabled={clearPending || state === 'unavailable'}
            aria-label="End session"
            className="flex-1 text-xs"
          >
            {clearPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <MicOff className="h-3 w-3" />}
            End session
          </Button>
        </div>

        {/* Persona */}
        {personas && Object.keys(personas.personas).length > 0 && (
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Voice persona</label>
            <select
              value={personas.active ?? ''}
              onChange={(e) => handlePersonaChange(e.target.value)}
              disabled={personaLoading}
              aria-label="Select voice persona"
              className="w-full h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
            >
              {Object.entries(personas.personas).map(([name]) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Transcript */}
      <div className="flex-1 min-h-0 flex flex-col border-t border-border/50">
        <div className="px-4 py-2 border-b border-border/30 flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground">
            Session · {session?.turn_count ?? 0} turn(s)
          </span>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {!session?.conversation_history?.length && !session?.turns?.length ? (
            <p className="text-xs text-muted-foreground italic">
              No turns yet. Start listening and speak.
            </p>
          ) : (
            <>
              {session?.turns?.length
                ? session.turns.map((turn, i) => (
                    <div key={i} className="space-y-1">
                      <div className="flex items-start gap-2">
                        <User className="h-3.5 w-3.5 text-cyan-400 mt-0.5 shrink-0" aria-hidden />
                        <p className="text-xs text-foreground bg-cyan-500/10 rounded-md px-2 py-1.5 w-full">
                          {turn.user_transcript ?? '—'}
                        </p>
                      </div>
                      <div className="flex items-start gap-2">
                        <Bot className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" aria-hidden />
                        <p className="text-xs text-muted-foreground bg-muted/50 rounded-md px-2 py-1.5 w-full">
                          {turn.tts_text ?? '—'}
                        </p>
                      </div>
                    </div>
                  ))
                : session?.conversation_history?.map((msg, i) => (
                    <div
                      key={i}
                      className={cn(
                        'flex items-start gap-2',
                        msg.role === 'user' ? '' : 'pl-4'
                      )}
                    >
                      {msg.role === 'user' ? (
                        <User className="h-3.5 w-3.5 text-cyan-400 mt-0.5 shrink-0" aria-hidden />
                      ) : (
                        <Bot className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" aria-hidden />
                      )}
                      <p
                        className={cn(
                          'text-xs rounded-md px-2 py-1.5 w-full',
                          msg.role === 'user'
                            ? 'text-foreground bg-cyan-500/10'
                            : 'text-muted-foreground bg-muted/50'
                        )}
                      >
                        {msg.content}
                      </p>
                    </div>
                  ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
