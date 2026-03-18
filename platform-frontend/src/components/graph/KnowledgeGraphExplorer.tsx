import React, { useEffect, useRef, useState, useCallback } from 'react';
import { DataSet } from 'vis-data';
import { Network } from 'vis-network';
import { useAppStore } from '@/store';
import { api } from '@/lib/api';
import { useTheme } from '@/components/theme';
import { RefreshCw, ZoomIn, ZoomOut, Maximize2, Loader2, AlertCircle, DatabaseZap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';

const LIMIT = 200;

/* ── Color palette (works on both light and dark) ─────────────── */
const ENTITY_COLORS: Record<string, { bg: string; border: string }> = {
    Person:       { bg: '#3b82f6', border: '#2563eb' },
    Company:      { bg: '#8b5cf6', border: '#7c3aed' },
    Organization: { bg: '#8b5cf6', border: '#7c3aed' },
    City:         { bg: '#f59e0b', border: '#d97706' },
    Location:     { bg: '#f59e0b', border: '#d97706' },
    Place:        { bg: '#10b981', border: '#059669' },
    Concept:      { bg: '#ef4444', border: '#dc2626' },
    Technology:   { bg: '#06b6d4', border: '#0891b2' },
    Product:      { bg: '#ec4899', border: '#db2777' },
    Event:        { bg: '#f97316', border: '#ea580c' },
    Date:         { bg: '#eab308', border: '#ca8a04' },
    Entity:       { bg: '#6366f1', border: '#4f46e5' },
};
const DEFAULT_COLORS = { bg: '#6366f1', border: '#4f46e5' };
const USER_COLORS = { bg: '#0d9488', border: '#0f766e' };
const MEMORY_COLORS_DARK = { bg: '#1e293b', border: '#334155' };
const MEMORY_COLORS_LIGHT = { bg: '#e2e8f0', border: '#cbd5e1' };

/* ── Theme-dependent colors ───────────────────────────────────── */
function themeColors(isDark: boolean) {
    return {
        canvasBg: isDark ? '#0f1219' : '#f8fafc',
        toolbarBg: isDark ? '#161b26' : '#ffffff',
        toolbarBorder: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.08)',
        nodeFont: isDark ? '#e2e8f0' : '#1e293b',
        nodeFontStroke: isDark ? '#0f172a' : '#ffffff',
        edgeColor: isDark ? '#475569' : '#94a3b8',
        edgeHighlight: '#3b82f6',
        edgeHover: isDark ? '#60a5fa' : '#3b82f6',
        shadowAlpha: isDark ? '40' : '30',
    };
}

/* ── Edge label formatting ────────────────────────────────────── */
function formatEdgeLabel(raw: string): string {
    if (!raw || raw === 'CONTAINS_ENTITY' || raw === 'HAS_MEMORY') return '';
    return raw
        .split('_')
        .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
        .join(' ');
}

/* ── Types ────────────────────────────────────────────────────── */
interface SelectedNodeInfo {
    id: string;
    label: string;
    type: string;
    nodeKind?: string;
    degree?: number;
    connections?: { relType: string; targetLabel: string; direction: 'in' | 'out' }[];
}

/* ── Selected-node detail panel ───────────────────────────────── */
function SelectedNodePanel({ node, onClose }: { node: SelectedNodeInfo; onClose: () => void }) {
    const k = node.nodeKind || 'entity';
    const colors = k === 'user' ? USER_COLORS : (ENTITY_COLORS[node.type] ?? DEFAULT_COLORS);

    return (
        <div className="absolute bottom-3 left-3 z-20 w-72 rounded-xl border border-border/60 bg-background/95 shadow-xl overflow-hidden">
            <div className="flex items-center gap-2.5 px-3.5 py-2.5 border-b border-border/40">
                <div
                    className="w-3 h-3 rounded-full shrink-0"
                    style={{ backgroundColor: colors.bg, boxShadow: `0 0 6px ${colors.bg}80` }}
                />
                <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm text-foreground truncate">{node.label}</div>
                    <div className="text-xs text-muted-foreground">
                        {k === 'entity' && node.type}
                        {k === 'user' && 'Your profile'}
                        {node.degree !== undefined && <span className="ml-1.5">&middot; {node.degree} connections</span>}
                    </div>
                </div>
                <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-xs px-1">&times;</button>
            </div>
            {node.connections && node.connections.length > 0 && (
                <div className="px-3.5 py-2 max-h-36 overflow-y-auto space-y-1">
                    {node.connections.map((c, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-[11px]">
                            <span className="text-muted-foreground shrink-0">{c.direction === 'out' ? '\u2192' : '\u2190'}</span>
                            <span className="text-foreground/70 shrink-0">{formatEdgeLabel(c.relType) || c.relType}</span>
                            <span className="text-foreground truncate">{c.targetLabel}</span>
                        </div>
                    ))}
                    {(node.degree ?? 0) > (node.connections?.length ?? 0) && (
                        <div className="text-xs text-muted-foreground/60">
                            +{(node.degree ?? 0) - (node.connections?.length ?? 0)} more
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

/* ── Legend overlay ────────────────────────────────────────────── */
function Legend({ types }: { types: string[] }) {
    if (types.length === 0) return null;
    const items = types.map((t) => ({ label: t, color: (ENTITY_COLORS[t] ?? DEFAULT_COLORS).bg }));
    items.unshift({ label: 'You', color: USER_COLORS.bg });

    return (
        <div className="absolute top-3 right-3 z-20 flex flex-wrap gap-x-3 gap-y-1 px-3 py-2 rounded-lg bg-background/80 backdrop-blur-sm border border-border/40 shadow-sm">
            {items.map((it) => (
                <div key={it.label} className="flex items-center gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: it.color }} />
                    <span className="text-xs text-muted-foreground">{it.label}</span>
                </div>
            ))}
        </div>
    );
}

/* ── Stats badge ──────────────────────────────────────────────── */
function StatsBadge({ nodeCount, edgeCount }: { nodeCount: number; edgeCount: number }) {
    return (
        <div className="absolute bottom-3 right-3 z-20 px-2.5 py-1 rounded-md bg-background/70 backdrop-blur-sm border border-border/30 text-xs text-muted-foreground">
            {nodeCount} nodes &middot; {edgeCount} edges
        </div>
    );
}

/* ── Main component ───────────────────────────────────────────── */
export const KnowledgeGraphExplorer: React.FC = () => {
    const containerRef = useRef<HTMLDivElement>(null);
    const networkRef = useRef<Network | null>(null);
    const nodesRef = useRef<DataSet<Record<string, unknown>>>(new DataSet<Record<string, unknown>>([]));
    const edgesRef = useRef<DataSet<Record<string, unknown>>>(new DataSet<Record<string, unknown>>([]));
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedNode, setSelectedNode] = useState<SelectedNodeInfo | null>(null);
    const [migrating, setMigrating] = useState(false);
    const [migrateResult, setMigrateResult] = useState<string | null>(null);
    const [isEmpty, setIsEmpty] = useState(false);
    const [entityTypes, setEntityTypes] = useState<string[]>([]);
    const [counts, setCounts] = useState({ nodes: 0, edges: 0 });
    const spaces = useAppStore((s) => s.spaces);
    const currentSpaceId = useAppStore((s) => s.currentSpaceId);
    const setCurrentSpaceId = useAppStore((s) => s.setCurrentSpaceId);
    const fetchSpaces = useAppStore((s) => s.fetchSpaces);
    const { theme } = useTheme();
    const isDark = theme === 'dark';
    const tc = themeColors(isDark);

    /* ── Node helpers ─────────────────────────────────────────── */
    const nodeKind = (n: { nodeKind?: string }) => n.nodeKind ?? 'entity';
    const entityType = (n: { type?: string }) => String(n.type || 'Entity').trim();

    const getNodeColors = (n: { nodeKind?: string; type?: string }) => {
        const k = nodeKind(n);
        if (k === 'user') return USER_COLORS;
        const t = entityType(n);
        return ENTITY_COLORS[t] ?? ENTITY_COLORS[t.charAt(0).toUpperCase() + t.slice(1).toLowerCase()] ?? DEFAULT_COLORS;
    };

    /* ── Fetch & render ───────────────────────────────────────── */
    const fetchAndRender = useCallback(async () => {
        setLoading(true);
        setError(null);
        setSelectedNode(null);
        try {
            const { nodes, edges } = await api.getGraphExplore(
                currentSpaceId ?? undefined,
                LIMIT,
            );
            if (!containerRef.current) return;

            // Keep all nodes — memories act as invisible connectors between entities
            const entityNodes = nodes.filter((n) => (n.nodeKind ?? 'entity') !== 'user' && (n.nodeKind ?? 'entity') !== 'memory');
            setIsEmpty(entityNodes.length === 0);

            // Collect unique entity types for the legend
            const typeSet = new Set<string>();
            nodes.forEach((n) => {
                if ((n.nodeKind ?? 'entity') === 'entity') typeSet.add(entityType(n));
            });
            setEntityTypes(Array.from(typeSet).sort());

            // Compute degree per node for sizing (entity/user nodes only)
            const degree: Record<string, number> = {};
            edges.forEach((e) => {
                degree[e.source] = (degree[e.source] || 0) + 1;
                degree[e.target] = (degree[e.target] || 0) + 1;
            });
            const maxDeg = Math.max(1, ...Object.values(degree));

            const visNodes = nodes.map((n) => {
                const k = nodeKind(n);
                const isMem = k === 'memory';
                const isUser = k === 'user';
                const colors = getNodeColors(n);
                const deg = degree[n.id] || 0;

                // Memory nodes: small muted boxes — act as connectors between entities
                if (isMem) {
                    const mc = isDark ? MEMORY_COLORS_DARK : MEMORY_COLORS_LIGHT;
                    const memLabel = n.label && n.label.length > 20
                        ? n.label.slice(0, 20) + '...'
                        : (n.label || String(n.id).slice(0, 10));
                    return {
                        id: n.id,
                        label: memLabel,
                        type: n.type,
                        nodeKind: k,
                        shape: 'box' as const,
                        size: 8,
                        color: {
                            background: mc.bg,
                            border: mc.border,
                            highlight: { background: mc.bg, border: tc.edgeHighlight },
                            hover: { background: mc.bg, border: tc.edgeHover },
                        },
                        borderWidth: 1,
                        borderWidthSelected: 2,
                        font: {
                            color: isDark ? '#64748b' : '#94a3b8',
                            size: 8,
                            face: 'Inter, system-ui, sans-serif',
                        },
                        shadow: { enabled: false },
                        margin: { top: 4, bottom: 4, left: 6, right: 6 },
                    };
                }

                // Scale: user=30, entities 14–28 by degree
                const baseSize = isUser ? 30 : 14 + 14 * (deg / maxDeg);
                const fontSize = isUser ? 14 : Math.max(11, 11 + 3 * (deg / maxDeg));

                return {
                    id: n.id,
                    label: n.label,
                    type: n.type,
                    nodeKind: k,
                    shape: isUser ? 'diamond' : 'dot',
                    size: baseSize,
                    color: {
                        background: colors.bg,
                        border: colors.border,
                        highlight: { background: colors.bg, border: isDark ? '#ffffff' : colors.border },
                        hover: { background: colors.bg, border: isDark ? '#e2e8f0' : colors.border },
                    },
                    borderWidth: isUser ? 3 : 2,
                    borderWidthSelected: 3,
                    font: {
                        color: tc.nodeFont,
                        size: fontSize,
                        face: 'Inter, system-ui, sans-serif',
                        strokeWidth: 3,
                        strokeColor: tc.nodeFontStroke,
                    },
                    shadow: {
                        enabled: true,
                        color: colors.bg + tc.shadowAlpha,
                        size: isUser ? 16 : 10,
                        x: 0,
                        y: 2,
                    },
                };
            });

            // Build set of memory node IDs for edge styling
            const memoryIds = new Set(
                nodes.filter((n) => (n.nodeKind ?? 'entity') === 'memory').map((n) => n.id),
            );

            const visEdges = edges.map((e, i) => {
                const t = (e.type && String(e.type).trim()) || '';
                const label = formatEdgeLabel(t);
                const isStructural = memoryIds.has(e.source) || memoryIds.has(e.target);
                return {
                    id: `e${i}`,
                    from: e.source,
                    to: e.target,
                    relType: t,
                    label: isStructural ? '' : label,
                    title: label || t,
                    arrows: isStructural
                        ? { to: { enabled: false } }
                        : { to: { enabled: true, scaleFactor: 0.5, type: 'arrow' } },
                    width: isStructural ? 0.6 : 1.2,
                    color: {
                        color: isStructural ? (isDark ? '#334155' : '#cbd5e1') : tc.edgeColor,
                        highlight: tc.edgeHighlight,
                        hover: tc.edgeHover,
                        opacity: isStructural ? 0.5 : 0.8,
                    },
                    smooth: { enabled: true, type: 'continuous', roundness: 0.2 },
                    font: isStructural ? { size: 0 } : {
                        size: 9,
                        color: isDark ? '#64748b' : '#94a3b8',
                        strokeWidth: 2,
                        strokeColor: tc.canvasBg,
                        align: 'middle' as const,
                    },
                    dashes: isStructural ? [3, 3] : false,
                    hoverWidth: 0.5,
                    selectionWidth: 1,
                };
            });

            setCounts({ nodes: visNodes.length, edges: visEdges.length });
            nodesRef.current.clear();
            edgesRef.current.clear();
            nodesRef.current.add(visNodes);
            edgesRef.current.add(visEdges);

            // Destroy old network (handles space changes + theme changes)
            if (networkRef.current) {
                networkRef.current.destroy();
                networkRef.current = null;
            }

            const network = new Network(
                containerRef.current,
                { nodes: nodesRef.current, edges: edgesRef.current },
                {
                    physics: {
                        enabled: true,
                        barnesHut: {
                            gravitationalConstant: -5000,
                            centralGravity: 0.3,
                            springLength: 180,
                            springConstant: 0.018,
                            damping: 0.15,
                            avoidOverlap: 0.5,
                        },
                        stabilization: {
                            enabled: true,
                            iterations: 250,
                            fit: true,
                        },
                        maxVelocity: 25,
                        minVelocity: 0.5,
                    },
                    interaction: {
                        hover: true,
                        tooltipDelay: 200,
                        zoomView: true,
                        zoomSpeed: 0.3,
                        dragView: true,
                        multiselect: false,
                        navigationButtons: false,
                    },
                    nodes: {
                        borderWidth: 2,
                        borderWidthSelected: 3,
                    },
                    edges: {
                        // defaults
                    },
                },
            );

            network.on('click', (params) => {
                const nodeIds = params.nodes;
                if (nodeIds.length === 0) {
                    setSelectedNode(null);
                    return;
                }
                const nodeId = nodeIds[0];
                const node = nodesRef.current.get(nodeId) as unknown as {
                    id: string; label: string; type?: string; nodeKind?: string;
                } | undefined;
                if (!node) return;

                const allEdges = edgesRef.current.get() as unknown as {
                    from: string; to: string; relType?: string;
                }[];
                const connectedEdges = allEdges.filter(
                    (e) => e.from === nodeId || e.to === nodeId,
                );
                const connections: { relType: string; targetLabel: string; direction: 'in' | 'out' }[] = [];
                connectedEdges.forEach((edge) => {
                    const otherId = edge.from === nodeId ? edge.to : edge.from;
                    const other = nodesRef.current.get(otherId) as { label?: string } | undefined;
                    connections.push({
                        relType: edge.relType || 'RELATED_TO',
                        targetLabel: other?.label ?? String(otherId).slice(0, 12),
                        direction: edge.to === nodeId ? 'in' : 'out',
                    });
                });

                setSelectedNode({
                    id: node.id,
                    label: node.label,
                    type: node.type ?? 'Entity',
                    nodeKind: node.nodeKind,
                    degree: connectedEdges.length,
                    connections: connections.slice(0, 15),
                });
            });

            // After stabilization, disable physics for smooth manual dragging
            network.on('stabilizationIterationsDone', () => {
                network.setOptions({ physics: { enabled: false } });
            });

            networkRef.current = network;
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : 'Failed to load graph';
            setError(msg);
        } finally {
            setLoading(false);
        }
    }, [currentSpaceId, isDark]);

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

    /* ── Zoom controls ────────────────────────────────────────── */
    const handleZoomIn = () => {
        const n = networkRef.current;
        if (!n) return;
        n.moveTo({ scale: Math.min(n.getScale() * 1.3, 4), animation: { duration: 200, easingFunction: 'easeInOutQuad' } });
    };
    const handleZoomOut = () => {
        const n = networkRef.current;
        if (!n) return;
        n.moveTo({ scale: Math.max(n.getScale() / 1.3, 0.2), animation: { duration: 200, easingFunction: 'easeInOutQuad' } });
    };
    const handleFit = () => {
        networkRef.current?.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
    };

    /* ── Migrate ──────────────────────────────────────────────── */
    const handleMigrate = async () => {
        setMigrating(true);
        setMigrateResult(null);
        try {
            const result = await api.migrateGraphMemories();
            if (result.status === 'ok') {
                setMigrateResult(
                    `Migrated ${result.migrated} of ${result.total} memories (${result.skipped} skipped, ${result.errors} errors)`,
                );
                setTimeout(() => fetchAndRender(), 500);
            } else {
                setMigrateResult(result.message || 'Migration failed');
            }
        } catch (err: unknown) {
            setMigrateResult(err instanceof Error ? err.message : 'Migration failed');
        } finally {
            setMigrating(false);
        }
    };

    /* ── Render ────────────────────────────────────────────────── */
    return (
        <div className="h-full flex flex-col" style={{ background: tc.canvasBg }}>
            {/* Toolbar */}
            <div
                className="flex items-center justify-between gap-2 px-3 py-2 shrink-0"
                style={{ background: tc.toolbarBg, borderBottom: `1px solid ${tc.toolbarBorder}` }}
            >
                <div className="flex items-center gap-2">
                    <Select
                        value={currentSpaceId ?? '__global__'}
                        onValueChange={(v) => setCurrentSpaceId(v === '__global__' ? null : v)}
                    >
                        <SelectTrigger className="w-[160px] h-7 text-xs">
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
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 gap-1.5 text-xs"
                        onClick={fetchAndRender}
                        disabled={loading}
                    >
                        {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                        Refresh
                    </Button>
                </div>
                <div className="flex items-center gap-0.5">
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleZoomOut} title="Zoom out">
                        <ZoomOut className="w-3.5 h-3.5" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleFit} title="Fit to view">
                        <Maximize2 className="w-3.5 h-3.5" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleZoomIn} title="Zoom in">
                        <ZoomIn className="w-3.5 h-3.5" />
                    </Button>
                </div>
            </div>

            {/* Graph canvas */}
            <div className="flex-1 min-h-0 relative">
                {loading && (
                    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center" style={{ background: tc.canvasBg + 'e6' }}>
                        <Loader2 className="w-10 h-10 animate-spin text-primary" />
                        <p className="mt-3 text-sm text-muted-foreground">Loading knowledge graph...</p>
                    </div>
                )}
                {error && (
                    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center p-8 text-center">
                        <AlertCircle className="w-10 h-10 text-destructive mb-2" />
                        <p className="text-sm text-destructive mb-4">{error}</p>
                        <Button variant="outline" size="sm" onClick={fetchAndRender}>
                            <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Retry
                        </Button>
                    </div>
                )}
                {isEmpty && !loading && !error && (
                    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center p-8 text-center">
                        <DatabaseZap className="w-10 h-10 text-muted-foreground mb-3" />
                        <p className="text-sm text-muted-foreground mb-1">No entities in the graph yet.</p>
                        <p className="text-xs text-muted-foreground/70 mb-4">
                            Populate from your existing RemMe memories.
                        </p>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleMigrate}
                            disabled={migrating}
                            className="gap-2"
                        >
                            {migrating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <DatabaseZap className="w-3.5 h-3.5" />}
                            {migrating ? 'Extracting entities...' : 'Populate Graph from Memories'}
                        </Button>
                        {migrateResult && (
                            <p className="text-xs text-muted-foreground mt-3">{migrateResult}</p>
                        )}
                    </div>
                )}

                {/* vis.js container */}
                <div
                    ref={containerRef}
                    className={cn(
                        'w-full h-full',
                        (loading || error) && 'opacity-20 pointer-events-none',
                    )}
                    style={{ background: tc.canvasBg }}
                />

                {/* Overlays */}
                {!isEmpty && !loading && !error && <Legend types={entityTypes} />}
                {!isEmpty && !loading && !error && <StatsBadge nodeCount={counts.nodes} edgeCount={counts.edges} />}
                {selectedNode && (
                    <SelectedNodePanel node={selectedNode} onClose={() => setSelectedNode(null)} />
                )}
            </div>
        </div>
    );
};
