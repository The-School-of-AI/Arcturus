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
                    strokeWidth: selected ? 2.5 : 1.5,
                    stroke: selected ? '#F6FF4D' : '#666',
                }}
            />
            <EdgeLabelRenderer>
                <div
                    style={{
                        position: 'absolute',
                        transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
                        pointerEvents: 'all',
                    }}
                    className="nodrag nopan opacity-0 hover:opacity-100 transition-opacity"
                >
                    <button
                        className="w-5 h-5 bg-charcoal-900 border border-neon-yellow text-neon-yellow rounded-full flex items-center justify-center hover:bg-neon-yellow hover:text-charcoal-900 transition-colors shadow-lg shadow-neon-yellow/20"
                        onClick={onEdgeClick}
                    >
                        <Plus className="w-3 h-3" />
                    </button>
                </div>
            </EdgeLabelRenderer>
        </>
    );
};

export default CustomEdge;

