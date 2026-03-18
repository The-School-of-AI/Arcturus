import React, { useMemo, useState } from 'react';
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
import axios from 'axios';

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
    const [skeletonData, setSkeletonData] = useState<any[] | null>(null);

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
                <Controls className="bg-card border border-border border-border fill-white" />
                <div className="absolute top-4 right-4 z-50">
                    <button
                        onClick={async () => {
                            try {
                                const res = await axios.get(`${API_BASE}/optimizer/skeletons`, { timeout: 5000 });
                                setSkeletonData(res.data && res.data.length > 0 ? res.data : null);
                                if (!res.data || res.data.length === 0) {
                                    setSkeletonData([{ _empty: true, message: "No episodic skeletons found yet. Run some queries first." }]);
                                }
                            } catch {
                                setSkeletonData([{ _empty: true, message: "Backend unreachable." }]);
                            }
                        }}
                        className="bg-background/50 text-foreground/50 text-xs px-3 py-1.5 rounded-md border border-border/30 hover:bg-background/80 hover:text-foreground/80 transition-colors flex items-center gap-2"
                        title="View Skeletons"
                    >
                        <span>💀</span>
                    </button>
                </div>
                {/* Skeleton JSON overlay */}
                {skeletonData && (
                    <div className="absolute inset-0 z-[60] bg-background/80 backdrop-blur-sm flex items-center justify-center p-8">
                        <div className="relative w-full max-w-2xl max-h-[80vh] bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col">
                            <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
                                <span className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Episodic Skeletons</span>
                                <button onClick={() => setSkeletonData(null)} className="text-muted-foreground hover:text-foreground text-lg leading-none">&times;</button>
                            </div>
                            <pre className="flex-1 overflow-auto p-4 text-xs font-mono text-foreground/80 whitespace-pre-wrap">
                                {JSON.stringify(skeletonData, null, 2)}
                            </pre>
                        </div>
                    </div>
                )}
                <AutoFitter nodeCount={visibleNodes.length} />
            </ReactFlow>
        </div>
    );
};
