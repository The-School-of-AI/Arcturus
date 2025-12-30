import React, { useMemo, useState } from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

// Multi-color palette for auto-color mode
const MULTI_COLOR_PALETTE = [
    '#F5C542', // Neon Yellow
    '#ff6b6b', // Coral Red
    '#4ecdc4', // Teal
    '#45b7d1', // Sky Blue
    '#96ceb4', // Sage Green
    '#ffeaa7', // Light Yellow
    '#fd79a8', // Pink
    '#a29bfe', // Lavender
    '#00b894', // Mint
    '#e17055', // Burnt Orange
    '#74b9ff', // Soft Blue
    '#dfe6e9', // Light Gray
];

export interface ScatterCardProps {
    title: string;
    data?: any;
    config?: any;
    style?: any;
    isInteractive?: boolean;
}

// Stable default data
const DEFAULT_SCATTER_DATA = {
    points: [
        { x: 15, y: 25, label: 'Alpha', category: 'Group A' },
        { x: 28, y: 45, label: 'Beta', category: 'Group A' },
        { x: 42, y: 35, label: 'Gamma', category: 'Group A' },
        { x: 55, y: 65, label: 'Delta', category: 'Group B' },
        { x: 68, y: 50, label: 'Epsilon', category: 'Group B' },
        { x: 22, y: 72, label: 'Zeta', category: 'Group B' },
        { x: 75, y: 82, label: 'Eta', category: 'Group C' },
        { x: 85, y: 38, label: 'Theta', category: 'Group C' },
        { x: 35, y: 58, label: 'Iota', category: 'Group C' },
        { x: 48, y: 88, label: 'Kappa', category: 'Group A' },
        { x: 62, y: 22, label: 'Lambda', category: 'Group B' },
        { x: 92, y: 68, label: 'Mu', category: 'Group C' }
    ],
    xLabel: 'X Axis',
    yLabel: 'Y Axis'
};

export const ScatterCard: React.FC<ScatterCardProps> = ({
    title,
    data = {},
    config = {},
    style = {},
    isInteractive = false
}) => {
    const [tooltip, setTooltip] = useState<{ x: number; y: number; content: React.ReactNode; visible: boolean }>({ x: 0, y: 0, content: '', visible: false });

    // Config options
    const showLegend = config.showLegend !== false;
    const showGrid = config.showGrid !== false;
    const showAxis = config.showAxisLabels !== false;
    const animate = config.animate !== false;
    const autoMultiColor = config.autoMultiColor !== false;

    // Style
    const accentColor = style.accentColor || '#F5C542';

    // Use default data if not provided
    const points = data.points?.length > 0 ? data.points : DEFAULT_SCATTER_DATA.points;
    const xLabel = data.xLabel || DEFAULT_SCATTER_DATA.xLabel;
    const yLabel = data.yLabel || DEFAULT_SCATTER_DATA.yLabel;

    // Calculate min/max for scaling
    const { minX, maxX, minY, maxY, categories, colorMap } = useMemo(() => {
        const xVals = points.map((p: any) => p.x);
        const yVals = points.map((p: any) => p.y);

        const minX = Math.min(...xVals);
        const maxX = Math.max(...xVals);
        const minY = Math.min(...yVals);
        const maxY = Math.max(...yVals);

        const categories = [...new Set(points.map((p: any) => p.category || 'Default'))];
        const colorMap: Record<string, string> = {};
        categories.forEach((cat, i) => {
            colorMap[cat as string] = MULTI_COLOR_PALETTE[i % MULTI_COLOR_PALETTE.length];
        });

        return { minX, maxX, minY, maxY, categories, colorMap };
    }, [points]);

    const scaleX = (x: number) => ((x - minX) / (maxX - minX || 1)) * 90 + 5;
    const scaleY = (y: number) => ((y - minY) / (maxY - minY || 1)) * 90 + 5;

    const getPointColor = (pt: any, index: number) => {
        if (pt.color) return pt.color;
        if (autoMultiColor && pt.category) return colorMap[pt.category];
        if (autoMultiColor) return MULTI_COLOR_PALETTE[index % MULTI_COLOR_PALETTE.length];
        return accentColor;
    };

    const showTooltip = (e: React.MouseEvent, pt: any, index: number) => {
        const container = e.currentTarget.closest('.scatter-container') as HTMLElement;
        if (container) {
            const rect = container.getBoundingClientRect();
            setTooltip({
                x: e.clientX - rect.left,
                y: e.clientY - rect.top - 10,
                content: (
                    <div>
                        <div className="font-bold mb-0.5">{pt.label || `Point ${index + 1}`}</div>
                        {pt.category && <div className="text-muted-foreground text-[8px]">{pt.category}</div>}
                        <div className="text-muted-foreground">x: {pt.x}, y: {pt.y}</div>
                    </div>
                ),
                visible: true
            });
        }
    };

    const hideTooltip = () => setTooltip(prev => ({ ...prev, visible: false }));

    return (
        <BaseCard title={title}>
            <div className="w-full h-full flex flex-col p-4 relative select-none scatter-container">
                {/* Tooltip */}
                {tooltip.visible && (
                    <div
                        className="absolute z-50 px-2 py-1.5 bg-popover text-popover-foreground text-[9px] rounded border border-border shadow-xl pointer-events-none whitespace-nowrap"
                        style={{ left: tooltip.x, top: tooltip.y, transform: 'translate(-50%, -100%)' }}
                    >
                        {tooltip.content}
                    </div>
                )}

                <div className="flex-1 relative border-l border-b border-white/20 mb-5 ml-6">
                    {/* Grid lines */}
                    {showGrid && (
                        <>
                            <div className="absolute inset-0 flex flex-col justify-between opacity-10 pointer-events-none">
                                {[0, 1, 2, 3, 4].map(i => <div key={i} className="w-full border-t border-white" />)}
                            </div>
                            <div className="absolute inset-0 flex justify-between opacity-10 pointer-events-none">
                                {[0, 1, 2, 3, 4].map(i => <div key={i} className="h-full border-r border-white" />)}
                            </div>
                        </>
                    )}

                    {/* Y Axis ticks */}
                    {showAxis && (
                        <div className="absolute -left-6 inset-y-0 flex flex-col justify-between text-[8px] text-muted-foreground pointer-events-none">
                            {[maxY, Math.round((maxY + minY) / 2), minY].map((val, i) => (
                                <span key={i} className="text-right pr-1">{Math.round(val)}</span>
                            ))}
                        </div>
                    )}

                    {/* Points */}
                    {points.map((pt: any, i: number) => (
                        <div
                            key={i}
                            className={cn(
                                "absolute w-3 h-3 rounded-full hover:scale-150 hover:ring-2 ring-white/30 transition-all cursor-crosshair z-10 shadow-lg",
                                animate && "animate-in zoom-in-50 duration-500"
                            )}
                            style={{
                                left: `${scaleX(pt.x)}%`,
                                bottom: `${scaleY(pt.y)}%`,
                                backgroundColor: getPointColor(pt, i),
                                transform: 'translate(-50%, 50%)',
                                animationDelay: animate ? `${i * 50}ms` : undefined
                            }}
                            onMouseEnter={(e) => showTooltip(e, pt, i)}
                            onMouseMove={(e) => showTooltip(e, pt, i)}
                            onMouseLeave={hideTooltip}
                        />
                    ))}
                </div>

                {/* X Axis ticks */}
                {showAxis && (
                    <div className="flex justify-between pl-6 text-[8px] text-muted-foreground -mt-3 mb-1">
                        {[minX, Math.round((maxX + minX) / 2), maxX].map((val, i) => (
                            <span key={i}>{Math.round(val)}</span>
                        ))}
                    </div>
                )}

                {/* Labels */}
                <div className="absolute bottom-0 left-8 right-0 text-center text-[10px] text-muted-foreground font-medium">{xLabel}</div>
                <div className="absolute top-0 bottom-8 left-0 flex items-center justify-center w-5">
                    <span className="-rotate-90 whitespace-nowrap text-[10px] text-muted-foreground font-medium">{yLabel}</span>
                </div>

                {/* Legend */}
                {showLegend && autoMultiColor && categories.length > 1 && (
                    <div className="flex flex-wrap gap-3 justify-center border-t border-border/50 pt-2 mt-1">
                        {categories.map((cat, i) => (
                            <div key={i} className="flex items-center gap-1.5">
                                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: colorMap[cat as string] }} />
                                <span className="text-[9px] text-muted-foreground font-medium">{cat as string}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
