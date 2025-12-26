import React from 'react';
import { BaseCard } from './BaseCard';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface MetricCardProps {
    title: string;
    value: string | number;
    change?: number; // percentage
    trend?: 'up' | 'down' | 'neutral';
    subtext?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({ title, value, change, trend, subtext }) => {
    return (
        <BaseCard title={title}>
            <div className="flex flex-col justify-center h-full">
                <div className="text-3xl font-bold text-foreground tracking-tight">{value}</div>
                {(change !== undefined || subtext) && (
                    <div className="flex items-center gap-2 mt-2">
                        {change !== undefined && (
                            <div className={cn(
                                "flex items-center text-xs font-bold px-1.5 py-0.5 rounded",
                                trend === 'up' ? "text-green-400 bg-green-500/10" :
                                    trend === 'down' ? "text-red-400 bg-red-500/10" :
                                        "text-gray-400 bg-gray-500/10"
                            )}>
                                {trend === 'up' && <TrendingUp className="w-3 h-3 mr-1" />}
                                {trend === 'down' && <TrendingDown className="w-3 h-3 mr-1" />}
                                {trend === 'neutral' && <Minus className="w-3 h-3 mr-1" />}
                                {change > 0 ? '+' : ''}{change}%
                            </div>
                        )}
                        {subtext && <div className="text-xs text-muted-foreground">{subtext}</div>}
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
