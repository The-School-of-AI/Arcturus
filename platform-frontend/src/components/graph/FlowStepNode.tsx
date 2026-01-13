import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { cn } from '@/lib/utils';

export interface FlowStepNodeData {
    label: string;
    description?: string;
    details?: string[];
    attributes?: string[];
    type?: string;
    isHighlighted?: boolean;
    isVisible?: boolean;
}

const FlowStepNode = ({ data, selected }: NodeProps<FlowStepNodeData>) => {
    const isHighlighted = data.isHighlighted;
    const isVisible = data.isVisible !== false;

    if (!isVisible) return <div className="opacity-0 pointer-events-none" />;

    const activeColor = '#F5C542'; // Neon Yellow

    const handleClass = "w-2.5 h-2.5 bg-muted-foreground border-2 border-background transition-all duration-300 hover:scale-150 hover:border-neon-yellow";

    const DualHandle = ({ pos, type, id }: { pos: Position; type: 'source' | 'target' | 'both', id?: string }) => (
        <>
            {(type === 'target' || type === 'both') && (
                <Handle
                    type="target"
                    position={pos}
                    id={id}
                    className={cn(handleClass, "z-10")}
                    style={{
                        backgroundColor: isHighlighted ? activeColor : undefined,
                        borderColor: isHighlighted ? 'white' : undefined,
                        opacity: 0.8
                    }}
                />
            )}
            {(type === 'source' || type === 'both') && (
                <Handle
                    type="source"
                    position={pos}
                    id={id}
                    className={cn(handleClass, "opacity-0 hover:opacity-100 z-20")}
                    style={{
                        backgroundColor: activeColor,
                        borderColor: 'white'
                    }}
                />
            )}
        </>
    );

    return (
        <div
            className={cn(
                "group relative px-5 py-4 rounded-xl border-2 transition-all duration-500 min-w-[240px] max-w-[320px] shadow-2xl",
                isHighlighted
                    ? "bg-card border-neon-yellow ring-4 ring-neon-yellow/20 -translate-y-1"
                    : "bg-card/90 border-border hover:border-muted-foreground/30",
                selected && !isHighlighted && "border-neon-yellow/50 ring-2 ring-neon-yellow/10"
            )}
        >
            {/* Handles - Top (Target/Input) and Bottom (Source/Output) only */}
            <DualHandle pos={Position.Top} type="target" id="top" />
            <DualHandle pos={Position.Bottom} type="source" id="bottom" />

            {/* Glowing Accent for Highlighted nodes */}
            {isHighlighted && (
                <div className="absolute inset-0 rounded-xl bg-neon-yellow/5 blur-xl -z-10 animate-pulse-slow" />
            )}

            <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between gap-3">
                    <span
                        className={cn(
                            "text-sm font-black tracking-tight leading-tight transition-colors duration-300",
                            isHighlighted ? "text-neon-yellow" : "text-foreground"
                        )}
                    >
                        {data.label}
                    </span>
                    {isHighlighted && (
                        <div className="flex h-2 w-2 relative">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-neon-yellow opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-neon-yellow"></span>
                        </div>
                    )}
                </div>

                {data.description && (
                    <div className="text-[11px] text-muted-foreground font-medium leading-relaxed italic border-l-2 border-border pl-2">
                        {data.description}
                    </div>
                )}

                {data.attributes && data.attributes.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                        {data.attributes.map((attr, idx) => (
                            <span
                                key={idx}
                                className={cn(
                                    "px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-tighter border transition-colors",
                                    isHighlighted
                                        ? "bg-neon-yellow/10 border-neon-yellow/30 text-neon-yellow"
                                        : "bg-muted/50 border-border text-muted-foreground"
                                )}
                            >
                                {attr}
                            </span>
                        ))}
                    </div>
                )}

                {data.details && data.details.length > 0 && (
                    <div className={cn(
                        "pt-3 border-t transition-colors",
                        isHighlighted ? "border-neon-yellow/20" : "border-border/50"
                    )}>
                        <ul className="space-y-2">
                            {data.details.map((detail, idx) => (
                                <li key={idx} className="flex gap-2 items-start">
                                    <div className={cn(
                                        "mt-1.5 h-1 w-1 rounded-full shrink-0",
                                        isHighlighted ? "bg-neon-yellow/60" : "bg-gray-600"
                                    )} />
                                    <span className={cn(
                                        "text-[10px] leading-relaxed font-medium transition-colors",
                                        isHighlighted ? "text-foreground" : "text-muted-foreground"
                                    )}>
                                        {detail}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    );
};

export default memo(FlowStepNode);
