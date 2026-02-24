// features/swarm/AgentPeekPanel.tsx
// Right inspector panel — mirrors WorkspacePanel in the Runs view.
// Primary: task metadata (title, status, deps, result) from the Zustand store.
// Secondary: live conversation log from /peek, when available.

import React, { useEffect, useState, useRef } from 'react';
import { X, Zap, CheckCircle2, Loader2, XCircle, Clock, FileText, MessageSquare } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useSwarmStore } from './useSwarmStore';
import { swarmApi } from './swarmApi';
import type { AgentLogEntry } from './types';

const statusIcon = {
    pending: <Clock className="w-3.5 h-3.5 text-muted-foreground" />,
    in_progress: <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />,
    completed: <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />,
    failed: <XCircle className="w-3.5 h-3.5 text-red-400" />,
} as const;

const statusLabel = {
    pending: 'Pending',
    in_progress: 'Running',
    completed: 'Completed',
    failed: 'Failed',
} as const;

export const AgentPeekPanel: React.FC = () => {
    const activeRunId = useSwarmStore(s => s.activeRunId);
    const selectedAgentId = useSwarmStore(s => s.selectedAgentId);
    const setSelectedAgent = useSwarmStore(s => s.setSelectedAgent);
    const setInterventionOpen = useSwarmStore(s => s.setInterventionOpen);
    const tasks = useSwarmStore(s => s.tasks);

    const [log, setLog] = useState<AgentLogEntry[]>([]);
    const [tab, setTab] = useState<'overview' | 'log'>('overview');
    const bottomRef = useRef<HTMLDivElement>(null);

    const selectedTask = tasks.find(t => t.assigned_to === selectedAgentId);
    const isActive = selectedTask?.status === 'in_progress';

    // Fetch conversation log
    useEffect(() => {
        if (!activeRunId || !selectedAgentId) { setLog([]); return; }
        const fetchLog = async () => {
            try {
                const entries = await swarmApi.peekAgent(activeRunId, selectedAgentId);
                setLog(entries);
            } catch { /* ignore */ }
        };
        fetchLog();
        if (!isActive) return;
        const interval = setInterval(fetchLog, 2000);
        return () => clearInterval(interval);
    }, [activeRunId, selectedAgentId, isActive]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [log]);

    // Reset tab when agent changes
    useEffect(() => { setTab('overview'); }, [selectedAgentId]);

    if (!selectedAgentId || !selectedTask) return null;

    const statusCfg = {
        pending: 'bg-muted text-muted-foreground',
        in_progress: 'bg-primary/10 text-primary',
        completed: 'bg-green-500/10 text-green-400',
        failed: 'bg-red-500/10 text-red-400',
    }[selectedTask.status];

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {/* Header */}
            <div className="shrink-0 p-3 border-b border-border flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                    {statusIcon[selectedTask.status]}
                    <span className="text-sm font-semibold text-foreground truncate">
                        {selectedAgentId}
                    </span>
                    {isActive && <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse shrink-0" />}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-primary"
                        title="Intervene" onClick={() => setInterventionOpen(true)}>
                        <Zap className="w-3.5 h-3.5" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground"
                        onClick={() => setSelectedAgent(null)}>
                        <X className="w-3.5 h-3.5" />
                    </Button>
                </div>
            </div>

            {/* Tab bar — Overview / Log (mirrors Runs' OVERVIEW / OUTPUT tabs) */}
            <div className="shrink-0 flex border-b border-border">
                {(['overview', 'log'] as const).map(t => (
                    <button key={t} onClick={() => setTab(t)}
                        className={cn(
                            'flex-1 py-2 text-[11px] font-semibold uppercase tracking-widest transition-colors',
                            tab === t
                                ? 'text-primary border-b-2 border-primary'
                                : 'text-muted-foreground hover:text-foreground',
                        )}>
                        {t === 'overview' ? '📋 Overview' : '💬 Log'}
                    </button>
                ))}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto scrollbar-hide">
                {tab === 'overview' ? (
                    <div className="p-4 space-y-4">
                        {/* Task title */}
                        <div>
                            <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-1">Task</p>
                            <p className="text-sm text-foreground leading-snug">{selectedTask.title}</p>
                        </div>

                        {/* Status badge */}
                        <div>
                            <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-1">Status</p>
                            <span className={cn('inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold', statusCfg)}>
                                {statusIcon[selectedTask.status]}
                                {statusLabel[selectedTask.status]}
                            </span>
                        </div>

                        {/* Dependencies */}
                        {selectedTask.dependencies.length > 0 && (
                            <div>
                                <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-1">Depends On</p>
                                <div className="flex flex-wrap gap-1">
                                    {selectedTask.dependencies.map(dep => (
                                        <span key={dep} className="px-2 py-0.5 rounded-md bg-muted text-[11px] text-muted-foreground font-mono">
                                            {dep}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Execution result */}
                        {selectedTask.result && (
                            <div>
                                <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-1">Result</p>
                                <div className="rounded-lg bg-muted/50 border border-border p-3">
                                    <p className="text-xs text-foreground whitespace-pre-wrap leading-relaxed">
                                        {selectedTask.result}
                                    </p>
                                </div>
                            </div>
                        )}

                        {/* Token / cost footer */}
                        <div className="flex items-center justify-between pt-1 border-t border-border">
                            <span className="text-[10px] text-muted-foreground font-mono">
                                {selectedTask.token_used.toLocaleString()} tokens
                            </span>
                            <span className="text-[10px] text-muted-foreground font-mono">
                                ${selectedTask.cost_usd.toFixed(5)}
                            </span>
                        </div>
                    </div>
                ) : (
                    <div className="p-3 space-y-2">
                        {log.length === 0 ? (
                            <p className="text-xs text-muted-foreground text-center pt-8 opacity-50">
                                {isActive ? 'Waiting for agent activity…' : 'No conversation log available.'}
                            </p>
                        ) : (
                            log.map((entry, i) => (
                                <div key={i}
                                    className={cn(
                                        'p-2.5 rounded-lg text-xs leading-relaxed',
                                        entry.role === 'assistant'
                                            ? 'bg-primary/10 text-foreground border border-primary/20'
                                            : entry.role === 'system'
                                                ? 'bg-muted/50 text-muted-foreground italic'
                                                : 'bg-muted text-foreground ml-4',
                                    )}>
                                    <span className={cn(
                                        'block text-[9px] font-bold uppercase tracking-widest mb-1',
                                        entry.role === 'assistant' ? 'text-primary' : 'text-muted-foreground',
                                    )}>
                                        {entry.role}
                                    </span>
                                    <p className="whitespace-pre-wrap break-words">{entry.content}</p>
                                </div>
                            ))
                        )}
                        <div ref={bottomRef} />
                    </div>
                )}
            </div>
        </div>
    );
};
