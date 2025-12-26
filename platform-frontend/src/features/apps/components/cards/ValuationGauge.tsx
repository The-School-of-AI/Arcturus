import React from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

export const ValuationGauge: React.FC<{ title?: string, marketPrice?: number, fairValue?: number }> = ({ title = "Valuation Gauge", marketPrice = 145.2, fairValue = 180.5 }) => {
    const discount = ((fairValue - marketPrice) / fairValue) * 100;
    const isUndervalued = discount > 0;

    // Calculate slider position (0-100)
    // Map range [fairValue*0.5, fairValue*1.5] to [0, 100]
    const rangeMin = fairValue * 0.5;
    const rangeMax = fairValue * 1.5;
    const position = Math.max(0, Math.min(100, ((marketPrice - rangeMin) / (rangeMax - rangeMin)) * 100));

    return (
        <BaseCard title={title}>
            <div className="flex flex-col gap-4">
                <div className="flex justify-between items-end">
                    <div className="space-y-1">
                        <div className="text-[10px] text-muted-foreground uppercase">Market Price</div>
                        <div className="text-xl font-bold font-mono">${marketPrice.toFixed(1)}</div>
                    </div>
                    <div className="text-right space-y-1">
                        <div className="text-[10px] text-muted-foreground uppercase">Estimated Fair Value</div>
                        <div className="text-xl font-bold font-mono text-neon-yellow">${fairValue.toFixed(1)}</div>
                    </div>
                </div>

                <div className="relative h-6 flex items-center">
                    <div className="absolute inset-0 h-1.5 bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 rounded-full top-1/2 -translate-y-1/2 opacity-30" />
                    <div className="absolute h-4 w-1 bg-white rounded-full left-[50%] top-1/2 -translate-y-1/2 z-10" title="Fair Value Center" />
                    <div className="absolute h-6 w-1.5 bg-primary rounded-full top-1/2 -translate-y-1/2 shadow-[0_0_10px_rgba(var(--primary),0.5)] z-20" style={{ left: `${position}%` }} />
                </div>

                <div className={cn(
                    "text-xs font-bold text-center py-2 rounded-lg border",
                    isUndervalued ? "bg-green-500/10 text-green-400 border-green-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"
                )}>
                    {isUndervalued ? `Undervalued by ${discount.toFixed(1)}%` : `Overvalued by ${Math.abs(discount).toFixed(1)}%`}
                </div>
            </div>
        </BaseCard>
    );
};
