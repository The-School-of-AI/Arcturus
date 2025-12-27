import React from 'react';
import { BaseEdge, EdgeLabelRenderer, type EdgeProps, getSmoothStepPath } from 'reactflow';
import { Plus } from 'lucide-react';

const CustomEdge = ({
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    style = {},
    markerEnd,
    label,
    selected,
}: EdgeProps) => {
    // Use SmoothStep for orthogonal (90° turn) edges
    const [edgePath, labelX, labelY] = getSmoothStepPath({
        sourceX,
        sourceY,
        sourcePosition,
        targetX,
        targetY,
        targetPosition,
        borderRadius: 8, // Slightly rounded corners at turns
    });

    const onEdgeClick = (evt: React.MouseEvent) => {
        evt.stopPropagation();
        alert(`Insert node between ${id}?`);
    };

    return (
        <>
            <BaseEdge
                path={edgePath}
                markerEnd={markerEnd}
                style={{
                    ...style,
                    strokeWidth: selected ? 2 : 1.5,
                }}
            />
            <EdgeLabelRenderer>
                <div
                    style={{
                        position: 'absolute',
                        transform: `translate(-50%, -30%) translate(${labelX}px,${labelY}px)`,
                        pointerEvents: 'all',
                    }}
                    className="flex flex-col items-center gap-1"
                >
                    {/* Render Edge Label if present */}
                    {label && (
                        <div className="bg-popover text-popover-foreground text-[10px] font-medium px-2 py-1 rounded border border-border shadow-lg hover:border-neon-yellow/50 transition-colors">
                            {label}
                        </div>
                    )}

                    {/* Tiny Plus Button for inserts (hidden unless hovered) */}
                    <button
                        className="w-4 h-4 bg-muted border border-border text-muted-foreground rounded-full flex items-center justify-center hover:bg-neon-yellow hover:text-neutral-950 hover:scale-110 transition-all opacity-0 hover:opacity-100"
                        onClick={onEdgeClick}
                    >
                        <Plus className="w-2.5 h-2.5" />
                    </button>
                </div>
            </EdgeLabelRenderer>
        </>
    );
};

export default CustomEdge;

