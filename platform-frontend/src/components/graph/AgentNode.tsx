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
            case 'running': return 'text-neon-yellow';
            case 'completed': return 'text-green-400';
            case 'failed': return 'text-red-400';
            default: return 'text-muted-foreground';
        }
    };

    const statusColor = getStatusColor(data.status);
    const isRunning = data.status === 'running';

    return (
        <div
            className={cn(
                "relative min-w-[180px] bg-card border rounded-xl shadow-lg transition-all duration-300 group",
                selected
                    ? "border-neon-yellow shadow-[0_0_15px_rgba(246,255,77,0.3)] bg-charcoal-800"
                    : "border-border hover:border-primary/50 bg-charcoal-800/80 backdrop-blur-sm",
                isRunning && "animate-pulse-subtle border-neon-yellow ring-2 ring-neon-yellow ring-offset-2 ring-offset-charcoal-900 shadow-[0_0_20px_rgba(246,255,77,0.5)] bg-charcoal-800"
            )}
            onClick={() => selectNode(id)}
        >
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
                    selected ? "text-neon-yellow border-neon-yellow/30" : "text-muted-foreground"
                )}>
                    <AgentIcon type={data.type} className="w-5 h-5" />
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                            {data.type}
                        </span>
                        {isRunning && <Loader2 className="w-3 h-3 animate-spin text-neon-yellow" />}
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
                <div className="absolute inset-0 -z-10 rounded-xl bg-neon-yellow/5 blur-xl pointer-events-none" />
            )}
        </div>
    );
};

export default memo(AgentNode);
