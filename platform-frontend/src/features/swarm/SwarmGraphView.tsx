// features/swarm/SwarmGraphView.tsx
// Live DAG visualization using React Flow, driven by useSwarmStore.
// Each SwarmTask becomes a node; dependencies become edges.
// Node colors animate based on task status (pending/in_progress/completed/failed).

import React, { useMemo, useCallback } from 'react';
import ReactFlow, {
    Background,
    Controls,
    type Node,
    type Edge,
    useReactFlow,
    ReactFlowProvider,
    Handle,
    Position,
    MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Bot, FileText, Brain, Code, Play, CheckCircle2, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSwarmStore } from './useSwarmStore';
import type { SwarmTask } from './types';

// ------------------------------- Custom Node --------------------------------

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

const getStatusColor = (status: string) => {
    switch (status) {
        case 'in_progress': return 'text-primary';
        case 'completed': return 'text-green-500';
        case 'failed': return 'text-red-500';
        case 'pending': return 'text-muted-foreground/50';
        default: return 'text-muted-foreground';
    }
};

const SwarmTaskNode = ({ data, selected }: { data: SwarmTask; selected: boolean }) => {
    const setSelectedAgent = useSwarmStore(s => s.setSelectedAgent);
    const selectedAgentId = useSwarmStore(s => s.selectedAgentId);
    const isSelected = selected || selectedAgentId === data.assigned_to;

    const statusColor = getStatusColor(data.status);
    const isRunning = data.status === 'in_progress';

    return (
        <div
            className={cn(
                "relative min-w-[200px] rounded-xl transition-all duration-300 group glass",
                isSelected
                    ? "border-primary border-[1.5px] bg-card shadow-[0_0_15px_rgba(59,130,246,0.2)]"
                    : "border-border hover:border-primary/50 bg-card/80 backdrop-blur-sm border-[1.5px]",
                isRunning && "animate-pulse-subtle border-primary ring-2 ring-primary/30 ring-offset-2 ring-offset-background bg-card border-[1.5px]"
            )}
        >
            {/* Handles - All 4 sides for flexible routing/edges */}
            <Handle id="top" type="target" position={Position.Top} className="!bg-muted-foreground !w-2.5 !h-2.5 !-top-1.5 transition-colors group-hover:!bg-primary" />
            <Handle id="left" type="target" position={Position.Left} className="!bg-muted-foreground !w-2.5 !h-2.5 !-left-1.5 transition-colors group-hover:!bg-primary" />
            <Handle id="right" type="source" position={Position.Right} className="!bg-muted-foreground !w-2.5 !h-2.5 !-right-1.5 transition-colors group-hover:!bg-primary" />
            <Handle id="bottom" type="source" position={Position.Bottom} className="!bg-muted-foreground !w-3 !h-3 !-bottom-1.5 transition-colors group-hover:!bg-primary" />

            <div className="p-4 flex items-start gap-3">
                <div className={cn(
                    "p-2 rounded-lg bg-background/50 border border-border transition-colors",
                    isSelected ? "text-primary border-primary/30" : "text-muted-foreground"
                )}>
                    <AgentIcon type={data.assigned_to} className="w-5 h-5" />
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground truncate max-w-[120px]">
                            {data.assigned_to}
                        </span>
                        {isRunning && <Loader2 className="w-3 h-3 animate-spin text-primary" />}
                    </div>

                    <h3 className={cn("text-sm font-semibold mt-0.5 leading-snug", statusColor)}>
                        {data.title}
                    </h3>
                </div>
            </div>

            {/* Active Glow Gradient (Optional) */}
            {isSelected && (
                <div className="absolute inset-0 -z-10 rounded-xl bg-primary/5 blur-xl pointer-events-none" />
            )}
        </div>
    );
};

const NODE_TYPES = { swarmTask: SwarmTaskNode };

// --------------------------------- Layout ----------------------------------

function buildFlow(tasks: SwarmTask[]): { nodes: Node[]; edges: Edge[] } {
    const colWidth = 220;
    const rowHeight = 120;

    // Simple layered layout: group by dependency depth
    const depthMap: Record<string, number> = {};
    const computeDepth = (tid: string, visited = new Set<string>()): number => {
        if (visited.has(tid)) return 0;
        if (depthMap[tid] !== undefined) return depthMap[tid];
        visited.add(tid);
        const task = tasks.find(t => t.task_id === tid);
        if (!task || task.dependencies.length === 0) { depthMap[tid] = 0; return 0; }
        const d = 1 + Math.max(...task.dependencies.map(dep => computeDepth(dep, visited)));
        depthMap[tid] = d;
        return d;
    };
    tasks.forEach(t => computeDepth(t.task_id));

    // Count tasks per depth for horizontal centering
    const byDepth: Record<number, SwarmTask[]> = {};
    tasks.forEach(t => {
        const d = depthMap[t.task_id] ?? 0;
        byDepth[d] = [...(byDepth[d] || []), t];
    });

    const nodes: Node[] = tasks.map(task => {
        const depth = depthMap[task.task_id] ?? 0;
        const col = byDepth[depth].indexOf(task);
        const total = byDepth[depth].length;
        return {
            id: task.task_id,
            type: 'swarmTask',
            data: task,
            position: { x: col * colWidth - (total - 1) * colWidth / 2, y: depth * rowHeight },
        };
    });

    const edges: Edge[] = tasks.flatMap(task =>
        task.dependencies.map(dep => {
            const isRunning = task.status === 'in_progress';
            const edgeColor = isRunning ? 'hsl(var(--primary))' : 'hsl(var(--border))';
            return {
                id: `${dep}->${task.task_id}`,
                source: dep,
                target: task.task_id,
                sourceHandle: 'bottom',
                targetHandle: 'top',
                type: 'smoothstep',
                animated: isRunning,
                style: { stroke: edgeColor, strokeWidth: 1.5 },
                markerEnd: {
                    type: MarkerType.ArrowClosed,
                    color: edgeColor,
                    width: 15,
                    height: 15,
                }
            };
        })
    );

    return { nodes, edges };
}

// ------------------------------ Inner graph --------------------------------

const Inner: React.FC = () => {
    const tasks = useSwarmStore(s => s.tasks);
    const { nodes, edges } = useMemo(() => buildFlow(tasks), [tasks]);
    const { fitView } = useReactFlow();
    const setSelectedAgent = useSwarmStore(s => s.setSelectedAgent);
    const selectedAgentId = useSwarmStore(s => s.selectedAgentId);

    const [userIntervened, setUserIntervened] = React.useState(false);

    React.useEffect(() => {
        if (nodes.length > 0) {
            setTimeout(() => fitView({ padding: 0.2, duration: 600 }), 100);
        }
    }, [nodes.length, fitView]);

    // Auto-follow running nodes
    React.useEffect(() => {
        if (userIntervened) return;

        const runningTask = tasks.find(t => t.status === 'in_progress');
        if (runningTask && runningTask.assigned_to !== selectedAgentId) {
            setSelectedAgent(runningTask.assigned_to);
        }
    }, [tasks, selectedAgentId, setSelectedAgent, userIntervened]);

    const onPaneClick = React.useCallback(() => {
        setUserIntervened(false);
        useSwarmStore.getState().setSelectedAgent(null);
    }, []);

    const onNodeClick = React.useCallback((_: React.MouseEvent, node: Node) => {
        setUserIntervened(true);
        const agentId = node.data.assigned_to;
        const currentSelected = useSwarmStore.getState().selectedAgentId;
        useSwarmStore.getState().setSelectedAgent(currentSelected === agentId ? null : agentId);
    }, []);

    if (tasks.length === 0) {
        return (
            <div className="w-full h-full flex flex-col items-center justify-center gap-4 text-muted-foreground">
                <Bot className="w-16 h-16 opacity-20" />
                <p className="text-sm opacity-50">No active swarm. Start a new run to see the DAG.</p>
            </div>
        );
    }

    return (
        <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={NODE_TYPES}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            onPaneClick={onPaneClick}
            onNodeClick={onNodeClick}
            className="bg-transparent"
            minZoom={0.2}
            maxZoom={2}
        >
            <Background color="#888" gap={20} size={1} className="opacity-20" />
            <Controls className="glass-panel border-border fill-white" />
        </ReactFlow>
    );
};

export const SwarmGraphView: React.FC = () => (
    <ReactFlowProvider>
        <div className="w-full h-full">
            <Inner />
        </div>
    </ReactFlowProvider>
);
