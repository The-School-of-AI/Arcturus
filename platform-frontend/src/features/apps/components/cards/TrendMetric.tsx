import React from 'react';
import { BaseCard } from './BaseCard';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface TrendMetricProps {
    title: string;
    value: string | number;
    change: number;
    sparklineData?: number[];
}

export const TrendMetric: React.FC<TrendMetricProps> = ({ title, value, change, sparklineData = [30, 40, 35, 50, 45, 60, 55] }) => {
    const isUp = change >= 0;

    return (
        <BaseCard title={title}>
            <div className="flex items-center justify-between h-full">
                <div className="space-y-1">
                    <div className="text-2xl font-bold text-foreground tracking-tight">{value}</div>
                    <div className={cn(
                        "flex items-center text-[10px] font-bold px-1 py-0.5 rounded w-fit",
                        isUp ? "text-green-400 bg-green-500/10" : "text-red-400 bg-red-500/10"
                    )}>
                        {isUp ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
                        {isUp ? '+' : ''}{change}%
                    </div>
                </div>

                {/* Mini Sparkline */}
                <div className="flex-1 h-10 max-w-[100px] ml-4 opacity-50">
                    <svg className="w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 100 40">
                        <path
                            d={`M ${sparklineData.map((v, i) => `${(i / (sparklineData.length - 1)) * 100} ${40 - (v / 100) * 40}`).join(' L ')}`}
                            fill="none"
                            stroke={isUp ? "#4ade80" : "#fb7185"}
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        />
                    </svg>
                </div>
            </div>
        </BaseCard>
    );
};
