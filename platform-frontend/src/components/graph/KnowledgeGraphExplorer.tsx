import React, { useEffect, useRef, useState, useCallback } from 'react';
import { DataSet } from 'vis-data';
import { Network } from 'vis-network';
import { useAppStore } from '@/store';
import { api } from '@/lib/api';
import { Network as NetworkIcon, RefreshCw, ZoomIn, ZoomOut, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';

const LIMIT = 150;

/** Colors for entity types */
const ENTITY_TYPE_COLORS: Record<string, string> = {
    Person: '#3b82f6',
    Company: '#8b5cf6',
    City: '#f97316',
    Place: '#22c55e',
    Concept: '#ef4444',
    Date: '#eab308',
    Entity: '#6366f1',
};
const DEFAULT_ENTITY_COLOR = '#6366f1';
const USER_COLOR = '#0d9488';
const MEMORY_COLOR = '#64748b';

interface SelectedNodeInfo {
    id: string;
    label: string;
    type: string;
    nodeKind?: string;
    degree?: number;
    connections?: { relType: string; targetLabel: string; direction: 'in' | 'out' }[];
}

function SelectedNodePanel({ node }: { node: SelectedNodeInfo }) {
    const k = node.nodeKind || 'entity';
    return (
        <div className="p-3 border-t border-border/50 bg-muted/20 text-xs shrink-0 overflow-y-auto max-h-32">
            <div className="font-semibold text-foreground">{node.label}</div>
            <div className="text-muted-foreground mt-0.5">
                {k === 'entity' && (
                    <>
                        <span>Type: {node.type}</span>
                        {node.id && <span className="ml-2 opacity-70">ID: {String(node.id).slice(0, 12)}…</span>}
                    </>
                )}
                {k === 'user' && <span>Your profile — connections to known entities</span>}
                {k === 'memory' && (
                    <>
                        <span>Memory</span>
                        {node.id && <span className="ml-2 opacity-70">ID: {String(node.id).slice(0, 16)}…</span>}
                    </>
                )}
            </div>
            {node.degree !== undefined && node.degree > 0 && (
                <div className="mt-2 space-y-0.5">
                    <span className="text-muted-foreground">{node.degree} connection{node.degree !== 1 ? 's' : ''}</span>
                    {node.connections && node.connections.length > 0 && (
                        <ul className="mt-1 space-y-0.5 pl-3 list-disc">
                            {node.connections.map((c, i) => (
                                <li key={i} className="text-muted-foreground">
                                    <span className="text-foreground/80">{c.relType}</span>
                                    <span className="mx-1">{c.direction === 'out' ? '→' : '←'}</span>
                                    <span>{c.targetLabel}</span>
                                </li>
                            ))}
                            {node.degree > (node.connections?.length ?? 0) && (
                                <li className="text-muted-foreground/70">+{node.degree - (node.connections?.length ?? 0)} more</li>
                            )}
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
}

export const KnowledgeGraphExplorer: React.FC = () => {
    const containerRef = useRef<HTMLDivElement>(null);
    const networkRef = useRef<Network | null>(null);
    const nodesRef = useRef<DataSet<Record<string, unknown>>>(new DataSet<Record<string, unknown>>([]));
    const edgesRef = useRef<DataSet<Record<string, unknown>>>(new DataSet<Record<string, unknown>>([]));
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedNode, setSelectedNode] = useState<SelectedNodeInfo | null>(null);
    const spaces = useAppStore((s) => s.spaces);
    const currentSpaceId = useAppStore((s) => s.currentSpaceId);
    const setCurrentSpaceId = useAppStore((s) => s.setCurrentSpaceId);
    const fetchSpaces = useAppStore((s) => s.fetchSpaces);

    const nodeKind = (n: { nodeKind?: string }) => (n as { nodeKind?: string }).nodeKind ?? 'entity';
    const entityType = (n: { type?: string }) => String((n as { type?: string }).type || 'Entity').trim();
    const getNodeColor = (n: { nodeKind?: string; type?: string }) => {
        const k = nodeKind(n);
        if (k === 'user') return USER_COLOR;
        if (k === 'memory') return MEMORY_COLOR;
        const t = entityType(n);
        return ENTITY_TYPE_COLORS[t] ?? ENTITY_TYPE_COLORS[t.charAt(0).toUpperCase() + t.slice(1).toLowerCase()] ?? DEFAULT_ENTITY_COLOR;
    };

    const getNodeShape = (n: { nodeKind?: string }) => {
        const k = nodeKind(n);
        if (k === 'user') return 'diamond';
        if (k === 'memory') return 'box';
        return 'dot';
    };

    const fetchAndRender = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const { nodes, edges } = await api.getGraphExplore(
                currentSpaceId ?? undefined,
                LIMIT
            );
            if (!containerRef.current) return;

            const visNodes = nodes.map((n) => {
                const k = nodeKind(n);
                const color = getNodeColor(n);
                const size = k === 'user' ? 20 : k === 'memory' ? 14 : 16;
                return {
                    id: n.id,
                    label: n.label,
                    type: n.type,
                    nodeKind: k,
                    color: { background: color, border: color },
                    shape: getNodeShape(n),
                    size,
                    font: { color: '#111827', size: k === 'memory' ? 10 : 12 },
                };
            });

            const visEdges = edges.map((e, i) => {
                const t = (e.type && String(e.type).trim()) || '';
                const isContains = t === 'CONTAINS_ENTITY';
                return {
                    id: `e${i}`,
                    from: e.source,
                    to: e.target,
                    relType: t,
                    label: isContains ? '' : t,
                    arrows: isContains ? undefined : { to: { enabled: true } },
                    width: isContains ? 1 : 1.5,
                    color: { color: '#94a3b8' },
                    font: t ? { size: 11, color: '#64748b' } : undefined,
                };
            });

            nodesRef.current.clear();
            edgesRef.current.clear();
            nodesRef.current.add(visNodes);
            edgesRef.current.add(visEdges);

            if (!networkRef.current) {
                const network = new Network(
                    containerRef.current,
                    { nodes: nodesRef.current, edges: edgesRef.current },
                    {
                        physics: {
                            enabled: true,
                            barnesHut: {
                                gravitationalConstant: -3000,
                                springLength: 120,
                                springConstant: 0.04,
                            },
                        },
                        interaction: { hover: true, zoomView: true, dragView: true },
                        nodes: { borderWidth: 2 },
                    }
                );

                network.on('click', (params) => {
                    const nodeIds = params.nodes;
                    if (nodeIds.length === 0) {
                        setSelectedNode(null);
                        return;
                    }
                    const nodeId = nodeIds[0];
                    const node = nodesRef.current.get(nodeId) as unknown as { id: string; label: string; type?: string; nodeKind?: string } | undefined;
                    if (!node) return;

                    const allEdges = edgesRef.current.get() as unknown as { from: string; to: string; relType?: string }[];
                    const connectedEdges = allEdges.filter((e) => e.from === nodeId || e.to === nodeId);
                    const connections: { relType: string; targetLabel: string; direction: 'in' | 'out' }[] = [];
                    connectedEdges.forEach((edge: { from: string; to: string; relType?: string }) => {
                        const otherId = edge.from === nodeId ? edge.to : edge.from;
                        const other = nodesRef.current.get(otherId) as { label?: string } | undefined;
                        const direction = edge.to === nodeId ? ('in' as const) : ('out' as const);
                        connections.push({
                            relType: edge.relType || 'RELATED_TO',
                            targetLabel: other?.label ?? otherId,
                            direction,
                        });
                    });

                    setSelectedNode({
                        id: node.id,
                        label: node.label,
                        type: node.type ?? 'Entity',
                        nodeKind: node.nodeKind,
                        degree: connectedEdges.length,
                        connections: connections.slice(0, 12),
                    });
                });

                networkRef.current = network;
            }
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : 'Failed to load graph';
            setError(msg);
        } finally {
            setLoading(false);
        }
    }, [currentSpaceId]);

    useEffect(() => {
        fetchSpaces();
    }, [fetchSpaces]);

    useEffect(() => {
        fetchAndRender();
        return () => {
            networkRef.current?.destroy();
            networkRef.current = null;
        };
    }, [fetchAndRender]);

    const handleZoomIn = () => {
        const n = networkRef.current;
        if (!n) return;
        const scale = n.getScale();
        n.moveTo({ scale: Math.min(scale * 1.3, 3) });
    };
    const handleZoomOut = () => {
        const n = networkRef.current;
        if (!n) return;
        const scale = n.getScale();
        n.moveTo({ scale: Math.max(scale / 1.3, 0.3) });
    };
    const handleFit = () => networkRef.current?.fit();

    return (
        <div className="h-full flex flex-col bg-background">
            {/* Toolbar */}
            <div className="flex items-center justify-between gap-2 p-2 border-b border-border/50 bg-muted/20 shrink-0">
                <div className="flex items-center gap-2">
                    <Select value={currentSpaceId ?? '__global__'} onValueChange={(v) => setCurrentSpaceId(v === '__global__' ? null : v)}>
                        <SelectTrigger className="w-[180px] h-8 text-xs bg-background">
                            <SelectValue placeholder="Space" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="__global__">Global</SelectItem>
                            {spaces.map((s) => (
                                <SelectItem key={s.space_id} value={s.space_id}>
                                    {s.name || 'Unnamed'}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={fetchAndRender} disabled={loading}>
                        {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                        Refresh
                    </Button>
                </div>
                <div className="flex items-center gap-1">
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleZoomOut} title="Zoom out">
                        <ZoomOut className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleFit} title="Fit">
                        <NetworkIcon className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleZoomIn} title="Zoom in">
                        <ZoomIn className="w-4 h-4" />
                    </Button>
                </div>
            </div>

            {/* Graph canvas */}
            <div className="flex-1 min-h-0 relative">
                {loading && (
                    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-background/80">
                        <Loader2 className="w-12 h-12 animate-spin text-primary" />
                        <p className="mt-2 text-sm text-muted-foreground">Loading knowledge graph...</p>
                    </div>
                )}
                {error && (
                    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center p-8 text-center">
                        <AlertCircle className="w-12 h-12 text-destructive mb-2" />
                        <p className="text-sm text-destructive mb-4">{error}</p>
                        <Button variant="outline" size="sm" onClick={fetchAndRender}>
                            <RefreshCw className="w-4 h-4 mr-2" /> Retry
                        </Button>
                    </div>
                )}
                <div
                    ref={containerRef}
                    className={cn(
                        "w-full h-full min-h-[300px] rounded-lg",
                        (loading || error) && "opacity-30 pointer-events-none"
                    )}
                />
            </div>

            {selectedNode && <SelectedNodePanel node={selectedNode} />}
        </div>
    );
};
