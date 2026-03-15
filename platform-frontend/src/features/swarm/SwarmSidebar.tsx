import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { Network, Play, Pause, BookMarked, Zap, RefreshCw, Plus, CheckCircle2, Loader2, XCircle, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { useSwarmStore, type RunEntry } from './useSwarmStore';
import { useSwarmSSE } from './useSwarmSSE';
import { swarmApi } from './swarmApi';
import { InterventionModal } from './InterventionModal';
import { TemplateDrawer } from './TemplateDrawer';
import type { SwarmEvent, SwarmTemplate } from './types';
import axios from 'axios';
import { API_BASE } from '@/lib/api';

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
    const runHistory = useSwarmStore(s => s.runHistory);
    const setRunHistory = useSwarmStore(s => s.setRunHistory);

    const [query, setQuery] = useState('');
    const [searchQuery, setSearchQuery] = useState('');
    const [isStarting, setIsStarting] = useState(false);
    const [isOptimizing, setIsOptimizing] = useState(false);
    const [isNewRunOpen, setIsNewRunOpen] = useState(false);

    // Wire SSE events
    const handleEvent = useCallback((e: SwarmEvent) => applyEvent(e), [applyEvent]);
    useSwarmSSE(activeRunId, handleEvent);

    // Filter runs
    const filteredRuns = useMemo(() => {
        if (!searchQuery.trim()) return runHistory;
        const q = searchQuery.toLowerCase();
        return runHistory.filter(r => r.label.toLowerCase().includes(q));
    }, [runHistory, searchQuery]);

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
            setIsNewRunOpen(false);
        } finally {
            setIsStarting(false);
        }
    };

    const handlePauseResume = async () => {
        if (!activeRunId) return;
        await swarmApi.intervene(activeRunId, { action: isPaused ? 'resume' : 'pause' });
        await refreshStatus(activeRunId);
    };

    const handleApplyTemplate = (t: SwarmTemplate) => {
        setQuery(t.description || t.name);
        setIsNewRunOpen(true);
    };

    const completedCount = tasks.filter(t => t.status === 'completed').length;
    const totalCount = tasks.length;

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground overflow-hidden">
            {/* Header Toolbar — matches Runs panel */}
            <div className="p-2 border-b border-border/50 bg-muted/20 flex items-center gap-1.5 shrink-0">
                <div className="relative flex-1 group">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    <Input
                        className="w-full bg-background/50 border-transparent focus:bg-background focus:border-border rounded-md text-xs pl-8 pr-2 h-8 transition-all placeholder:text-muted-foreground"
                        placeholder="Search runs..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>

                <Dialog open={isNewRunOpen} onOpenChange={setIsNewRunOpen}>
                    <DialogTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-background/80" title="New Swarm Run">
                            <Plus className="w-4 h-4" />
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="bg-card border-border sm:max-w-lg text-foreground">
                        <DialogHeader>
                            <DialogTitle className="text-foreground text-lg">Start New Swarm Run</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-muted-foreground">What should the swarm do?</label>
                                <div className="relative">
                                    <Input
                                        placeholder="e.g., Research latest AI trends and draft a report..."
                                        value={query}
                                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)}
                                        className="bg-muted border-input text-foreground placeholder:text-muted-foreground pr-24"
                                        onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => e.key === 'Enter' && handleStart()}
                                        autoFocus
                                        disabled={isStarting || isOptimizing}
                                    />
                                </div>
                                <div className="flex justify-between items-center text-xs text-muted-foreground">
                                    <span>Tip: Be specific about tools and outputs.</span>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        disabled={isOptimizing || isStarting || !query.trim()}
                                        className="h-6 text-xs text-neon-yellow hover:text-neon-yellow hover:bg-neon-yellow/10 px-2 gap-1 disabled:opacity-50"
                                        onClick={async () => {
                                            if (!query) return;
                                            setIsOptimizing(true);
                                            try {
                                                const res = await axios.post(`${API_BASE}/optimizer/preview`, { query: query });
                                                if (res.data && res.data.optimized) {
                                                    setQuery(res.data.optimized);
                                                }
                                            } catch (e) {
                                                console.error("Optimization failed", e);
                                            } finally {
                                                setIsOptimizing(false);
                                            }
                                        }}
                                    >
                                        {isOptimizing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                                        {isOptimizing ? "Optimizing..." : "Optimize"}
                                    </Button>
                                </div>
                            </div>
                        </div>
                        <DialogFooter className="flex items-center justify-between sm:justify-between">
                            <Button variant="ghost" onClick={() => setTemplateDrawerOpen(true)} className="text-muted-foreground hover:text-foreground gap-2">
                                <BookMarked className="w-4 h-4" />
                                Use Template
                            </Button>
                            <div className="flex gap-2">
                                <Button variant="outline" onClick={() => setIsNewRunOpen(false)} className="border-border text-foreground hover:bg-muted" disabled={isStarting}>Cancel</Button>
                                <Button onClick={handleStart} disabled={isStarting || !query.trim()} className="bg-neon-yellow text-charcoal-950 hover:bg-neon-yellow/90 font-semibold min-w-[100px]">
                                    {isStarting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Start Swarm"}
                                </Button>
                            </div>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>

            {/* Run history list matches exactly Sidebar.tsx */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide">
                {filteredRuns.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground space-y-4 fade-in-50">
                        <Network className="w-12 h-12 opacity-20" />
                        <div className="text-center">
                            <p className="text-sm font-medium">No swarm runs found</p>
                            <p className="text-xs opacity-70 mt-1">Click + to start a new swarm</p>
                        </div>
                    </div>
                ) : (
                    filteredRuns.map(run => {
                        const isActive = run.id === activeRunId;
                        const displayStatus = run.status;

                        return (
                            <div
                                key={run.id}
                                onClick={() => setActiveRunId(run.id)}
                                className={cn(
                                    "group relative p-4 rounded-xl border transition-all duration-300 cursor-pointer",
                                    "hover:shadow-md",
                                    isActive
                                        ? "border-neon-yellow/40 hover:border-neon-yellow/60 bg-neon-yellow/5"
                                        : "border-border/50 hover:border-primary/50 hover:bg-accent/50"
                                )}
                            >
                                <div className="flex justify-between items-start gap-3">
                                    <div className="flex-1 min-w-0">
                                        <p className={cn(
                                            "text-[13px] leading-relaxed font-medium transition-all duration-300 line-clamp-2",
                                            isActive
                                                ? "text-neon-yellow selection:bg-neon-yellow/30"
                                                : displayStatus === 'failed'
                                                    ? "text-red-500 group-hover:text-red-400"
                                                    : "text-foreground group-hover:text-foreground/80"
                                        )}>
                                            {run.label}
                                        </p>
                                    </div>
                                    {/* Action buttons show on hover if active and running */}
                                    {isActive && displayStatus === 'running' && (
                                        <div className="opacity-0 group-hover:opacity-100 flex gap-1 transition-all duration-200">
                                            <button
                                                onClick={(e) => { e.stopPropagation(); handlePauseResume(); }}
                                                className="p-1.5 rounded-lg hover:bg-neon-yellow/10 text-muted-foreground hover:text-neon-yellow"
                                                title={isPaused ? 'Resume' : 'Pause'}
                                            >
                                                {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
                                            </button>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); setInterventionOpen(true); }}
                                                className="p-1.5 rounded-lg hover:bg-neon-yellow/10 text-muted-foreground hover:text-neon-yellow"
                                                title="Intervene"
                                            >
                                                <Zap className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    )}
                                </div>

                                <div className="mt-4 pt-3 border-t border-border/50 flex flex-col gap-2 animate-in fade-in slide-in-from-top-2 duration-200">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            {displayStatus === 'running' ? (
                                                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20">
                                                    <span className="relative flex h-2 w-2">
                                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                                                        <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                                                    </span>
                                                    <span className="text-[10px] font-medium text-primary">Running {isActive ? `(${completedCount}/${totalCount})` : ''}</span>
                                                </div>
                                            ) : displayStatus === 'failed' ? (
                                                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-red-500/10 border border-red-500/20">
                                                    <XCircle className="w-2.5 h-2.5 text-red-500" />
                                                    <span className="text-[10px] font-medium text-red-500">Failed</span>
                                                </div>
                                            ) : (
                                                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/20">
                                                    <CheckCircle2 className="w-2.5 h-2.5 text-green-500" />
                                                    <span className="text-[10px] font-medium text-green-500">Completed</span>
                                                </div>
                                            )}
                                        </div>

                                        {/* Cost display */}
                                        {isActive && costUsd > 0 && (
                                            <div className="flex items-center gap-1.5 text-[10px] font-medium text-muted-foreground">
                                                <span>${costUsd.toFixed(4)}</span>
                                            </div>
                                        )}
                                    </div>

                                    {/* Progress Bar for Active Run */}
                                    {isActive && totalCount > 0 && displayStatus === 'running' && (
                                        <div className="w-full h-1 bg-muted rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-neon-yellow shadow-[0_0_10px_rgba(234,255,0,0.5)] transition-all duration-500"
                                                style={{ width: `${Math.max(5, (completedCount / totalCount) * 100)}%` }}
                                            />
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })
                )}
            </div>

            <InterventionModal />
            <TemplateDrawer onApply={handleApplyTemplate} />
        </div>
    );
};
