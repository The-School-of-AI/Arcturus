import React, { useState, useCallback, useMemo, useEffect } from 'react';
import ReactFlow, {
    Background,
    Controls,
    useNodesState,
    useEdgesState,
    MarkerType,
    ReactFlowProvider,
    useReactFlow,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useAppStore } from '@/store';
import FlowStepNode from '../graph/FlowStepNode';
import CustomEdge from '../graph/CustomEdge'; // Import Custom Edge
import { Button } from '@/components/ui/button';
import { Play, RotateCcw, ChevronRight, Layout, ListOrdered, Share2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import dagre from 'dagre';

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const nodeWidth = 340; // Increased from 280
const nodeHeight = 250; // Increased from 150 to fit rich details

const getLayoutedElements = (nodes: any[], edges: any[], direction = 'TB') => {
    const isHorizontal = direction === 'LR';
    dagreGraph.setGraph({ rankdir: direction, ranksep: 150, nodesep: 80 }); // Increased spacing

    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
    });

    edges.forEach((edge) => {
        // Force type to custom to ensure labels render
        edge.type = 'custom';
        // CRITICAL: Force handle connection to specific IDs we defined in FlowStepNode
        edge.sourceHandle = 'bottom';
        edge.targetHandle = 'top';

        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        return {
            ...node,
            type: 'custom', // FORCE to 'custom' to ensure FlowStepNode (Rich UI) is used
            targetPosition: isHorizontal ? 'left' : 'top',
            sourcePosition: isHorizontal ? 'right' : 'bottom',
            // Shift slightly so handles align
            position: {
                x: nodeWithPosition.x - nodeWidth / 2,
                y: nodeWithPosition.y - nodeHeight / 2,
            },
        };
    });

    return { nodes: layoutedNodes, edges };
};

// NodeTypes moved inside component with useMemo

const FlowWorkspaceInner: React.FC = () => {
    const { flowData } = useAppStore();

    const nodeTypes = useMemo(() => ({
        custom: FlowStepNode,
        agent: FlowStepNode
    }), []);

    const edgeTypes = useMemo(() => ({
        custom: CustomEdge,
        smoothstep: CustomEdge // fallback
    }), []);

    // Initial State from flowData
    const initialNodes = flowData?.nodes || [];
    const initialEdges = flowData?.edges || [];

    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

    const [mode, setMode] = useState<'READER' | 'SEQUENCE'>('READER');
    const [visibleNodeIds, setVisibleNodeIds] = useState<Set<string>>(new Set());
    const [activeNodeId, setActiveNodeId] = useState<string | null>(null);

    const { fitView, setCenter } = useReactFlow();

    // Sync state when flowData changes
    useEffect(() => {
        if (flowData) {
            const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
                flowData.nodes.map((n: any) => ({ ...n, draggable: true })),
                flowData.edges.map((e: any) => ({ ...e, animated: false }))
            );

            setNodes(layoutedNodes);
            setEdges(layoutedEdges);
            // Small delay to ensure nodes are rendered before fitting
            setTimeout(() => {
                fitView({ padding: 0.2, duration: 800 });
            }, 50);
        }
    }, [flowData, setNodes, setEdges, fitView]);

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
        let lastTargetId: string | null = null;

        edges.forEach((edge) => {
            if (visibleNodeIds.has(edge.source) && !nextNodeIds.has(edge.target)) {
                nextNodeIds.add(edge.target);
                lastTargetId = edge.target;
                added = true;
            }
        });

        if (added) {
            setVisibleNodeIds(nextNodeIds);
            if (lastTargetId) {
                setActiveNodeId(lastTargetId);
                const targetNode = nodes.find(n => n.id === lastTargetId);
                if (targetNode) {
                    setCenter(
                        targetNode.position.x + nodeWidth / 2,
                        targetNode.position.y + nodeHeight / 2,
                        { duration: 800, zoom: 1.0 }
                    );
                }
            }
        }
    }, [visibleNodeIds, edges, nodes, setCenter]);

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
                    color: isVisible ? '#F5C542' : '#1a1a1a'
                },
                style: {
                    stroke: isVisible ? '#F5C542' : '#1a1a1a',
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
            <div className="w-full h-full flex flex-col items-center justify-center bg-background p-12 text-center text-foreground">
                <div className="relative mb-8">
                    <div className="absolute inset-0 bg-neon-yellow/10 blur-3xl rounded-full" />
                    <div className="relative p-8 bg-card border border-border/50 rounded-3xl shadow-2xl">
                        <Layout className="w-20 h-20 text-neon-yellow/20" />
                        <Code2 className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 text-neon-yellow animate-pulse" />
                    </div>
                </div>
                <div className="max-w-md space-y-4">
                    <h2 className="text-3xl font-black tracking-tighter uppercase italic">Architecture Map</h2>
                    <p className="text-muted-foreground text-sm leading-relaxed">
                        Select a function or module in the left panel and click <strong className="text-neon-yellow">"Start Analysis"</strong> to visualize the execution flow and logical dependencies of your code.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="w-full h-full bg-[#050505] relative overflow-hidden">
            {/* Header Controls - Centered at Top to avoid Zoom controls (usually corners) */}
            <div className="absolute top-2 left-1/2 -translate-x-1/2 z-50 flex gap-4 items-start pointer-events-none">
                <div className="flex flex-col gap-4 items-center pointer-events-auto">
                    {/* Mode Toggle */}
                    <div className="bg-card/80 backdrop-blur-xl ring-2 ring-white/10 shadow-2xl rounded-2xl p-1.5 flex gap-1">
                        <button
                            onClick={() => handleModeChange('READER')}
                            className={cn(
                                "flex items-center gap-2 px-6 py-2.5 rounded-sm transition-all duration-300 text-xs font-black uppercase tracking-widest",
                                mode === 'READER'
                                    ? "bg-neon-yellow text-charcoal-950 shadow-[0_0_20px_rgba(234,255,0,0.2)]"
                                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                            )}
                        >
                            <Layout className="w-3.5 h-3.5" />
                            Overview
                        </button>
                        <button
                            onClick={() => handleModeChange('SEQUENCE')}
                            className={cn(
                                "flex items-center gap-2 px-6 py-2.5 rounded-sm transition-all duration-300 text-xs font-black uppercase tracking-widest",
                                mode === 'SEQUENCE'
                                    ? "bg-neon-yellow text-charcoal-950 shadow-[0_0_20px_rgba(234,255,0,0.2)]"
                                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                            )}
                        >
                            <ListOrdered className="w-3.5 h-3.5" />
                            Sequence
                        </button>
                    </div>

                    {/* Sequence Controls */}
                    {mode === 'SEQUENCE' && (
                        <div className="bg-card/80 backdrop-blur-xl ring-1 ring-white/10 shadow-2xl rounded-2xl p-1.5 flex gap-1 animate-in slide-in-from-top-4">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={initializeSequence}
                                className="h-10 w-10 p-0 text-muted-foreground hover:text-neon-yellow hover:bg-neon-yellow/5 rounded-sm"
                                title="Reset Flow"
                            >
                                <RotateCcw className="w-4 h-4" />
                            </Button>
                            <Button
                                onClick={advanceSequence}
                                disabled={!canGoNext}
                                className={cn(
                                    "h-10 px-6 rounded-sm transition-all font-black text-xs uppercase tracking-widest flex items-center gap-2",
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
            </div>

            <ReactFlow
                id="explorer-flow"
                nodes={displayNodes}
                edges={displayEdges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                fitView
                snapToGrid
                snapGrid={[15, 15]}
                nodesDraggable={mode === 'READER'}
                nodesConnectable={false}
                elementsSelectable={true}
            >
                <Background color="#1a1a1a" gap={20} />
                <Controls className="bg-card border-border fill-white" />
            </ReactFlow>

            {/* Sequence Tooltip */}
            {mode === 'SEQUENCE' && (
                <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
                    <div className="bg-card/90 backdrop-blur px-8 py-4 rounded-full shadow-[0_0_40px_rgba(0,0,0,0.5)] border border-neon-yellow/20 flex items-center gap-4 animate-pulse shrink-0">
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
