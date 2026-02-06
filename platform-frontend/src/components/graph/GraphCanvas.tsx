import React, { useMemo } from 'react';
import ReactFlow, {
    Controls,
    Background,
    useReactFlow,
    type Node
} from 'reactflow';
import 'reactflow/dist/style.css';
import AgentNode from './AgentNode';
import CustomEdge from './CustomEdge';
import { useAppStore } from '@/store';
import { API_BASE } from '@/lib/api';

// Helper component to handle auto-fitting inside the ReactFlow context
const AutoFitter = ({ nodeCount }: { nodeCount: number }) => {
    const { fitView } = useReactFlow();

    React.useEffect(() => {
        if (nodeCount > 0) {
            const timer = setTimeout(() => {
                fitView({ padding: 0.2, duration: 800, maxZoom: 1.0 });
            }, 100);
            return () => clearTimeout(timer);
        }
    }, [nodeCount, fitView]);

    return null;
};

const NODE_TYPES = {
    agentNode: AgentNode,
    module: AgentNode,
    ui: AgentNode,
    data: AgentNode,
    utility: AgentNode,
};

const EDGE_TYPES = {
    custom: CustomEdge,
};

export const GraphCanvas: React.FC = () => {
    // Connect to Store
    const { nodes, edges, onNodesChange, onEdgesChange, selectNode, selectedNodeId } = useAppStore();

    const nodeTypes = useMemo(() => NODE_TYPES, []);
    const edgeTypes = useMemo(() => EDGE_TYPES, []);

    const [userIntervened, setUserIntervened] = React.useState(false);

    // Auto-follow running nodes
    React.useEffect(() => {
        // If the user has manually selected something, don't jump unless they explicitly clear it 
        // Or if the selection is the ROOT node (default start)
        if (userIntervened && selectedNodeId && selectedNodeId !== 'ROOT') {
            return;
        }

        const runningNode = nodes.find(n => n.data.status === 'running');
        if (runningNode && runningNode.id !== selectedNodeId) {
            selectNode(runningNode.id);
        }
    }, [nodes, selectedNodeId, selectNode, userIntervened]);

    // Reset intervention when click on canvas (empty space)
    const onPaneClick = React.useCallback(() => {
        setUserIntervened(false);
        selectNode(null);
    }, [selectNode]);

    const onNodeClick = React.useCallback((_: React.MouseEvent, node: Node) => {
        setUserIntervened(true);
        selectNode(node.id);
    }, [selectNode]);

    const visibleNodes = nodes.filter(n => n.id !== 'ROOT');

    return (
        <div className="w-full h-full">
            <ReactFlow
                id="main-graph-flow"
                nodes={visibleNodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                onPaneClick={onPaneClick}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                className="bg-transparent"
                minZoom={0.2}
                maxZoom={2}
            >
                <Background color="#888" gap={20} size={1} className="opacity-20" />
                <Controls className="glass-panel border-border fill-white" />
                <div className="absolute top-4 right-4 z-50">
                    <button
                        onClick={() => window.open(`${API_BASE}/optimizer/skeletons`, '_blank')}
                        className="bg-black/80 text-white text-xs px-3 py-1.5 rounded-md border border-white/10 hover:bg-black transition-colors flex items-center gap-2"
                    >
                        <span>💀</span>
                        {/* View Skeleton */}
                    </button>
                </div>
                <AutoFitter nodeCount={visibleNodes.length} />
            </ReactFlow>
        </div>
    );
};
