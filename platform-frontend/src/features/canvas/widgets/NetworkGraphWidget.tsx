import React, { useEffect, useRef } from 'react';
import { DataSet } from 'vis-data';
import { Network } from 'vis-network';
import { useTheme } from '@/components/theme';

interface GraphNode {
    id: string | number;
    label: string;
    group?: string;
    color?: string;
}

interface GraphEdge {
    from: string | number;
    to: string | number;
    label?: string;
    color?: string;
}

interface NetworkGraphWidgetProps {
    title?: string;
    nodes: GraphNode[];
    edges: GraphEdge[];
}

const NetworkGraphWidget: React.FC<NetworkGraphWidgetProps> = ({ title, nodes: nodeData = [], edges: edgeData = [] }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';
    const containerRef = useRef<HTMLDivElement>(null);
    const networkRef = useRef<Network | null>(null);

    useEffect(() => {
        if (!containerRef.current || nodeData.length === 0) return;

        const nodes = new DataSet(nodeData.map(n => ({
            id: n.id,
            label: n.label,
            group: n.group,
            color: n.color || (isDark ? '#3b82f6' : '#2563eb'),
            font: { color: isDark ? '#e5e7eb' : '#1f2937', size: 12 },
        })));

        const edges = new DataSet(edgeData.map(e => ({
            from: e.from,
            to: e.to,
            label: e.label,
            color: { color: e.color || (isDark ? '#4b5563' : '#d1d5db') },
            font: { color: isDark ? '#9ca3af' : '#6b7280', size: 10 },
        })));

        const options = {
            physics: { stabilization: { iterations: 100 }, barnesHut: { gravitationalConstant: -3000 } },
            interaction: { hover: true, tooltipDelay: 200 },
            nodes: {
                shape: 'dot',
                size: 16,
                borderWidth: 2,
                borderWidthSelected: 3,
                font: { face: 'system-ui' },
            },
            edges: {
                width: 1.5,
                smooth: { type: 'cubicBezier', forceDirection: 'horizontal' },
                arrows: { to: { enabled: true, scaleFactor: 0.5 } },
            },
        };

        networkRef.current = new Network(containerRef.current, { nodes, edges }, options);

        return () => { networkRef.current?.destroy(); };
    }, [nodeData, edgeData, isDark]);

    return (
        <div className={`w-full rounded-lg border overflow-hidden ${isDark ? 'bg-gray-800/50 border-gray-700' : 'bg-white border-gray-200 shadow-sm'}`}>
            {title && (
                <div className={`px-4 py-2 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                    <h3 className={`text-sm font-semibold ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{title}</h3>
                </div>
            )}
            <div ref={containerRef} className="h-80 w-full" />
        </div>
    );
};

export default NetworkGraphWidget;
