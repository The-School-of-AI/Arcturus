import React from 'react';
import { BaseCard } from './BaseCard';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface TrendMetricProps {
    title?: string;
    value: string | number;
    change?: number;
    sparklineData?: number[];
    showSparkline?: boolean;
    config?: any;
    data?: any;
    style?: any;
}

export const TrendMetric: React.FC<TrendMetricProps> = ({
    title,
    value,
    change,
    sparklineData = [30, 40, 35, 50, 45, 60, 55],
    showSparkline = true,
    data = {},
    style = {}
}) => {
    // Use data prop values if available, otherwise fall back to direct props
    const displayValue = data.value || value || '0';
    const displayChange = data.change ?? change;
    const displayLabel = data.label || title;

    const isUp = (displayChange || 0) >= 0;
    const successColor = style.successColor || '#4ade80';
    const dangerColor = style.dangerColor || '#fb7185';
    const textColor = (style.textColor && style.textColor !== '#ffffff' && style.textColor !== '#fff') ? style.textColor : undefined;

    return (
        <BaseCard title={displayLabel} textColor={textColor}>
            <div className="flex items-center justify-between h-full">
                <div className="space-y-1">
                    <div className="text-2xl font-bold tracking-tight" style={{ color: textColor }}>{displayValue}</div>
                    {displayChange !== undefined && (
                        <div className={cn(
                            "flex items-center text-[10px] font-bold px-1 py-0.5 rounded w-fit"
                        )}
                            style={{
                                color: isUp ? successColor : dangerColor,
                                backgroundColor: isUp ? `${successColor}15` : `${dangerColor}15`
                            }}
                        >
                            {isUp ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
                            {isUp ? '+' : ''}{displayChange}%
                        </div>
                    )}
                </div>

                {/* Mini Sparkline */}
                {showSparkline && (
                    <div className="flex-1 h-10 max-w-[100px] ml-4 opacity-50">
                        <svg className="w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 100 40">
                            <path
                                d={`M ${sparklineData.map((v, i) => `${(i / (sparklineData.length - 1)) * 100} ${40 - (v / 100) * 40}`).join(' L ')}`}
                                fill="none"
                                stroke={isUp ? successColor : dangerColor}
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            />
                        </svg>
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
