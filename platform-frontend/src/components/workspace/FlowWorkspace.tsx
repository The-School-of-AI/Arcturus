import React, { useState, useCallback, useMemo, useEffect } from 'react';
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState,
    MarkerType,
    ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useAppStore } from '@/store';
import FlowStepNode from '../graph/FlowStepNode';
import { Button } from '@/components/ui/button';
import { Play, RotateCcw, ChevronRight, Layout, ListOrdered, Share2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const nodeTypes = {
    custom: FlowStepNode,
};

const FlowWorkspaceInner: React.FC = () => {
    const { flowData } = useAppStore();

    // Initial State from flowData
    const initialNodes = flowData?.nodes || [];
    const initialEdges = flowData?.edges || [];

    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

    const [mode, setMode] = useState<'READER' | 'SEQUENCE'>('READER');
    const [visibleNodeIds, setVisibleNodeIds] = useState<Set<string>>(new Set());
    const [activeNodeId, setActiveNodeId] = useState<string | null>(null);

    // Sync state when flowData changes
    useEffect(() => {
        if (flowData) {
            setNodes(flowData.nodes.map((n: any) => ({ ...n, draggable: true })));
            setEdges(flowData.edges.map((e: any) => ({ ...e, animated: false })));
        }
    }, [flowData, setNodes, setEdges]);

    const initializeSequence = useCallback(() => {
        const firstNode = nodes.find((n) => !edges.some((e) => e.target === n.id)) || nodes[0];
        if (firstNode) {
            setVisibleNodeIds(new Set([firstNode.id]));
            setActiveNodeId(firstNode.id);
        }
    }, [nodes, edges]);

    const handleModeChange = (newMode: 'READER' | 'SEQUENCE') => {
        setMode(newMode);
        if (newMode === 'SEQUENCE') {
            initializeSequence();
        } else {
            setVisibleNodeIds(new Set());
            setActiveNodeId(null);
        }
    };

    const advanceSequence = useCallback(() => {
        const nextNodeIds = new Set<string>(Array.from(visibleNodeIds));
        let added = false;
        let lastTargetId = null;

        edges.forEach((edge) => {
            if (visibleNodeIds.has(edge.source) && !nextNodeIds.has(edge.target)) {
                nextNodeIds.add(edge.target);
                lastTargetId = edge.target;
                added = true;
            }
        });

        if (added) {
            setVisibleNodeIds(nextNodeIds);
            if (lastTargetId) setActiveNodeId(lastTargetId);
        }
    }, [visibleNodeIds, edges]);

    const displayNodes = useMemo(() => {
        return nodes.map((node) => {
            const isVisible = mode === 'READER' || visibleNodeIds.has(node.id);
            const isHighlighted = mode === 'SEQUENCE' && activeNodeId === node.id;
            return {
                ...node,
                data: {
                    ...node.data,
                    isVisible,
                    isHighlighted,
                },
            };
        });
    }, [nodes, mode, visibleNodeIds, activeNodeId]);

    const displayEdges = useMemo(() => {
        return edges.map((edge) => {
            const sourceVisible = mode === 'READER' || visibleNodeIds.has(edge.source);
            const targetVisible = mode === 'READER' || visibleNodeIds.has(edge.target);
            const isVisible = sourceVisible && targetVisible;

            return {
                ...edge,
                hidden: !isVisible,
                animated: mode === 'SEQUENCE' && isVisible,
                markerEnd: {
                    type: MarkerType.ArrowClosed,
                    color: isVisible ? '#eaff00' : '#1a1a1a'
                },
                style: {
                    stroke: isVisible ? '#eaff00' : '#1a1a1a',
                    strokeWidth: 2,
                    opacity: isVisible ? 1 : 0.1
                },
            };
        });
    }, [edges, mode, visibleNodeIds]);

    const canGoNext = useMemo(() => {
        if (mode !== 'SEQUENCE') return false;
        return edges.some((e) => {
            const sourceVisible = visibleNodeIds.has(e.source);
            const targetVisible = visibleNodeIds.has(e.target);
            return sourceVisible && !targetVisible;
        });
    }, [mode, edges, visibleNodeIds]);

    const onNodeClick = useCallback((_event: React.MouseEvent, node: any) => {
        useAppStore.getState().setSelectedExplorerNodeId(node.id);

        if (mode === 'SEQUENCE') {
            const targets = edges.filter((e) => e.source === node.id).map((e) => e.target);
            if (targets.length > 0) {
                setVisibleNodeIds((prev) => {
                    const next = new Set(prev);
                    targets.forEach((t) => next.add(t));
                    return next;
                });
                setActiveNodeId(node.id);
            }
        }
    }, [mode, edges]);

    if (!flowData) {
        return (
            <div className="w-full h-full flex flex-col items-center justify-center bg-charcoal-950 p-12 text-center text-white">
                <div className="relative mb-8">
                    <div className="absolute inset-0 bg-neon-yellow/10 blur-3xl rounded-full" />
                    <div className="relative p-8 bg-charcoal-900 border border-white/5 rounded-3xl shadow-2xl">
                        <Layout className="w-20 h-20 text-neon-yellow/20" />
                        <Code2 className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 text-neon-yellow animate-pulse" />
                    </div>
                </div>
                <div className="max-w-md space-y-4">
                    <h2 className="text-3xl font-black tracking-tighter uppercase italic">Architecture Map</h2>
                    <p className="text-gray-500 text-sm leading-relaxed">
                        Select a function or module in the left panel and click <strong className="text-neon-yellow">"Start Analysis"</strong> to visualize the execution flow and logical dependencies of your code.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="w-full h-full bg-[#050505] relative overflow-hidden">
            {/* Header Controls */}
            <div className="absolute top-6 left-6 right-6 z-50 flex justify-between items-start pointer-events-none">
                <div className="flex flex-col gap-4 pointer-events-auto">
                    {/* Mode Toggle */}
                    <div className="bg-charcoal-900/80 backdrop-blur-xl ring-1 ring-white/10 shadow-2xl rounded-2xl p-1.5 flex gap-1">
                        <button
                            onClick={() => handleModeChange('READER')}
                            className={cn(
                                "flex items-center gap-2 px-6 py-2.5 rounded-xl transition-all duration-300 text-xs font-black uppercase tracking-widest",
                                mode === 'READER'
                                    ? "bg-neon-yellow text-charcoal-950 shadow-[0_0_20px_rgba(234,255,0,0.2)]"
                                    : "text-gray-500 hover:text-white hover:bg-white/5"
                            )}
                        >
                            <Layout className="w-3.5 h-3.5" />
                            Overview
                        </button>
                        <button
                            onClick={() => handleModeChange('SEQUENCE')}
                            className={cn(
                                "flex items-center gap-2 px-6 py-2.5 rounded-xl transition-all duration-300 text-xs font-black uppercase tracking-widest",
                                mode === 'SEQUENCE'
                                    ? "bg-neon-yellow text-charcoal-950 shadow-[0_0_20px_rgba(234,255,0,0.2)]"
                                    : "text-gray-500 hover:text-white hover:bg-white/5"
                            )}
                        >
                            <ListOrdered className="w-3.5 h-3.5" />
                            Sequence
                        </button>
                    </div>

                    {/* Sequence Controls */}
                    {mode === 'SEQUENCE' && (
                        <div className="bg-charcoal-900/80 backdrop-blur-xl ring-1 ring-white/10 shadow-2xl rounded-2xl p-1.5 flex gap-1 animate-in slide-in-from-left-4">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={initializeSequence}
                                className="h-10 w-10 p-0 text-gray-500 hover:text-neon-yellow hover:bg-neon-yellow/5 rounded-xl"
                                title="Reset Flow"
                            >
                                <RotateCcw className="w-4 h-4" />
                            </Button>
                            <Button
                                onClick={advanceSequence}
                                disabled={!canGoNext}
                                className={cn(
                                    "h-10 px-6 rounded-xl transition-all font-black text-xs uppercase tracking-widest flex items-center gap-2",
                                    canGoNext
                                        ? "bg-neon-yellow text-charcoal-950 shadow-lg active:scale-95"
                                        : "bg-gray-800 text-gray-600 cursor-not-allowed"
                                )}
                            >
                                Next Step
                                <ChevronRight className="w-4 h-4" />
                            </Button>
                        </div>
                    )}
                </div>

                <div className="flex gap-2 pointer-events-auto">
                    <Button variant="outline" className="bg-charcoal-900/50 border-white/5 text-gray-400 hover:text-white hover:border-white/20 gap-2 font-bold text-xs">
                        <Share2 className="w-3.5 h-3.5" />
                        Export
                    </Button>
                </div>
            </div>

            <ReactFlow
                nodes={displayNodes}
                edges={displayEdges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                nodeTypes={nodeTypes}
                fitView
                snapToGrid
                snapGrid={[15, 15]}
                nodesDraggable={mode === 'READER'}
                nodesConnectable={false}
                elementsSelectable={true}
            >
                <Background color="#1a1a1a" gap={20} />
                <Controls className="bg-charcoal-900 border-white/10 fill-white" />
                <MiniMap
                    style={{ backgroundColor: '#0a0a0a' }}
                    nodeColor={(n) => n.data?.isHighlighted ? '#eaff00' : '#262626'}
                    maskColor="rgba(0, 0, 0, 0.7)"
                />
            </ReactFlow>

            {/* Sequence Tooltip */}
            {mode === 'SEQUENCE' && (
                <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
                    <div className="bg-charcoal-900/90 backdrop-blur px-8 py-4 rounded-full shadow-[0_0_40px_rgba(0,0,0,0.5)] border border-neon-yellow/20 flex items-center gap-4 animate-bounce shrink-0">
                        <span className="font-black text-xs uppercase tracking-widest text-neon-yellow">
                            {canGoNext ? "Click 'Next' or a node to follow the logic" : 'End of mapped sequence'}
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
};

export const FlowWorkspace: React.FC = () => (
    <ReactFlowProvider>
        <FlowWorkspaceInner />
    </ReactFlowProvider>
);

const Code2 = ({ className }: { className?: string }) => (
    <svg
        xmlns="http://www.w3.org/2000/svg"
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
    >
        <path d="m18 16 4-4-4-4" /><path d="m6 8-4 4 4 4" /><path d="m14.5 4-5 16" />
    </svg>
);
