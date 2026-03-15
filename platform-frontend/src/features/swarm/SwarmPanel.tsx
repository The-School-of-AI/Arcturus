// features/swarm/SwarmPanel.tsx
// Main Swarm view: toolbar + live DAG + AgentPeekPanel side panel.
// Wired into Sidebar as sidebarTab === 'swarm'.

import React, { useCallback, useState } from 'react';
import { Network, Play, Pause, BookMarked, Zap, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { SwarmGraphView } from './SwarmGraphView';
import { AgentPeekPanel } from './AgentPeekPanel';
import { InterventionModal } from './InterventionModal';
import { TemplateDrawer } from './TemplateDrawer';
import { useSwarmStore } from './useSwarmStore';
import { useSwarmSSE } from './useSwarmSSE';
import { swarmApi } from './swarmApi';
import type { SwarmTemplate, SwarmEvent } from './types';

export const SwarmPanel: React.FC = () => {
    const activeRunId = useSwarmStore(s => s.activeRunId);
    const setActiveRunId = useSwarmStore(s => s.setActiveRunId);
    const applyEvent = useSwarmStore(s => s.applyEvent);
    const refreshStatus = useSwarmStore(s => s.refreshStatus);
    const isPaused = useSwarmStore(s => s.isPaused);
    const setInterventionOpen = useSwarmStore(s => s.setInterventionOpen);
    const setTemplateDrawerOpen = useSwarmStore(s => s.setTemplateDrawerOpen);
    const tokensUsed = useSwarmStore(s => s.tokensUsed);
    const costUsd = useSwarmStore(s => s.costUsd);
    const tasks = useSwarmStore(s => s.tasks);

    const [query, setQuery] = useState('');
    const [isStarting, setIsStarting] = useState(false);

    // Wire SSE events into the store
    const handleEvent = useCallback((event: SwarmEvent) => {
        applyEvent(event);
    }, [applyEvent]);

    useSwarmSSE(activeRunId, handleEvent);

    const pollRef = React.useRef<ReturnType<typeof setInterval> | null>(null);

    const stopPolling = () => {
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    };

    // Poll status every 2s while run is active
    React.useEffect(() => {
        if (!activeRunId) { stopPolling(); return; }

        // Immediate fetch
        refreshStatus(activeRunId);

        pollRef.current = setInterval(async () => {
            await refreshStatus(activeRunId);
            // Stop when everything is settled
            const { tasks: t } = useSwarmStore.getState();
            const allDone = t.length > 0 && t.every(task => task.status === 'completed' || task.status === 'failed');
            if (allDone) stopPolling();
        }, 2000);

        return stopPolling;
    }, [activeRunId]);

    const handleStart = async () => {
        if (!query.trim()) return;
        setIsStarting(true);
        try {
            const { run_id } = await swarmApi.startRun(query.trim());
            setActiveRunId(run_id);   // triggers the polling useEffect above
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

    const handleApplyTemplate = (template: SwarmTemplate) => {
        // Pre-fill query with template description for quick start
        setQuery(template.description || template.name);
    };

    const completedCount = tasks.filter(t => t.status === 'completed').length;
    const failedCount = tasks.filter(t => t.status === 'failed').length;
    const inProgressCount = tasks.filter(t => t.status === 'in_progress').length;

    return (
        <div className="flex flex-col h-full overflow-hidden bg-transparent">
            {/* Toolbar */}
            <div className="shrink-0 p-3 border-b border-border bg-card/30 backdrop-blur-md space-y-2">
                {/* Header row */}
                <div className="flex items-center gap-2">
                    <Network className="w-4 h-4 text-primary shrink-0" />
                    <span className="text-sm font-semibold text-foreground">Swarm Orchestrator</span>
                    <div className="flex-1" />
                    {activeRunId && (
                        <>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                                title="Refresh status"
                                onClick={() => activeRunId && refreshStatus(activeRunId)}
                            >
                                <RefreshCw className="w-3.5 h-3.5" />
                            </Button>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-muted-foreground hover:text-yellow-400"
                                title={isPaused ? 'Resume swarm' : 'Pause swarm'}
                                onClick={handlePauseResume}
                            >
                                {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
                            </Button>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-muted-foreground hover:text-primary"
                                title="Intervene"
                                onClick={() => setInterventionOpen(true)}
                            >
                                <Zap className="w-3.5 h-3.5" />
                            </Button>
                        </>
                    )}
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-foreground"
                        title="Templates"
                        onClick={() => setTemplateDrawerOpen(true)}
                    >
                        <BookMarked className="w-3.5 h-3.5" />
                    </Button>
                </div>

                {/* Query input */}
                <div className="flex gap-2">
                    <Input
                        placeholder="Describe your goal for the swarm…"
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleStart()}
                        className="flex-1 text-xs bg-muted/50 border-border h-8"
                        disabled={isStarting}
                    />
                    <Button
                        size="sm"
                        onClick={handleStart}
                        disabled={isStarting || !query.trim()}
                        className="h-8 text-xs px-3 bg-primary hover:bg-primary/90 text-white gap-1 shrink-0"
                    >
                        <Play className="w-3 h-3" />
                        {isStarting ? 'Starting…' : 'Run'}
                    </Button>
                </div>

                {/* Stats bar */}
                {tasks.length > 0 && (
                    <div className="flex items-center gap-3 text-[10px] text-muted-foreground font-mono">
                        <span className="text-green-400">{completedCount} done</span>
                        {inProgressCount > 0 && <span className="text-primary animate-pulse">{inProgressCount} running</span>}
                        {failedCount > 0 && <span className="text-red-400">{failedCount} failed</span>}
                        <span className="ml-auto">{tokensUsed.toLocaleString()} tokens · ${costUsd.toFixed(5)}</span>
                        {isPaused && <span className="text-yellow-400 font-bold">⏸ PAUSED</span>}
                    </div>
                )}
            </div>

            {/* Main content: graph + peek panel */}
            <div className="flex-1 flex overflow-hidden relative">
                <div className="flex-1 min-w-0">
                    <SwarmGraphView />
                </div>
                <AgentPeekPanel />
            </div>

            {/* Modals & drawers */}
            <InterventionModal />
            <TemplateDrawer onApply={handleApplyTemplate} />
        </div>
    );
};
