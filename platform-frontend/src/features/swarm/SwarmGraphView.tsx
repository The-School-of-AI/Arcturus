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
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Bot } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSwarmStore } from './useSwarmStore';
import type { SwarmTask } from './types';

// ------------------------------- Custom Node --------------------------------

const statusConfig = {
    pending: { border: 'border-border', dot: 'bg-muted-foreground', label: 'text-muted-foreground' },
    in_progress: { border: 'border-primary/60', dot: 'bg-primary animate-pulse', label: 'text-primary' },
    completed: { border: 'border-green-500/40', dot: 'bg-green-400', label: 'text-green-400' },
    failed: { border: 'border-red-500/40', dot: 'bg-red-400', label: 'text-red-400' },
} as const;

const SwarmTaskNode = ({ data, selected }: { data: SwarmTask; selected: boolean }) => {
    const cfg = statusConfig[data.status] ?? statusConfig.pending;
    const setSelectedAgent = useSwarmStore(s => s.setSelectedAgent);
    const selectedAgentId = useSwarmStore(s => s.selectedAgentId);
    const isSelected = selected || selectedAgentId === data.assigned_to;

    return (
        <div
            className={cn(
                'w-[200px] rounded-xl border-2 bg-card/90 backdrop-blur-sm px-3 py-2.5 cursor-pointer transition-all duration-200',
                cfg.border,
                isSelected && 'ring-2 ring-primary/40 shadow-lg shadow-primary/10',
            )}
            onClick={() => setSelectedAgent(
                selectedAgentId === data.assigned_to ? null : data.assigned_to
            )}
        >
            {/* Role label */}
            <div className="flex items-center gap-1.5 mb-1">
                <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', cfg.dot)} />
                <span className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground truncate">
                    {data.assigned_to}
                </span>
            </div>
            {/* Task title */}
            <p className={cn('text-xs font-medium leading-snug', cfg.label)}>
                {data.title}
            </p>
            {/* In-progress bar */}
            {data.status === 'in_progress' && (
                <div className="mt-2 h-0.5 w-full rounded-full bg-primary/20">
                    <div className="h-0.5 rounded-full bg-primary animate-pulse w-1/2" />
                </div>
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
        task.dependencies.map(dep => ({
            id: `${dep}->${task.task_id}`,
            source: dep,
            target: task.task_id,
            type: 'smoothstep',
            animated: task.status === 'in_progress',
            style: { stroke: task.status === 'in_progress' ? 'hsl(var(--primary))' : 'hsl(var(--border))' },
        }))
    );

    return { nodes, edges };
}

// ------------------------------ Inner graph --------------------------------

const Inner: React.FC = () => {
    const tasks = useSwarmStore(s => s.tasks);
    const { nodes, edges } = useMemo(() => buildFlow(tasks), [tasks]);
    const { fitView } = useReactFlow();

    React.useEffect(() => {
        if (nodes.length > 0) {
            setTimeout(() => fitView({ padding: 0.2, duration: 600 }), 100);
        }
    }, [nodes.length, fitView]);

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
