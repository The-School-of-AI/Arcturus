import React, { useMemo } from 'react';
import ReactFlow, {
    Background,
    Controls,
    useNodesState,
    useEdgesState
} from 'reactflow';
import 'reactflow/dist/style.css';
import AgentNode from './AgentNode';
import CustomEdge from './CustomEdge';
import { useAppStore } from '@/store';

export const GraphCanvas: React.FC = () => {
    // Connect to Store
    const { nodes, edges, onNodesChange, onEdgesChange, selectNode, selectedNodeId } = useAppStore();

    // Auto-follow running nodes
    React.useEffect(() => {
        const runningNode = nodes.find(n => n.data.status === 'running');
        // Only switch if we aren't already looking at it, and maybe ONLY if the current selection is completed or null?
        // User asked: "agent nodes should be automatically be selected"
        if (runningNode && runningNode.id !== selectedNodeId) {
            selectNode(runningNode.id);
        }
    }, [nodes, selectedNodeId, selectNode]);

    const nodeTypes = React.useMemo(() => ({
        agentNode: AgentNode,
    }), []);

    const edgeTypes = useMemo(() => ({
        custom: CustomEdge,
    }), []);

    return (
        <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={(_, node) => useAppStore.getState().selectNode(node.id)}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            className="bg-charcoal-900"
            minZoom={0.2}
            maxZoom={2}
        >
            <Background color="#333" gap={20} size={1} />
            <Controls className="react-flow__controls--dark" />
        </ReactFlow>
    );
};
