import React from 'react';
import { BaseCard } from './BaseCard';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { DEFAULT_COLORS } from '../../utils/defaults';

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
    config = {},
    data = {},
    style = {}
}) => {
    // Use data prop values if available, otherwise fall back to direct props
    const displayValue = data.value || value || '0';
    const displayChange = data.change ?? change;
    const displayTrend = data.trend || trend || 'neutral';
    const displaySubtext = data.subtext || subtext;

    // Feature toggles from config
    const showTitle = config.showTitle !== false;
    const showTrend = config.showTrend !== false;
    const showPercent = config.showPercent !== false;
    const isUp = (displayChange || 0) >= 0;

    const successColor = style.successColor || '#4ade80';
    const dangerColor = style.dangerColor || '#fb7185';
    const textColor = (style.textColor && style.textColor !== '#ffffff' && style.textColor !== '#fff') ? style.textColor : undefined;
    const accentColor = style.accentColor || DEFAULT_COLORS.accent;

    const getTrendColor = () => {
        if (displayTrend === 'up') return successColor;
        if (displayTrend === 'down') return dangerColor;
        return 'hsl(var(--muted-foreground))';
    };

    return (
        <BaseCard title={showTitle ? title : undefined} textColor={textColor}>
            <div className="flex flex-col justify-center h-full">
                <div className="text-3xl font-bold tracking-tight" style={{ color: textColor }}>{displayValue}</div>
                {(showPercent && displayChange !== undefined) || displaySubtext ? (
                    <div className="flex items-center gap-2 mt-2">
                        {showPercent && displayChange !== undefined && (
                            <div
                                className="flex items-center text-xs font-bold px-1.5 py-0.5 rounded"
                                style={{
                                    color: getTrendColor(),
                                    backgroundColor: `${getTrendColor()}15`
                                }}
                            >
                                {showTrend && displayTrend === 'up' && <TrendingUp className="w-3 h-3 mr-1" />}
                                {showTrend && displayTrend === 'down' && <TrendingDown className="w-3 h-3 mr-1" />}
                                {showTrend && displayTrend === 'neutral' && <Minus className="w-3 h-3 mr-1" />}
                                {displayChange > 0 ? '+' : ''}{displayChange}%
                            </div>
                        )}
                        {displaySubtext && <div className="text-xs text-foreground/60">{displaySubtext}</div>}
                    </div>
                ) : null}
            </div>
        </BaseCard>
    );
};
