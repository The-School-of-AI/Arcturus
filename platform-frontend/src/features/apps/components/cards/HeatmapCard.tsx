import React from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

export interface HeatmapCardProps {
    title: string;
    data?: any;
    config?: any;
    style?: any;
    isInteractive?: boolean;
}

export const HeatmapCard: React.FC<HeatmapCardProps> = ({
    title,
    data = {},
    config = {},
    style = {},
    isInteractive = false
}) => {
    const accentColor = style.accentColor || '#eaff00';

    // Default/Sample data
    const xLabels = data.xLabels || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const yLabels = data.yLabels || ['00:00', '06:00', '12:00', '18:00'];
    const values = data.values || [
        [10, 20, 30, 45, 50, 40, 20],
        [15, 25, 35, 50, 60, 45, 25],
        [20, 30, 40, 60, 80, 50, 30],
        [10, 15, 25, 35, 45, 30, 15]
    ];

    const flatValues = values.flat();
    const maxValue = flatValues.length > 0 ? Math.max(...flatValues) : 100;

    return (
        <BaseCard title={title}>
            <div className="w-full h-full flex flex-col p-4 overflow-hidden select-none">
                <div className="flex-1 flex flex-col gap-1 min-h-0">
                    {/* Rows */}
                    {values.map((row: number[], i: number) => (
                        <div key={i} className="flex-1 flex gap-1 min-h-0">
                            {/* Y Label */}
                            <div className="w-12 flex items-center justify-end pr-2 text-[10px] text-muted-foreground truncate shrink-0">
                                {yLabels[i] || ''}
                            </div>
                            {/* Cells */}
                            {row.map((val: number, j: number) => {
                                const intensity = Math.max(0.1, val / maxValue);
                                return (
                                    <div
                                        key={j}
                                        className="flex-1 rounded-sm transition-all hover:opacity-80 relative group min-w-0"
                                        style={{
                                            backgroundColor: accentColor,
                                            opacity: intensity
                                        }}
                                        title={`${xLabels[j] || ''}, ${yLabels[i] || ''}: ${val}`}
                                    >
                                        {/* Tooltip on hover */}
                                        <div className="opacity-0 group-hover:opacity-100 absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-1.5 py-0.5 bg-black/90 text-white text-[8px] rounded pointer-events-none whitespace-nowrap z-10 border border-white/10">
                                            {val}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    ))}
                </div>
                {/* X Labels */}
                <div className="flex gap-1 pl-12 pt-1 h-5 shrink-0">
                    {xLabels.map((label: string, i: number) => (
                        <div key={i} className="flex-1 text-[9px] text-muted-foreground text-center truncate">
                            {label}
                        </div>
                    ))}
                </div>
            </div>
        </BaseCard>
    );
};
