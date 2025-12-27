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

// Helper component to handle auto-fitting inside the ReactFlow context
const AutoFitter = ({ nodeCount }: { nodeCount: number }) => {
    const { fitView } = useReactFlow();

    React.useEffect(() => {
        if (nodeCount > 0) {
            const timer = setTimeout(() => {
                fitView({ padding: 0.2, duration: 800 });
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

    // Auto-follow running nodes
    React.useEffect(() => {
        const runningNode = nodes.find(n => n.data.status === 'running');
        if (runningNode && runningNode.id !== selectedNodeId) {
            selectNode(runningNode.id);
        }
    }, [nodes, selectedNodeId, selectNode]);

    const visibleNodes = nodes.filter(n => n.id !== 'ROOT');

    return (
        <div className="w-full h-full">
            <ReactFlow
                id="main-graph-flow"
                nodes={visibleNodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={(_: React.MouseEvent, node: Node) => useAppStore.getState().selectNode(node.id)}
                nodeTypes={NODE_TYPES}
                edgeTypes={EDGE_TYPES}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                className="bg-background"
                minZoom={0.2}
                maxZoom={2}
            >
                <Background color="#888" gap={20} size={1} className="opacity-20" />
                <Controls className="react-flow__controls--dark" />
                <AutoFitter nodeCount={visibleNodes.length} />
            </ReactFlow>
        </div>
    );
};
