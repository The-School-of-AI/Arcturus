import React, { memo, useState } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Bot, FileText, Brain, Code, Play, CheckCircle2, Loader2, AlertCircle, Clock } from 'lucide-react';
import type { AgentNodeData } from '@/types';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';

// ── Agent Icon by type ───────────────────────────────────────────────────────

const AgentIcon = ({ type, className }: { type: string; className?: string }) => {
    switch (type) {
        case 'Planner': return <CheckCircle2 className={className} />;
        case 'Retriever': return <FileText className={className} />;
        case 'Thinker': return <Brain className={className} />;
        case 'Coder': return <Code className={className} />;
        case 'Executor': return <Play className={className} />;
        case 'Evaluator': return <CheckCircle2 className={className} />;
        case 'Summary': return <FileText className={className} />;
        default: return <Bot className={className} />;
    }
};

// ── Status config ────────────────────────────────────────────────────────────

const STATUS_CONFIG = {
    running: {
        dotClass: 'bg-primary animate-pulse',
        textClass: 'text-foreground',
        borderClass: 'border-primary/40',
        label: 'running',
    },
    completed: {
        dotClass: 'bg-success',
        textClass: 'text-muted-foreground',
        borderClass: 'border-transparent',
        label: 'done',
    },
    failed: {
        dotClass: 'bg-destructive',
        textClass: 'text-destructive/80',
        borderClass: 'border-destructive/20',
        label: 'failed',
    },
    pending: {
        dotClass: 'bg-muted-foreground/40',
        textClass: 'text-muted-foreground',
        borderClass: 'border-transparent',
        label: 'pending',
    },
    waiting_input: {
        dotClass: 'bg-warning animate-pulse',
        textClass: 'text-warning',
        borderClass: 'border-warning/20',
        label: 'waiting',
    },
    stale: {
        dotClass: 'bg-muted-foreground/30',
        textClass: 'text-muted-foreground/50',
        borderClass: 'border-transparent',
        label: 'stale',
    },
    stopped: {
        dotClass: 'bg-muted-foreground/40',
        textClass: 'text-muted-foreground',
        borderClass: 'border-transparent',
        label: 'stopped',
    },
};

// ── CapsuleNode ──────────────────────────────────────────────────────────────

const CapsuleNode = ({ data, id, selected }: NodeProps<AgentNodeData>) => {
    const { selectNode } = useAppStore();
    const uiMode = useAppStore(state => state.uiMode);
    const [isHovered, setIsHovered] = useState(false);

    const status = STATUS_CONFIG[data.status] || STATUS_CONFIG.pending;
    const isRunning = data.status === 'running';
    const isCompleted = data.status === 'completed';
    const isStale = data.status === 'stale';
    const showExpanded = selected || (isHovered && (isRunning || isCompleted));
    const showDebugInfo = uiMode === 'debug';

    return (
        <div
            className={cn(
                "relative group transition-all",
                isStale && "opacity-60"
            )}
            onClick={() => selectNode(id)}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            {/* ── Running ticker — floats above ── */}
            {isRunning && (data.agent_prompt || data.prompt || data.description) && (
                <div className="absolute -top-10 left-1/2 -translate-x-1/2 w-[240px] z-50 pointer-events-none">
                    <div className="floating-panel text-primary text-2xs font-mono rounded-lg px-2.5 py-1.5">
                        <div className="flex items-center gap-1.5 mb-0.5">
                            <span className="relative flex h-1.5 w-1.5">
                                <span className="absolute inline-flex h-full w-full rounded-full bg-primary opacity-75 animate-ping" />
                                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-primary" />
                            </span>
                            <span className="font-bold tracking-wider uppercase text-[9px]">Active</span>
                        </div>
                        <div className="overflow-hidden h-3.5">
                            <div className="animate-ticker whitespace-nowrap text-[10px] opacity-80">
                                {data.agent_prompt || data.prompt || data.description}
                            </div>
                        </div>
                    </div>
                    <div className="absolute left-1/2 -translate-x-1/2 top-full w-[1px] h-2 bg-gradient-to-b from-primary/40 to-transparent" />
                </div>
            )}

            {/* ── Handles — invisible until hover ── */}
            <Handle
                type="target"
                position={Position.Top}
                className={cn(
                    "!w-2 !h-2 !-top-1 !border-none transition-all duration-200",
                    isHovered || selected ? "!bg-primary/60" : "!bg-transparent"
                )}
            />
            <Handle
                type="target"
                position={Position.Left}
                className={cn(
                    "!w-2 !h-2 !-left-1 !border-none transition-all duration-200",
                    isHovered || selected ? "!bg-primary/60" : "!bg-transparent"
                )}
            />
            <Handle
                type="source"
                position={Position.Right}
                className={cn(
                    "!w-2 !h-2 !-right-1 !border-none transition-all duration-200",
                    isHovered || selected ? "!bg-primary/60" : "!bg-transparent"
                )}
            />
            <Handle
                type="source"
                position={Position.Bottom}
                className={cn(
                    "!w-2 !h-2 !-bottom-1 !border-none transition-all duration-200",
                    isHovered || selected ? "!bg-primary/60" : "!bg-transparent"
                )}
            />

            {/* ── Capsule body ── */}
            <div className={cn(
                "capsule-node rounded-2xl transition-all duration-200",
                selected && "selected",
                isRunning && "running",
                showExpanded ? "min-w-[220px]" : "min-w-[160px]"
            )}>
                {/* Running gradient sweep overlay */}
                {isRunning && (
                    <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none">
                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-primary/5 to-transparent animate-gradient-sweep" />
                    </div>
                )}

                {/* Compact capsule row */}
                <div className="flex items-center gap-2.5 px-3.5 py-2.5 relative z-10">
                    {/* Icon */}
                    <div className={cn(
                        "w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition-colors",
                        selected || isRunning
                            ? "bg-primary/10 text-primary"
                            : "bg-surface-2 text-muted-foreground"
                    )}>
                        {isRunning ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
                        ) : (
                            <AgentIcon type={data.type} className="w-3.5 h-3.5" />
                        )}
                    </div>

                    {/* Label + type */}
                    <div className="flex-1 min-w-0">
                        <h3 className={cn(
                            "text-xs font-semibold truncate leading-tight",
                            status.textClass
                        )}>
                            {data.label}
                        </h3>
                        <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">
                            {data.type}
                        </span>
                    </div>

                    {/* Status dot */}
                    <span className={cn("w-2 h-2 rounded-full shrink-0", status.dotClass)} />
                </div>

                {/* ── Expanded detail (hover or selected) ── */}
                {showExpanded && (
                    <div className="px-3.5 pb-3 pt-0 border-t border-border/30 mt-0 animate-content-in">
                        {/* Result preview */}
                        {data.result && isCompleted && (
                            <p className="text-[10px] text-muted-foreground mt-2 line-clamp-3 leading-relaxed">
                                {data.result}
                            </p>
                        )}

                        {/* Error info */}
                        {data.error && data.status === 'failed' && (
                            <div className="flex items-start gap-1.5 mt-2">
                                <AlertCircle className="w-3 h-3 text-destructive shrink-0 mt-0.5" />
                                <p className="text-[10px] text-destructive/80 line-clamp-2">
                                    {data.error}
                                </p>
                            </div>
                        )}

                        {/* Debug info */}
                        {showDebugInfo && (
                            <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-[9px] font-mono text-muted-foreground/60">
                                {data.execution_time && (
                                    <span className="flex items-center gap-0.5">
                                        <Clock className="w-2.5 h-2.5" />
                                        {typeof data.execution_time === 'number'
                                            ? `${data.execution_time.toFixed(1)}s`
                                            : data.execution_time}
                                    </span>
                                )}
                                {data.cost !== undefined && (
                                    <span>${data.cost.toFixed(4)}</span>
                                )}
                                {data.executed_model && (
                                    <span className="truncate max-w-[100px]">{data.executed_model}</span>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* ── Selected glow ── */}
            {selected && (
                <div className="absolute inset-0 -z-10 rounded-2xl bg-primary/5 blur-xl pointer-events-none" />
            )}
        </div>
    );
};

export default memo(CapsuleNode);
