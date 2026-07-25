import React from 'react';
import { BaseEdge, EdgeLabelRenderer, type EdgeProps, getBezierPath } from 'reactflow';
import { useAppStore } from '@/store';

const FlowEdge = ({
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
    source,
    target,
}: EdgeProps) => {
    const nodes = useAppStore(state => state.nodes);

    // Determine if this edge connects to/from a running node
    const sourceNode = nodes.find(n => n.id === source);
    const targetNode = nodes.find(n => n.id === target);
    const isActive = sourceNode?.data.status === 'running' ||
        targetNode?.data.status === 'running' ||
        (sourceNode?.data.status === 'completed' && targetNode?.data.status === 'running');

    // Use bezier for smooth curves (not orthogonal smooth-step)
    const [edgePath, labelX, labelY] = getBezierPath({
        sourceX,
        sourceY,
        sourcePosition,
        targetX,
        targetY,
        targetPosition,
    });

    // Compute stroke properties based on state
    const strokeWidth = isActive ? 2 : selected ? 1.5 : 1;
    const strokeColor = isActive
        ? 'hsl(var(--edge-active))'
        : selected
            ? 'hsl(var(--edge-active) / 0.6)'
            : 'hsl(var(--edge-idle))';

    return (
        <>
            {/* Base edge path */}
            <BaseEdge
                path={edgePath}
                markerEnd={markerEnd}
                style={{
                    ...style,
                    strokeWidth,
                    stroke: strokeColor,
                    transition: 'stroke 0.3s ease, stroke-width 0.3s ease',
                }}
            />

            {/* Animated flow overlay when active */}
            {isActive && (
                <path
                    d={edgePath}
                    fill="none"
                    stroke="hsl(var(--edge-flow))"
                    strokeWidth={strokeWidth}
                    className="edge-animated"
                    style={{ opacity: 0.6 }}
                />
            )}

            {/* Label — only shown on hover/select */}
            {label && (
                <EdgeLabelRenderer>
                    <div
                        style={{
                            position: 'absolute',
                            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
                            pointerEvents: 'all',
                        }}
                        className="opacity-0 hover:opacity-100 transition-opacity duration-200"
                    >
                        <div className="floating-panel text-[10px] font-medium px-2 py-0.5 rounded-md">
                            {label}
                        </div>
                    </div>
                </EdgeLabelRenderer>
            )}
        </>
    );
};

export default FlowEdge;
