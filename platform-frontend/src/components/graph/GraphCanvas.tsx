import React, { useMemo } from 'react';
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState
} from 'reactflow';
import 'reactflow/dist/style.css';
import { mockNodes, mockEdges } from '@/lib/mockData';
import AgentNode from './AgentNode';
import CustomEdge from './CustomEdge';

export const GraphCanvas: React.FC = () => {
    // In real app, sync with store
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const [nodes, setNodes, onNodesChange] = useNodesState(mockNodes);
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const [edges, setEdges, onEdgesChange] = useEdgesState(mockEdges.map(e => ({ ...e, type: 'custom' })));

    const nodeTypes = useMemo(() => ({
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
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            className="bg-charcoal-900"
            minZoom={0.2}
            maxZoom={2}
        >
            <Background color="#333" gap={20} size={1} />
            <Controls className="bg-charcoal-800 border-border text-foreground" />
            <MiniMap
                className="bg-charcoal-800 border-border"
                maskColor="rgba(0,0,0,0.6)"
                nodeColor={(n) => {
                    if (n.type === 'agentNode') return '#F6FF4D';
                    return '#333';
                }}
            />
        </ReactFlow>
    );
};
