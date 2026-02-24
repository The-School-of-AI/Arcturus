// features/swarm/SwarmSidebar.tsx
// Left sidebar panel for the Swarm tab — mirrors the Runs panel structure.
// Shows: query input, run controls, and a list of swarm run entries (NOT task nodes).
// Task nodes render in the center SwarmGraphView; AgentPeekPanel slides in on the right.

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Network, Play, Pause, BookMarked, Zap, RefreshCw, Plus, CheckCircle2, Loader2, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { useSwarmStore } from './useSwarmStore';
import { useSwarmSSE } from './useSwarmSSE';
import { swarmApi } from './swarmApi';
import { InterventionModal } from './InterventionModal';
import { TemplateDrawer } from './TemplateDrawer';
import type { SwarmEvent, SwarmTemplate } from './types';

type RunEntry = { id: string; label: string; status: 'running' | 'done' | 'failed' };

export const SwarmSidebar: React.FC = () => {
    const activeRunId = useSwarmStore(s => s.activeRunId);
    const setActiveRunId = useSwarmStore(s => s.setActiveRunId);
    const applyEvent = useSwarmStore(s => s.applyEvent);
    const refreshStatus = useSwarmStore(s => s.refreshStatus);
    const isPaused = useSwarmStore(s => s.isPaused);
    const tasks = useSwarmStore(s => s.tasks);
    const costUsd = useSwarmStore(s => s.costUsd);
    const setInterventionOpen = useSwarmStore(s => s.setInterventionOpen);
    const setTemplateDrawerOpen = useSwarmStore(s => s.setTemplateDrawerOpen);

    const [query, setQuery] = useState('');
    const [isStarting, setIsStarting] = useState(false);
    const [runHistory, setRunHistory] = useState<RunEntry[]>([]);

    // Wire SSE events
    const handleEvent = useCallback((e: SwarmEvent) => applyEvent(e), [applyEvent]);
    useSwarmSSE(activeRunId, handleEvent);

    // Polling loop — stop when all tasks settle
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const stopPolling = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };

    useEffect(() => {
        if (!activeRunId) { stopPolling(); return; }
        refreshStatus(activeRunId);
        pollRef.current = setInterval(async () => {
            await refreshStatus(activeRunId);
            const t = useSwarmStore.getState().tasks;
            const allDone = t.length > 0 && t.every(tk => tk.status === 'completed' || tk.status === 'failed');
            const hasFailed = t.some(tk => tk.status === 'failed');
            if (allDone) {
                stopPolling();
                setRunHistory(prev => prev.map(r =>
                    r.id === activeRunId ? { ...r, status: hasFailed ? 'failed' : 'done' } : r));
            }
        }, 2000);
        return stopPolling;
    }, [activeRunId]);

    const handleStart = async () => {
        if (!query.trim()) return;
        setIsStarting(true);
        const label = query.trim();
        try {
            const { run_id } = await swarmApi.startRun(label);
            setActiveRunId(run_id);
            setRunHistory(prev => [{ id: run_id, label, status: 'running' }, ...prev]);
            setQuery('');
        } finally {
            setIsStarting(false);
        }
    };

    const handlePauseResume = async () => {
        if (!activeRunId) return;
        await swarmApi.intervene(activeRunId, { action: isPaused ? 'resume' : 'pause' });
        await refreshStatus(activeRunId);
    };

    const handleApplyTemplate = (t: SwarmTemplate) => setQuery(t.description || t.name);

    const completedCount = tasks.filter(t => t.status === 'completed').length;
    const totalCount = tasks.length;

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {/* Header — query input and controls */}
            <div className="shrink-0 px-3 pt-3 pb-3 border-b border-border space-y-2">
                <div className="flex items-center gap-1.5">
                    <Network className="w-4 h-4 text-primary shrink-0" />
                    <span className="text-sm font-semibold text-foreground flex-1">Swarm</span>
                    {activeRunId && (
                        <>
                            <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground"
                                title="Refresh" onClick={() => refreshStatus(activeRunId)}>
                                <RefreshCw className="w-3 h-3" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-yellow-400"
                                title={isPaused ? 'Resume' : 'Pause'} onClick={handlePauseResume}>
                                {isPaused ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
                            </Button>
                            <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-primary"
                                title="Intervene" onClick={() => setInterventionOpen(true)}>
                                <Zap className="w-3 h-3" />
                            </Button>
                        </>
                    )}
                    <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground"
                        title="Templates" onClick={() => setTemplateDrawerOpen(true)}>
                        <BookMarked className="w-3 h-3" />
                    </Button>
                </div>

                <div className="flex gap-1.5">
                    <Input
                        placeholder="Describe your swarm goal…"
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleStart()}
                        className="flex-1 text-xs bg-muted/50 border-border h-8"
                        disabled={isStarting}
                    />
                    <Button size="sm" onClick={handleStart}
                        disabled={isStarting || !query.trim()}
                        className="h-8 text-xs px-2.5 bg-primary hover:bg-primary/90 text-white gap-1 shrink-0">
                        <Plus className="w-3 h-3" />
                        {isStarting ? '…' : 'Run'}
                    </Button>
                </div>
            </div>

            {/* Run history list — same pattern as the Runs panel run list */}
            <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1 scrollbar-hide">
                {runHistory.length === 0 ? (
                    <p className="text-[11px] text-muted-foreground text-center pt-10 opacity-40 px-4 leading-relaxed">
                        No swarm runs yet.<br />Enter a goal above to start.
                    </p>
                ) : (
                    runHistory.map(run => {
                        const isActive = run.id === activeRunId;
                        return (
                            <button
                                key={run.id}
                                onClick={() => setActiveRunId(run.id)}
                                className={cn(
                                    'w-full text-left px-3 py-2.5 rounded-xl transition-all duration-150 border',
                                    isActive
                                        ? 'border-primary/40 bg-primary/5'
                                        : 'border-transparent hover:border-border hover:bg-muted/40',
                                )}
                            >
                                <p className="text-xs text-foreground leading-snug line-clamp-2">{run.label}</p>
                                <div className="flex items-center gap-1.5 mt-1.5">
                                    {run.status === 'running' && (
                                        <span className="flex items-center gap-1 text-[10px] text-primary animate-pulse">
                                            <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                            {isActive && totalCount > 0 ? `${completedCount} / ${totalCount}` : 'Running…'}
                                        </span>
                                    )}
                                    {run.status === 'done' && (
                                        <span className="flex items-center gap-1 text-[10px] text-green-400">
                                            <CheckCircle2 className="w-2.5 h-2.5" /> Completed
                                        </span>
                                    )}
                                    {run.status === 'failed' && (
                                        <span className="flex items-center gap-1 text-[10px] text-red-400">
                                            <XCircle className="w-2.5 h-2.5" /> Failed
                                        </span>
                                    )}
                                    {isActive && costUsd > 0 && (
                                        <span className="ml-auto text-[10px] text-muted-foreground font-mono">
                                            ${costUsd.toFixed(4)}
                                        </span>
                                    )}
                                    {isPaused && isActive && (
                                        <span className="text-[10px] text-yellow-400 ml-1">⏸</span>
                                    )}
                                </div>
                            </button>
                        );
                    })
                )}
            </div>

            <InterventionModal />
            <TemplateDrawer onApply={handleApplyTemplate} />
        </div>
    );
};
