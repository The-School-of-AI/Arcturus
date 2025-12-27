import React, { useMemo, useState } from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

export interface HeatmapCardProps {
    title: string;
    data?: any;
    config?: any;
    style?: any;
    isInteractive?: boolean;
}

// Default sample data
const DEFAULT_HEATMAP_DATA = {
    xLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    yLabels: ['Morning', 'Afternoon', 'Evening', 'Night'],
    values: [
        [15, 25, 55, 70, 60, 45, 25],
        [25, 45, 80, 95, 85, 60, 35],
        [12, 18, 35, 50, 45, 30, 18],
        [8, 12, 20, 30, 25, 15, 10]
    ]
};

// Color interpolation helper
const interpolateColor = (color1: string, color2: string, factor: number): string => {
    const hex = (x: string) => parseInt(x, 16);
    const r1 = hex(color1.slice(1, 3));
    const g1 = hex(color1.slice(3, 5));
    const b1 = hex(color1.slice(5, 7));
    const r2 = hex(color2.slice(1, 3));
    const g2 = hex(color2.slice(3, 5));
    const b2 = hex(color2.slice(5, 7));

    const r = Math.round(r1 + factor * (r2 - r1));
    const g = Math.round(g1 + factor * (g2 - g1));
    const b = Math.round(b1 + factor * (b2 - b1));

    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
};

export const HeatmapCard: React.FC<HeatmapCardProps> = ({
    title,
    data = {},
    config = {},
    style = {},
    isInteractive = false
}) => {
    const [tooltip, setTooltip] = useState<{ x: number; y: number; value: number; xLabel: string; yLabel: string; visible: boolean }>({
        x: 0, y: 0, value: 0, xLabel: '', yLabel: '', visible: false
    });

    // Config options
    const showLegend = config.showLegend !== false;
    const showGrid = config.showGrid !== false;
    const showAxis = config.showAxisLabels !== false;
    const animate = config.animate !== false;
    const autoMultiColor = config.autoMultiColor !== false;

    // Style
    const accentColor = style.accentColor || '#eaff00';

    // Use default data if not provided
    const xLabels = data.xLabels?.length > 0 ? data.xLabels : DEFAULT_HEATMAP_DATA.xLabels;
    const yLabels = data.yLabels?.length > 0 ? data.yLabels : DEFAULT_HEATMAP_DATA.yLabels;
    const values = data.values?.length > 0 ? data.values : DEFAULT_HEATMAP_DATA.values;

    const { maxValue, minValue } = useMemo(() => {
        const flat = values.flat();
        return {
            maxValue: flat.length > 0 ? Math.max(...flat) : 100,
            minValue: flat.length > 0 ? Math.min(...flat) : 0
        };
    }, [values]);

    // Generate cell color based on value
    const getCellColor = (val: number) => {
        const normalized = (val - minValue) / (maxValue - minValue || 1);

        if (autoMultiColor) {
            if (normalized < 0.25) {
                return interpolateColor('#1a1a2e', '#4ecdc4', normalized * 4);
            } else if (normalized < 0.5) {
                return interpolateColor('#4ecdc4', '#eaff00', (normalized - 0.25) * 4);
            } else if (normalized < 0.75) {
                return interpolateColor('#eaff00', '#ff6b6b', (normalized - 0.5) * 4);
            } else {
                return interpolateColor('#ff6b6b', '#ff2e63', (normalized - 0.75) * 4);
            }
        } else {
            return accentColor;
        }
    };

    const getCellOpacity = (val: number) => {
        if (autoMultiColor) return 1;
        const normalized = (val - minValue) / (maxValue - minValue || 1);
        return Math.max(0.15, normalized);
    };

    const showTooltip = (e: React.MouseEvent, value: number, xLabel: string, yLabel: string) => {
        const container = e.currentTarget.closest('.heatmap-container') as HTMLElement;
        if (container) {
            const rect = container.getBoundingClientRect();
            setTooltip({
                x: e.clientX - rect.left,
                y: e.clientY - rect.top - 10,
                value,
                xLabel,
                yLabel,
                visible: true
            });
        }
    };

    const hideTooltip = () => setTooltip(prev => ({ ...prev, visible: false }));

    return (
        <BaseCard title={title}>
            <div className="w-full h-full flex flex-col p-4 overflow-hidden select-none heatmap-container relative">
                {/* Tooltip */}
                {tooltip.visible && (
                    <div
                        className="absolute z-50 px-2 py-1.5 bg-black/95 text-white text-[9px] rounded border border-white/10 shadow-xl pointer-events-none whitespace-nowrap"
                        style={{ left: tooltip.x, top: tooltip.y, transform: 'translate(-50%, -100%)' }}
                    >
                        <div className="font-bold">{tooltip.value}</div>
                        <div className="text-gray-400">{tooltip.xLabel}, {tooltip.yLabel}</div>
                    </div>
                )}

                <div className="flex-1 flex flex-col gap-0.5 min-h-0">
                    {/* Rows */}
                    {values.map((row: number[], i: number) => (
                        <div key={i} className={cn("flex-1 flex gap-0.5 min-h-0", animate && "animate-in fade-in duration-500")} style={{ animationDelay: `${i * 100}ms` }}>
                            {/* Y Label */}
                            {showAxis && (
                                <div className="w-16 flex items-center justify-end pr-2 text-[9px] text-muted-foreground truncate shrink-0 font-medium">
                                    {yLabels[i] || ''}
                                </div>
                            )}
                            {/* Cells */}
                            {row.map((val: number, j: number) => (
                                <div
                                    key={j}
                                    className={cn(
                                        "flex-1 rounded-sm transition-all hover:brightness-125 hover:scale-105 min-w-0 cursor-crosshair",
                                        showGrid && "border border-white/5"
                                    )}
                                    style={{
                                        backgroundColor: getCellColor(val),
                                        opacity: getCellOpacity(val)
                                    }}
                                    onMouseEnter={(e) => showTooltip(e, val, xLabels[j] || '', yLabels[i] || '')}
                                    onMouseMove={(e) => showTooltip(e, val, xLabels[j] || '', yLabels[i] || '')}
                                    onMouseLeave={hideTooltip}
                                />
                            ))}
                        </div>
                    ))}
                </div>

                {/* X Labels */}
                {showAxis && (
                    <div className="flex gap-0.5 pl-16 pt-1.5 h-5 shrink-0">
                        {xLabels.map((label: string, i: number) => (
                            <div key={i} className="flex-1 text-[9px] text-muted-foreground text-center truncate font-medium">
                                {label}
                            </div>
                        ))}
                    </div>
                )}

                {/* Legend */}
                {showLegend && (
                    <div className="flex items-center justify-center gap-2 pt-2 border-t border-white/5 mt-2">
                        <span className="text-[9px] text-muted-foreground">Low</span>
                        <div className="flex h-2 w-24 rounded-full overflow-hidden">
                            {autoMultiColor ? (
                                <>
                                    <div className="flex-1 bg-[#1a1a2e]" />
                                    <div className="flex-1 bg-[#4ecdc4]" />
                                    <div className="flex-1 bg-[#eaff00]" />
                                    <div className="flex-1 bg-[#ff6b6b]" />
                                    <div className="flex-1 bg-[#ff2e63]" />
                                </>
                            ) : (
                                <div className="flex-1" style={{ background: `linear-gradient(to right, ${accentColor}20, ${accentColor})` }} />
                            )}
                        </div>
                        <span className="text-[9px] text-muted-foreground">High</span>
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
