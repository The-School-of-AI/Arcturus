import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Bot, FileText, Brain, Code, Play, CheckCircle2, Loader2 } from 'lucide-react';
import type { AgentNodeData } from '@/types';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';

const AgentIcon = ({ type, className }: { type: string, className?: string }) => {
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

const AgentNode = ({ data, id, selected }: NodeProps<AgentNodeData>) => {
    const { selectNode } = useAppStore();

    // Status colors
    const getStatusColor = (status: string) => {
        switch (status) {
            case 'running': return 'text-primary';
            case 'completed': return 'text-green-500';
            case 'failed': return 'text-red-500';
            case 'stale': return 'text-muted-foreground/50';
            default: return 'text-muted-foreground';
        }
    };

    const statusColor = getStatusColor(data.status);
    const isRunning = data.status === 'running';
    const isStale = data.status === 'stale';

    return (
        <div
            className={cn(
                "relative min-w-[180px] rounded-xl transition-all duration-300 group glass",
                selected
                    ? "border-primary border-glow bg-card"
                    : "border-border hover:border-primary/50 bg-card/80 backdrop-blur-sm",
                isRunning && "animate-pulse-subtle border-primary ring-2 ring-primary/30 ring-offset-2 ring-offset-background border-glow bg-card",
                isStale && "opacity-90 grayscale border-border/50 bg-card/50 backdrop-blur-sm ring-2 ring-border/50"
            )}
            onClick={() => selectNode(id)}
        >
            {/* 🟢 Ticker UI for Running State */}
            {isRunning && (data.agent_prompt || data.prompt || data.description) && (
                <div className="absolute -top-12 left-1/2 -translate-x-1/2 w-[280px] z-50 pointer-events-none">
                    <div className="glass text-primary text-[10px] font-mono rounded-md px-2 py-1">
                        <div className="flex items-center gap-1.5 mb-0.5 border-b border-primary/20 pb-0.5">
                            <span className="relative flex h-1.5 w-1.5">
                                <span className="absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-primary"></span>
                            </span>
                            <span className="font-bold tracking-wider uppercase text-[9px]">Active Task</span>
                        </div>
                        <div className="overflow-hidden relative h-4">
                            <div className=" whitespace-nowrap">
                                {data.agent_prompt || data.prompt || data.description}
                            </div>
                        </div>
                    </div>
                    {/* Connector Line */}
                    <div className="absolute left-1/2 -translate-x-1/2 top-full w-[1px] h-3 bg-gradient-to-b from-primary/50 to-transparent"></div>
                </div>
            )}
            {/* Handles - All 4 sides for flexible routing */}
            <Handle
                type="target"
                position={Position.Top}
                className="!bg-muted-foreground !w-2.5 !h-2.5 !-top-1.5 transition-colors group-hover:!bg-primary"
            />
            <Handle
                type="target"
                position={Position.Left}
                className="!bg-muted-foreground !w-2.5 !h-2.5 !-left-1.5 transition-colors group-hover:!bg-primary"
            />
            <Handle
                type="source"
                position={Position.Right}
                className="!bg-muted-foreground !w-2.5 !h-2.5 !-right-1.5 transition-colors group-hover:!bg-primary"
            />

            <div className="p-4 flex items-start gap-3">
                <div className={cn(
                    "p-2 rounded-lg bg-background/50 border border-border transition-colors",
                    selected ? "text-primary border-primary/30" : "text-muted-foreground"
                )}>
                    <AgentIcon type={data.type} className="w-5 h-5" />
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                            {data.type}
                        </span>
                        {isRunning && <Loader2 className="w-3 h-3 animate-spin text-primary" />}
                    </div>

                    <h3 className={cn("text-sm font-semibold truncate mt-0.5", statusColor)}>
                        {data.label}
                    </h3>

                    {data.result && data.status === 'completed' && (
                        <p className="text-[10px] text-muted-foreground mt-1 truncate max-w-[120px]">
                            {data.result}
                        </p>
                    )}
                </div>
            </div>

            {/* Output Handle - Bottom Center */}
            <Handle
                type="source"
                position={Position.Bottom}
                className="!bg-muted-foreground !w-3 !h-3 !-bottom-1.5 transition-colors group-hover:!bg-primary"
            />

            {/* Active Glow Gradient (Optional) */}
            {selected && (
                <div className="absolute inset-0 -z-10 rounded-xl bg-primary/5 blur-xl pointer-events-none" />
            )}
        </div>
    );
};

export default memo(AgentNode);
