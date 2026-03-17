import React from 'react';
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState,
} from 'reactflow';
import type { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { useTheme } from '@/components/theme';

interface FlowChartWidgetProps {
    title?: string;
    nodes: Node[];
    edges: Edge[];
    direction?: 'TB' | 'LR';
}

const FlowChartWidget: React.FC<FlowChartWidgetProps> = ({ title, nodes: initialNodes = [], edges: initialEdges = [] }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';
    const [nodes, , onNodesChange] = useNodesState(initialNodes);
    const [edges, , onEdgesChange] = useEdgesState(initialEdges);

    return (
        <div className={`w-full rounded-lg border overflow-hidden ${isDark ? 'bg-gray-800/50 border-gray-700' : 'bg-white border-gray-200 shadow-sm'}`}>
            {title && (
                <div className={`px-4 py-2 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                    <h3 className={`text-sm font-semibold ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{title}</h3>
                </div>
            )}
            <div className="h-80">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    fitView
                    proOptions={{ hideAttribution: true }}
                    className={isDark ? 'bg-gray-900' : 'bg-gray-50'}
                >
                    <Background color={isDark ? '#374151' : '#e5e7eb'} gap={16} />
                    <Controls className="!bg-background !border-border !shadow-lg" />
                    <MiniMap
                        nodeColor={isDark ? '#4b5563' : '#d1d5db'}
                        maskColor={isDark ? 'rgba(0,0,0,0.6)' : 'rgba(0,0,0,0.1)'}
                        className="!bg-background !border-border"
                    />
                </ReactFlow>
            </div>
        </div>
    );
};

export default FlowChartWidget;
