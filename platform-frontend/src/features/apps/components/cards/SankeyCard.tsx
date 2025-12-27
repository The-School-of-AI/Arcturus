import React, { useMemo } from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

interface SankeyNode {
    name: string;
    color?: string;
    value?: number; // Calculated
    x?: number;
    y?: number;
    w?: number;
    h?: number;
    layer?: number;
}

interface SankeyLink {
    source: number; // Index in nodes array
    target: number; // Index in nodes array
    value: number;
    color?: string;
    y0?: number; // Source Y offset
    y1?: number; // Target Y offset
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

export const SankeyCard: React.FC<SankeyCardProps> = ({
    title,
    data = { nodes: [], links: [] },
    config = {},
    style = {}
}) => {
    const showLegend = config.showLegend === true;
    const isHorizontal = true; // Hardcoded spread for now

    const accentColor = style.accentColor || '#eaff00';
    const textColor = style.textColor || '#ffffff';

    // Simple Sankey Layout Engine
    const { nodes, links, cardWidth, cardHeight } = useMemo(() => {
        // Clone to avoid mutation
        const nodes: SankeyNode[] = JSON.parse(JSON.stringify(data.nodes || []));
        const links: SankeyLink[] = JSON.parse(JSON.stringify(data.links || []));

        const cardWidth = 300; // Internal SVG coordinate space width
        const cardHeight = 200; // Internal SVG coordinate space height
        const nodeWidth = 8;
        const padding = 20; // Side padding

        if (nodes.length === 0) return { nodes: [], links: [], cardWidth, cardHeight };

        // 1. Assign Layers (Columns) - Naive BFS
        nodes.forEach(n => n.layer = 0);
        // Assumes DAG. A robust implementation would detect cycles.
        // Simple propagate: target layer = source layer + 1
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

        // 2. Calculate Values (Throughput)
        nodes.forEach(n => {
            n.value = Math.max(0.1,
                Math.max(
                    links.filter(l => l.source === nodes.indexOf(n)).reduce((sum, l) => sum + l.value, 0),
                    links.filter(l => l.target === nodes.indexOf(n)).reduce((sum, l) => sum + l.value, 0)
                )
            );
        });

        // Link offsets tracking
        const sourceOffsets = new Array(nodes.length).fill(0);
        const targetOffsets = new Array(nodes.length).fill(0);

        // 3. Assign X Positions
        const layerWidth = (cardWidth - (padding * 2)) / (Math.max(1, maxLayer));
        nodes.forEach(n => {
            n.x = padding + ((n.layer || 0) * layerWidth);
            n.w = nodeWidth;
        });

        // 4. Assign Y Positions (Vertical distribution in layer)
        const layers: SankeyNode[][] = [];
        for (let i = 0; i <= maxLayer; i++) layers.push([]);
        nodes.forEach(n => layers[n.layer || 0].push(n));

        const maxY = cardHeight - 10;
        layers.forEach(layerNodes => {
            const totalValue = layerNodes.reduce((sum, n) => sum + (n.value || 0), 0);
            const gap = (maxY - totalValue) / (layerNodes.length + 1); // Distribute gaps? 
            // Better: Scale everything to fit height? For now, relative scale
            // Let's assume input values map closely to pixels or normalize
            const scale = (cardHeight - 20) / Math.max(totalValue * 1.5, 50); // Scale factor

            let currentY = 10;
            layerNodes.forEach(n => {
                n.h = (n.value || 0) * scale;
                n.y = currentY;
                currentY += n.h + 10; // Gap
            });
        });

        // 5. Calculate Link Coordinates
        links.forEach(l => {
            const source = nodes[l.source];
            const target = nodes[l.target];
            if (!source || !target) return;

            // Recalculate scale for consistency
            // Just use node height ratio
            const sourceH = source.h || 0;
            const targetH = target.h || 0;

            // Link width at source/target proportional to value
            // We use simple accumulation

            // Need effective flow scale
            // Simplified: just use offsets relative to node height
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

            // Store displaying Thickness for path
            // In SVG path 'stroke-width' is constant... we might need a filled path for varying width
            // But usually Sankey links are constant width ribbons. 
            // Let's average source/target height for stroke width, or use a filled shape.
            // Filled shape is better.
            (l as any).thickness = (sHeight + tHeight) / 2;
            (l as any).sThickness = sHeight;
            (l as any).tThickness = tHeight;
        });

        return { nodes, links, cardWidth, cardHeight };
    }, [data]);


    // Helper for Sankey Ribbon Path (Source Rect -> Target Rect)
    const getRibbonPath = (l: any, i: number) => {
        const sourceNode = nodes[l.source];
        const targetNode = nodes[l.target];
        if (!sourceNode || !targetNode) return '';

        const x0 = sourceNode.x! + sourceNode.w!;
        const x1 = targetNode.x!;
        const y0 = l.y0!;
        const y1 = l.y1!;
        const h0 = l.sThickness;
        const h1 = l.tThickness;

        // Curvature
        const curvature = 0.5;
        const xi = d3_interpolateNumber(x0, x1);
        const x2 = xi(curvature);
        const x3 = xi(1 - curvature);

        // Helper to interpolate X
        function d3_interpolateNumber(a: number, b: number) { return function (t: number) { return a * (1 - t) + b * t; }; }

        // M x0 y0 C x2 y0, x3 y1, x1 y1  (Top Curve)
        // L x1 y1+h1                     (Down)
        // C x3 y1+h1, x2 y0+h0, x0 y0+h0 (Bottom Curve)
        // Z

        return `
            M ${x0} ${y0}
            C ${x2} ${y0}, ${x3} ${y1}, ${x1} ${y1}
            L ${x1} ${y1 + h1}
            C ${x3} ${y1 + h1}, ${x2} ${y0 + h0}, ${x0} ${y0 + h0}
            Z
        `;
    };

    return (
        <BaseCard title={title}>
            <div className="w-full h-full flex flex-col relative p-4">
                <div className="flex-1 relative">
                    <svg className="w-full h-full overflow-visible" viewBox={`0 0 ${cardWidth} ${cardHeight}`} preserveAspectRatio="none">
                        <defs>
                            <linearGradient id="linkGradient" gradientUnits="userSpaceOnUse">
                                <stop offset="0%" stopColor={accentColor} stopOpacity="0.2" />
                                <stop offset="100%" stopColor={accentColor} stopOpacity="0.5" />
                            </linearGradient>
                        </defs>

                        {/* Links */}
                        {links.map((l: any, i) => (
                            <path
                                key={`link-${i}`}
                                d={getRibbonPath(l, i)}
                                fill={l.color || "url(#linkGradient)"}
                                className="opacity-50 hover:opacity-80 transition-opacity duration-300"
                            />
                        ))}

                        {/* Nodes */}
                        {nodes.map((n, i) => (
                            <g key={`node-${i}`}>
                                <rect
                                    x={n.x}
                                    y={n.y}
                                    width={n.w}
                                    height={n.h}
                                    fill={n.color || accentColor}
                                    rx={1}
                                    className="hover:brightness-125 transition-all"
                                />
                                <text
                                    x={n.x! + (n.layer! > 1 ? -6 : 8)}
                                    y={n.y! + n.h! / 2}
                                    dy="0.35em"
                                    textAnchor={n.layer! > 1 ? "end" : "start"}
                                    className="text-[6px] font-medium pointer-events-none uppercase tracking-wider"
                                    fill={textColor}
                                    style={{ textShadow: '0 1px 2px rgba(0,0,0,0.8)' }}
                                >
                                    {n.name}
                                </text>
                            </g>
                        ))}
                    </svg>
                </div>

                {showLegend && (
                    <div className="flex flex-wrap gap-2 mt-2 justify-center">
                        {nodes.map((n, i) => (
                            <div key={i} className="flex items-center gap-1">
                                <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: n.color || accentColor }} />
                                <span className="text-[8px] text-muted-foreground">{n.name}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
