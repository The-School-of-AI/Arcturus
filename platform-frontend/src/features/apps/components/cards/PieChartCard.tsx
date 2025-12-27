import React from 'react';
import { BaseCard } from './BaseCard';

export interface PieChartCardProps {
    title: string;
    data?: any;
    config?: any;
    style?: any;
}

const defaultSlices = [
    { label: 'Category A', value: 40, color: '#3b82f6' },
    { label: 'Category B', value: 30, color: '#10b981' },
    { label: 'Category C', value: 20, color: '#f59e0b' },
    { label: 'Category D', value: 10, color: '#ef4444' },
];

export const PieChartCard: React.FC<PieChartCardProps> = ({
    title,
    data = {},
    config = {},
    style = {}
}) => {
    // Support both data.slices (from inspector) and direct array (legacy)
    const slices = Array.isArray(data) ? data : (data.slices || defaultSlices);

    // Feature toggles from config
    const showLegend = config.showLegend !== false;
    const showPercent = config.showPercent !== false;
    const isDonut = config.donut === true;

    // Calculate total for percentages
    const total = slices.reduce((sum: number, s: any) => sum + (s.value || 0), 0);

    // Calculate stroke offsets for each slice
    const circumference = 2 * Math.PI * 40; // radius = 40
    let cumulativeOffset = 0;

    // Donut vs Pie: donut has thinner stroke
    // For pie chart (solid): radius should be half the size (25) and strokeWidth full size (50) to fill it.
    // However, the previous logic used radius 40.
    // To make it look "filled" with stroke-dasharray hack:
    // radius = 25 (center of stroke is at 25px from center)
    // strokeWidth = 50 (covers 0 to 50px)
    // isDonut: radius 40, width 15 (covers 32.5 to 47.5 approx) - looks good for donut.

    const strokeWidth = isDonut ? 15 : 50;
    const radius = isDonut ? 42 : 25;

    return (
        <BaseCard title={title}>
            <div className="flex items-center h-full gap-4">
                <div className="w-24 h-24 shrink-0 relative">
                    <svg viewBox="0 0 100 100" className="rotate-[-90deg]">
                        {slices.map((slice: any, idx: number) => {
                            const percentage = total > 0 ? (slice.value / total) * 100 : 0;
                            const strokeLength = (percentage / 100) * (2 * Math.PI * radius);
                            const offset = cumulativeOffset;
                            cumulativeOffset += strokeLength;

                            return (
                                <circle
                                    key={idx}
                                    cx="50"
                                    cy="50"
                                    r={radius}
                                    fill="transparent"
                                    stroke={slice.color || '#3b82f6'}
                                    strokeWidth={strokeWidth}
                                    strokeDasharray={`${strokeLength} ${2 * Math.PI * radius}`}
                                    strokeDashoffset={-offset}
                                />
                            );
                        })}
                    </svg>
                </div>
                {showLegend && (
                    <div className="space-y-1">
                        {Array.isArray(slices) && slices.map((item: any) => {
                            const percentage = total > 0 ? ((item.value / total) * 100).toFixed(1) : 0;
                            return (
                                <div key={item.label} className="flex items-center gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: item.color }} />
                                    <span className="text-[10px] text-muted-foreground truncate">
                                        {item.label}{showPercent && ` (${percentage}%)`}
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
