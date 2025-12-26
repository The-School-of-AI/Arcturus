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

    // Calculate total for percentages
    const total = slices.reduce((sum: number, s: any) => sum + (s.value || 0), 0);

    // Calculate stroke offsets for each slice
    const circumference = 2 * Math.PI * 40; // radius = 40
    let cumulativeOffset = 0;

    return (
        <BaseCard title={title}>
            <div className="flex items-center h-full gap-4">
                <div className="w-24 h-24 shrink-0 relative">
                    <svg viewBox="0 0 100 100" className="rotate-[-90deg]">
                        {slices.map((slice: any, idx: number) => {
                            const percentage = total > 0 ? (slice.value / total) * 100 : 0;
                            const strokeLength = (percentage / 100) * circumference;
                            const offset = cumulativeOffset;
                            cumulativeOffset += strokeLength;

                            return (
                                <circle
                                    key={idx}
                                    cx="50"
                                    cy="50"
                                    r="40"
                                    fill="transparent"
                                    stroke={slice.color || '#3b82f6'}
                                    strokeWidth="20"
                                    strokeDasharray={`${strokeLength} ${circumference}`}
                                    strokeDashoffset={-offset}
                                />
                            );
                        })}
                    </svg>
                </div>
                <div className="space-y-1">
                    {Array.isArray(slices) && slices.map((item: any) => (
                        <div key={item.label} className="flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: item.color }} />
                            <span className="text-[10px] text-muted-foreground truncate">{item.label}</span>
                        </div>
                    ))}
                    {!Array.isArray(slices) && (
                        <div className="text-[10px] text-muted-foreground italic">No data available</div>
                    )}
                </div>
            </div>
        </BaseCard>
    );
};
