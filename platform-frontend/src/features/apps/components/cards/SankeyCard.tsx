import React, { useMemo, useState } from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

// Multi-color palette for auto-color mode
const MULTI_COLOR_PALETTE = [
    '#eaff00', // Neon Yellow
    '#ff6b6b', // Coral Red
    '#4ecdc4', // Teal
    '#45b7d1', // Sky Blue
    '#96ceb4', // Sage Green
    '#ffeaa7', // Light Yellow
    '#dfe6e9', // Light Gray
    '#fd79a8', // Pink
    '#a29bfe', // Lavender
    '#00b894', // Mint
    '#e17055', // Burnt Orange
    '#74b9ff', // Soft Blue
];

interface SankeyNode {
    name: string;
    color?: string;
    value?: number;
    x?: number;
    y?: number;
    w?: number;
    h?: number;
    layer?: number;
}

interface SankeyLink {
    source: number;
    target: number;
    value: number;
    color?: string;
    y0?: number;
    y1?: number;
}

interface SankeyCardProps {
    title: string;
    data?: {
        nodes: SankeyNode[];
        links: SankeyLink[];
    };
    config?: any;
    style?: any;
}

// Default sample data
const DEFAULT_SANKEY_DATA = {
    nodes: [
        { name: 'Website' },
        { name: 'App' },
        { name: 'Social' },
        { name: 'Signup' },
        { name: 'Browse' },
        { name: 'Purchase' },
        { name: 'Churn' }
    ],
    links: [
        { source: 0, target: 3, value: 40 },
        { source: 0, target: 4, value: 30 },
        { source: 1, target: 3, value: 25 },
        { source: 1, target: 4, value: 20 },
        { source: 2, target: 3, value: 15 },
        { source: 3, target: 5, value: 50 },
        { source: 3, target: 6, value: 30 },
        { source: 4, target: 5, value: 35 },
        { source: 4, target: 6, value: 15 }
    ]
};

export const SankeyCard: React.FC<SankeyCardProps> = ({
    title,
    data,
    config = {},
    style = {}
}) => {
    const [tooltip, setTooltip] = useState<{ x: number; y: number; content: string; visible: boolean }>({ x: 0, y: 0, content: '', visible: false });

    // Config options
    const showLegend = config.showLegend !== false;
    const showGrid = config.showGrid === true;
    const showAxis = config.showAxisLabels !== false;
    const animate = config.animate !== false;
    const autoMultiColor = config.autoMultiColor !== false;

    // Style
    const accentColor = style.accentColor || '#eaff00';
    const textColor = style.textColor || '#ffffff';

    // Use default data if not provided or empty
    const inputData = (data?.nodes?.length && data?.links?.length) ? data : DEFAULT_SANKEY_DATA;

    // Simple Sankey Layout Engine
    const { nodes, links, cardWidth, cardHeight } = useMemo(() => {
        const nodes: SankeyNode[] = JSON.parse(JSON.stringify(inputData.nodes || []));
        const links: SankeyLink[] = JSON.parse(JSON.stringify(inputData.links || []));

        const cardWidth = 400;
        const cardHeight = 300;
        const nodeWidth = 14;
        const horizontalPadding = 2; // Near-zero padding on sides
        const topPadding = 0;

        if (nodes.length === 0) return { nodes: [], links: [], cardWidth, cardHeight };

        // Assign colors
        if (autoMultiColor) {
            nodes.forEach((n, i) => {
                if (!n.color) n.color = MULTI_COLOR_PALETTE[i % MULTI_COLOR_PALETTE.length];
            });
        } else {
            nodes.forEach(n => { if (!n.color) n.color = accentColor; });
        }

        // 1. Assign Layers
        nodes.forEach(n => n.layer = 0);
        let changed = true;
        let iter = 0;
        while (changed && iter < 10) {
            changed = false;
            links.forEach(l => {
                if (nodes[l.source] && nodes[l.target]) {
                    if ((nodes[l.target].layer || 0) <= (nodes[l.source].layer || 0)) {
                        nodes[l.target].layer = (nodes[l.source].layer || 0) + 1;
                        changed = true;
                    }
                }
            });
            iter++;
        }

        const maxLayer = Math.max(...nodes.map(n => n.layer || 0));

        // 2. Calculate Values
        nodes.forEach((n, idx) => {
            n.value = Math.max(1,
                Math.max(
                    links.filter(l => l.source === idx).reduce((sum, l) => sum + l.value, 0),
                    links.filter(l => l.target === idx).reduce((sum, l) => sum + l.value, 0)
                )
            );
        });

        const sourceOffsets = new Array(nodes.length).fill(0);
        const targetOffsets = new Array(nodes.length).fill(0);

        // 3. Assign X Positions - Use full width with minimal padding
        const usableWidth = cardWidth - (horizontalPadding * 2) - nodeWidth; // Subtract nodeWidth so last node fits
        const layerWidth = usableWidth / Math.max(1, maxLayer); // Distance between layer starts
        nodes.forEach(n => {
            n.x = horizontalPadding + ((n.layer || 0) * layerWidth);
            n.w = nodeWidth;
        });

        // 4. Assign Y Positions
        const layers: SankeyNode[][] = [];
        for (let i = 0; i <= maxLayer; i++) layers.push([]);
        nodes.forEach(n => layers[n.layer || 0].push(n));

        const usableHeight = cardHeight - topPadding;
        layers.forEach(layerNodes => {
            const totalValue = layerNodes.reduce((sum, n) => sum + (n.value || 0), 0);
            const gapCount = layerNodes.length - 1;
            const gapSize = 6;
            const availableForNodes = usableHeight - (gapCount * gapSize);
            const scale = availableForNodes / Math.max(totalValue, 1);


            let currentY = topPadding;
            layerNodes.forEach(n => {
                n.h = Math.max(8, (n.value || 0) * scale);
                n.y = currentY;
                currentY += n.h + gapSize;
            });
        });

        // 5. Calculate Link Coordinates
        links.forEach(l => {
            const source = nodes[l.source];
            const target = nodes[l.target];
            if (!source || !target) return;

            const sTotal = links.filter(link => link.source === l.source).reduce((s, link) => s + link.value, 0);
            const tTotal = links.filter(link => link.target === l.target).reduce((s, link) => s + link.value, 0);

            const sScale = source.h! / (sTotal || 1);
            const tScale = target.h! / (tTotal || 1);

            const sHeight = l.value * sScale;
            const tHeight = l.value * tScale;

            l.y0 = source.y! + sourceOffsets[l.source];
            l.y1 = target.y! + targetOffsets[l.target];

            sourceOffsets[l.source] += sHeight;
            targetOffsets[l.target] += tHeight;

            (l as any).thickness = (sHeight + tHeight) / 2;
            (l as any).sThickness = sHeight;
            (l as any).tThickness = tHeight;
            (l as any).sourceColor = source.color;
            (l as any).targetColor = target.color;
            (l as any).sourceName = source.name;
            (l as any).targetName = target.name;
        });

        return { nodes, links, cardWidth, cardHeight };
    }, [inputData, autoMultiColor, accentColor]);

    // Helper for Sankey Ribbon Path
    const getRibbonPath = (l: any) => {
        const sourceNode = nodes[l.source];
        const targetNode = nodes[l.target];
        if (!sourceNode || !targetNode) return '';

        const x0 = sourceNode.x! + sourceNode.w!;
        const x1 = targetNode.x!;
        const y0 = l.y0!;
        const y1 = l.y1!;
        const h0 = l.sThickness;
        const h1 = l.tThickness;

        const curvature = 0.5;
        function d3_interpolateNumber(a: number, b: number) { return (t: number) => a * (1 - t) + b * t; }
        const xi = d3_interpolateNumber(x0, x1);
        const x2 = xi(curvature);
        const x3 = xi(1 - curvature);

        return `M ${x0} ${y0} C ${x2} ${y0}, ${x3} ${y1}, ${x1} ${y1} L ${x1} ${y1 + h1} C ${x3} ${y1 + h1}, ${x2} ${y0 + h0}, ${x0} ${y0 + h0} Z`;
    };

    const showTooltip = (e: React.MouseEvent, content: string) => {
        const container = e.currentTarget.closest('.sankey-container') as HTMLElement;
        if (container) {
            const rect = container.getBoundingClientRect();
            setTooltip({
                x: e.clientX - rect.left,
                y: e.clientY - rect.top - 10,
                content,
                visible: true
            });
        }
    };

    const hideTooltip = () => setTooltip(prev => ({ ...prev, visible: false }));

    return (
        <BaseCard title={title}>
            <div className="w-full h-full flex flex-col relative p-2 sankey-container">
                {/* Tooltip */}
                {tooltip.visible && (
                    <div
                        className="absolute z-50 px-2 py-1.5 bg-black/95 text-foreground text-[10px] rounded border border-border shadow-xl pointer-events-none whitespace-nowrap"
                        style={{ left: tooltip.x, top: tooltip.y, transform: 'translate(-50%, -100%)' }}
                    >
                        {tooltip.content}
                    </div>
                )}

                <div className="flex-1 relative overflow-hidden">
                    {showGrid && (
                        <div className="absolute inset-0 opacity-10 pointer-events-none">
                            <div className="w-full h-full" style={{
                                backgroundImage: 'linear-gradient(to right, rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.1) 1px, transparent 1px)',
                                backgroundSize: '40px 40px'
                            }} />
                        </div>
                    )}

                    <svg
                        className={cn("w-full h-full", animate && "animate-in fade-in duration-700")}
                        viewBox={`0 0 ${cardWidth} ${cardHeight}`}
                        preserveAspectRatio="xMidYMid meet"
                    >
                        <defs>
                            {links.map((l: any, i) => (
                                <linearGradient key={`grad-${i}`} id={`link-grad-${i}`} gradientUnits="userSpaceOnUse" x1={nodes[l.source]?.x} x2={nodes[l.target]?.x}>
                                    <stop offset="0%" stopColor={l.sourceColor || accentColor} stopOpacity="0.6" />
                                    <stop offset="100%" stopColor={l.targetColor || accentColor} stopOpacity="0.4" />
                                </linearGradient>
                            ))}
                        </defs>

                        {/* Links with tooltips */}
                        {links.map((l: any, i) => (
                            <path
                                key={`link-${i}`}
                                d={getRibbonPath(l)}
                                fill={autoMultiColor ? `url(#link-grad-${i})` : (l.color || accentColor)}
                                className={cn("opacity-60 hover:opacity-90 transition-opacity duration-300 cursor-crosshair", !autoMultiColor && "opacity-40")}
                                onMouseEnter={(e) => showTooltip(e as any, `${l.sourceName} → ${l.targetName}: ${l.value}`)}
                                onMouseMove={(e) => showTooltip(e as any, `${l.sourceName} → ${l.targetName}: ${l.value}`)}
                                onMouseLeave={hideTooltip}
                            />
                        ))}

                        {/* Nodes with tooltips */}
                        {nodes.map((n, i) => (
                            <g key={`node-${i}`} className="group">
                                <rect
                                    x={n.x}
                                    y={n.y}
                                    width={n.w}
                                    height={n.h}
                                    fill={n.color || accentColor}
                                    rx={2}
                                    className="hover:brightness-125 transition-all cursor-crosshair"
                                    style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.3))' }}
                                    onMouseEnter={(e) => showTooltip(e as any, `${n.name}: ${n.value}`)}
                                    onMouseMove={(e) => showTooltip(e as any, `${n.name}: ${n.value}`)}
                                    onMouseLeave={hideTooltip}
                                />
                                {showAxis && (
                                    <text
                                        x={n.x! + (n.layer === 0 ? n.w! + 6 : -6)}
                                        y={n.y! + n.h! / 2}
                                        dy="0.35em"
                                        textAnchor={n.layer === 0 ? "start" : "end"}
                                        className="text-[9px] font-semibold pointer-events-none uppercase tracking-wide"
                                        fill={textColor}
                                        style={{ textShadow: '0 1px 3px rgba(0,0,0,0.9)' }}
                                    >
                                        {n.name}
                                    </text>
                                )}
                            </g>
                        ))}
                    </svg>
                </div>

                {showLegend && nodes.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-1 justify-center border-t border-border/50 pt-2">
                        {nodes.map((n, i) => (
                            <div key={i} className="flex items-center gap-1.5">
                                <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: n.color || accentColor }} />
                                <span className="text-[9px] text-muted-foreground font-medium">{n.name}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
