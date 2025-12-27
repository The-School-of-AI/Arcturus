import React, { useState } from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

export interface PieChartCardProps {
    title: string;
    data?: any;
    config?: any;
    style?: any;
}

// Vibrant color palette for auto-assigning colors when not specified
const DEFAULT_CHART_COLORS = [
    '#4ecdc4', // Teal
    '#ff6b6b', // Coral
    '#eaff00', // Neon Yellow
    '#a29bfe', // Lavender
    '#00cec9', // Cyan
    '#fd79a8', // Pink
    '#6c5ce7', // Purple
    '#00b894', // Mint
    '#e17055', // Burnt Orange
    '#74b9ff', // Sky Blue
    '#ffeaa7', // Cream Yellow
    '#55a3ff', // Bright Blue
];

const defaultSlices = [
    { label: 'Category A', value: 40, color: '#4ecdc4' },
    { label: 'Category B', value: 30, color: '#ff6b6b' },
    { label: 'Category C', value: 20, color: '#eaff00' },
    { label: 'Category D', value: 10, color: '#a29bfe' },
];

export const PieChartCard: React.FC<PieChartCardProps> = ({
    title,
    data = {},
    config = {},
    style = {}
}) => {
    const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
    const [tooltip, setTooltip] = useState<{ x: number; y: number; content: string; visible: boolean }>({ x: 0, y: 0, content: '', visible: false });

    // Support both data.slices (from inspector) and direct array (legacy)
    const rawSlices = Array.isArray(data) ? data : (data.slices || defaultSlices);

    // Auto-assign colors if not provided
    const slices = rawSlices.map((slice: any, idx: number) => ({
        ...slice,
        color: slice.color || DEFAULT_CHART_COLORS[idx % DEFAULT_CHART_COLORS.length]
    }));

    // Feature toggles from config
    const showLegend = config.showLegend !== false;
    const showPercent = config.showPercent !== false;
    const isDonut = config.donut === true;
    const animate = config.animate !== false;

    // Calculate total for percentages
    const total = slices.reduce((sum: number, s: any) => sum + (s.value || 0), 0);

    // Donut vs Pie settings
    const strokeWidth = isDonut ? 18 : 50;
    const radius = isDonut ? 41 : 25;
    const circumference = 2 * Math.PI * radius;

    // Calculate angles for hit detection
    const getSliceAngles = () => {
        let cumulative = 0;
        return slices.map((slice: any) => {
            const percentage = total > 0 ? (slice.value / total) * 100 : 0;
            const startAngle = cumulative;
            cumulative += (percentage / 100) * 360;
            return { startAngle, endAngle: cumulative, slice, percentage };
        });
    };

    const sliceAngles = getSliceAngles();

    const showTooltipForSlice = (e: React.MouseEvent, slice: any, percentage: number) => {
        const rect = (e.currentTarget.closest('.pie-container') as HTMLElement)?.getBoundingClientRect();
        if (rect) {
            setTooltip({
                x: e.clientX - rect.left,
                y: e.clientY - rect.top - 15,
                content: `${slice.label}: ${slice.value} (${percentage.toFixed(1)}%)`,
                visible: true
            });
        }
    };

    const hideTooltip = () => setTooltip(prev => ({ ...prev, visible: false }));

    let cumulativeOffset = 0;

    return (
        <BaseCard title={title}>
            <div className="flex items-center h-full gap-4 pie-container relative">
                {/* Tooltip */}
                {tooltip.visible && (
                    <div
                        className="absolute z-50 px-2 py-1.5 bg-popover text-popover-foreground text-[10px] rounded border border-border shadow-xl pointer-events-none whitespace-nowrap"
                        style={{ left: tooltip.x, top: tooltip.y, transform: 'translate(-50%, -100%)' }}
                    >
                        {tooltip.content}
                    </div>
                )}

                <div className="w-28 h-28 shrink-0 relative">
                    <svg viewBox="0 0 100 100" className={cn("rotate-[-90deg]", animate && "animate-in zoom-in-95 duration-500")}>
                        {slices.map((slice: any, idx: number) => {
                            const percentage = total > 0 ? (slice.value / total) * 100 : 0;
                            const strokeLength = (percentage / 100) * circumference;
                            const offset = cumulativeOffset;
                            cumulativeOffset += strokeLength;

                            const isHovered = hoveredIndex === idx;

                            return (
                                <circle
                                    key={idx}
                                    cx="50"
                                    cy="50"
                                    r={radius}
                                    fill="transparent"
                                    stroke={slice.color || '#3b82f6'}
                                    strokeWidth={strokeWidth}
                                    strokeDasharray={`${strokeLength} ${circumference}`}
                                    strokeDashoffset={-offset}
                                    className={cn(
                                        "cursor-crosshair transition-all duration-200",
                                        isHovered && "brightness-125"
                                    )}
                                    style={{
                                        transform: isHovered ? 'scale(1.03)' : 'scale(1)',
                                        transformOrigin: 'center',
                                        filter: isHovered ? 'drop-shadow(0 0 8px rgba(255,255,255,0.3))' : undefined
                                    }}
                                    onMouseEnter={(e) => {
                                        setHoveredIndex(idx);
                                        showTooltipForSlice(e as any, slice, percentage);
                                    }}
                                    onMouseMove={(e) => showTooltipForSlice(e as any, slice, percentage)}
                                    onMouseLeave={() => {
                                        setHoveredIndex(null);
                                        hideTooltip();
                                    }}
                                />
                            );
                        })}
                    </svg>

                    {/* Center label for donut */}
                    {isDonut && (
                        <div className="absolute inset-0 flex items-center justify-center">
                            <div className="text-center">
                                <div className="text-lg font-bold" style={{ color: style.textColor || '#fff' }}>{total}</div>
                                <div className="text-[8px] text-muted-foreground">Total</div>
                            </div>
                        </div>
                    )}
                </div>

                {showLegend && (
                    <div className="space-y-1.5">
                        {Array.isArray(slices) && slices.map((item: any, idx: number) => {
                            const percentage = total > 0 ? ((item.value / total) * 100).toFixed(1) : 0;
                            const isHovered = hoveredIndex === idx;
                            const itemLabel = item.label || item.name || `Slice ${idx + 1}`;
                            return (
                                <div
                                    key={idx}
                                    className={cn(
                                        "flex items-center gap-2 cursor-pointer transition-all duration-200",
                                        isHovered && "translate-x-1"
                                    )}
                                    onMouseEnter={() => setHoveredIndex(idx)}
                                    onMouseLeave={() => setHoveredIndex(null)}
                                >
                                    <div
                                        className={cn("w-2 h-2 rounded-sm transition-all", isHovered && "scale-125")}
                                        style={{ backgroundColor: item.color }}
                                    />
                                    <span className={cn("text-[10px] text-muted-foreground truncate transition-colors", isHovered && "text-foreground")}>
                                        {itemLabel}{showPercent && ` (${percentage}%)`}
                                    </span>
                                </div>
                            );
                        })}
                        {!Array.isArray(slices) && (
                            <div className="text-[10px] text-muted-foreground italic">No data available</div>
                        )}
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
