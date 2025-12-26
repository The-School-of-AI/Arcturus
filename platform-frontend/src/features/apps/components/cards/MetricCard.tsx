import React from 'react';
import { BaseCard } from './BaseCard';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface MetricCardProps {
    title?: string;
    value?: string | number;
    change?: number; // percentage
    trend?: 'up' | 'down' | 'neutral';
    subtext?: string;
    config?: any;
    data?: any;
    style?: any;
}

export const MetricCard: React.FC<MetricCardProps> = ({
    title,
    value,
    change,
    trend,
    subtext,
    data = {},
    style = {}
}) => {
    // Use data prop values if available, otherwise fall back to direct props
    const displayValue = data.value || value || '0';
    const displayChange = data.change ?? change;
    const displayTrend = data.trend || trend || 'neutral';
    const displaySubtext = data.subtext || subtext;

    const successColor = style.successColor || '#4ade80';
    const dangerColor = style.dangerColor || '#f87171';
    const textColor = style.textColor || undefined;
    const accentColor = style.accentColor || '#eaff00';

    const getTrendColor = () => {
        if (displayTrend === 'up') return successColor;
        if (displayTrend === 'down') return dangerColor;
        return '#9ca3af';
    };

    return (
        <BaseCard title={title}>
            <div className="flex flex-col justify-center h-full">
                <div className="text-3xl font-bold tracking-tight" style={{ color: textColor }}>{displayValue}</div>
                {(displayChange !== undefined || displaySubtext) && (
                    <div className="flex items-center gap-2 mt-2">
                        {displayChange !== undefined && (
                            <div
                                className="flex items-center text-xs font-bold px-1.5 py-0.5 rounded"
                                style={{
                                    color: getTrendColor(),
                                    backgroundColor: `${getTrendColor()}15`
                                }}
                            >
                                {displayTrend === 'up' && <TrendingUp className="w-3 h-3 mr-1" />}
                                {displayTrend === 'down' && <TrendingDown className="w-3 h-3 mr-1" />}
                                {displayTrend === 'neutral' && <Minus className="w-3 h-3 mr-1" />}
                                {displayChange > 0 ? '+' : ''}{displayChange}%
                            </div>
                        )}
                        {displaySubtext && <div className="text-xs text-muted-foreground">{displaySubtext}</div>}
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
