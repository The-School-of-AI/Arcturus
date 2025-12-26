import React from 'react';
import { BaseCard } from './BaseCard';

export interface PieChartCardProps {
    title: string;
    data?: { label: string, value: number, color: string }[];
}

export const PieChartCard: React.FC<PieChartCardProps> = ({ title, data = [
    { label: 'Category A', value: 40, color: '#3b82f6' },
    { label: 'Category B', value: 30, color: '#10b981' },
    { label: 'Category C', value: 20, color: '#f59e0b' },
    { label: 'Category D', value: 10, color: '#ef4444' },
] }) => {
    return (
        <BaseCard title={title}>
            <div className="flex items-center h-full gap-4">
                <div className="w-24 h-24 shrink-0 relative">
                    <svg viewBox="0 0 100 100" className="rotate-[-90deg]">
                        {/* Simulated segments */}
                        <circle cx="50" cy="50" r="40" fill="transparent" stroke="#3b82f6" strokeWidth="20" strokeDasharray="40 211.2" />
                        <circle cx="50" cy="50" r="40" fill="transparent" stroke="#10b981" strokeWidth="20" strokeDasharray="30 221.2" strokeDashoffset="-40" />
                        <circle cx="50" cy="50" r="40" fill="transparent" stroke="#f59e0b" strokeWidth="20" strokeDasharray="20 231.2" strokeDashoffset="-70" />
                        <circle cx="50" cy="50" r="40" fill="transparent" stroke="#ef4444" strokeWidth="20" strokeDasharray="10 241.2" strokeDashoffset="-90" />
                    </svg>
                </div>
                <div className="space-y-1">
                    {Array.isArray(data) && data.map(item => (
                        <div key={item.label} className="flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: item.color }} />
                            <span className="text-[10px] text-muted-foreground truncate">{item.label}</span>
                        </div>
                    ))}
                    {!Array.isArray(data) && (
                        <div className="text-[10px] text-muted-foreground italic">No data available</div>
                    )}
                </div>
            </div>
        </BaseCard>
    );
};
