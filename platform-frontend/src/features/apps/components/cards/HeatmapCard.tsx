import React, { useMemo } from 'react';
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
    '#fd79a8', // Pink
    '#a29bfe', // Lavender
    '#00b894', // Mint
    '#e17055', // Burnt Orange
    '#74b9ff', // Soft Blue
];

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
    yLabels: ['00:00', '06:00', '12:00', '18:00'],
    values: [
        [10, 20, 30, 45, 50, 40, 20],
        [15, 25, 55, 70, 60, 45, 25],
        [25, 45, 80, 95, 85, 60, 35],
        [12, 18, 35, 50, 45, 30, 18]
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
    // Config options
    const showLegend = config.showLegend !== false;
    const showGrid = config.showGrid !== false;
    const showAxis = config.showAxisLabels !== false;
    const animate = config.animate !== false;
    const autoMultiColor = config.autoMultiColor !== false; // Default ON

    // Style
    const accentColor = style.accentColor || '#eaff00';

    // Use default data if not provided
    const xLabels = data.xLabels?.length > 0 ? data.xLabels : DEFAULT_HEATMAP_DATA.xLabels;
    const yLabels = data.yLabels?.length > 0 ? data.yLabels : DEFAULT_HEATMAP_DATA.yLabels;
    const values = data.values?.length > 0 ? data.values : DEFAULT_HEATMAP_DATA.values;

    const { flatValues, maxValue, minValue } = useMemo(() => {
        const flat = values.flat();
        return {
            flatValues: flat,
            maxValue: flat.length > 0 ? Math.max(...flat) : 100,
            minValue: flat.length > 0 ? Math.min(...flat) : 0
        };
    }, [values]);

    // Generate cell color based on value
    const getCellColor = (val: number) => {
        const normalized = (val - minValue) / (maxValue - minValue || 1);

        if (autoMultiColor) {
            // Multi-color gradient: dark blue -> teal -> yellow -> red
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
            // Single color with opacity variation
            return accentColor;
        }
    };

    const getCellOpacity = (val: number) => {
        if (autoMultiColor) return 1;
        const normalized = (val - minValue) / (maxValue - minValue || 1);
        return Math.max(0.15, normalized);
    };

    return (
        <BaseCard title={title}>
            <div className="w-full h-full flex flex-col p-4 overflow-hidden select-none">
                <div className="flex-1 flex flex-col gap-0.5 min-h-0">
                    {/* Rows */}
                    {values.map((row: number[], i: number) => (
                        <div key={i} className={cn("flex-1 flex gap-0.5 min-h-0", animate && "animate-in fade-in duration-500")} style={{ animationDelay: `${i * 100}ms` }}>
                            {/* Y Label */}
                            {showAxis && (
                                <div className="w-12 flex items-center justify-end pr-2 text-[10px] text-muted-foreground truncate shrink-0 font-medium">
                                    {yLabels[i] || ''}
                                </div>
                            )}
                            {/* Cells */}
                            {row.map((val: number, j: number) => (
                                <div
                                    key={j}
                                    className={cn(
                                        "flex-1 rounded-sm transition-all hover:brightness-125 hover:scale-105 relative group min-w-0 cursor-crosshair",
                                        showGrid && "border border-white/5"
                                    )}
                                    style={{
                                        backgroundColor: getCellColor(val),
                                        opacity: getCellOpacity(val)
                                    }}
                                    title={`${xLabels[j] || ''}, ${yLabels[i] || ''}: ${val}`}
                                >
                                    {/* Tooltip on hover */}
                                    <div className="opacity-0 group-hover:opacity-100 absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-black/95 text-white text-[9px] rounded pointer-events-none whitespace-nowrap z-50 border border-white/10 shadow-xl">
                                        <div className="font-bold">{val}</div>
                                        <div className="text-gray-400">{xLabels[j]}, {yLabels[i]}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ))}
                </div>

                {/* X Labels */}
                {showAxis && (
                    <div className="flex gap-0.5 pl-12 pt-1.5 h-5 shrink-0">
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
