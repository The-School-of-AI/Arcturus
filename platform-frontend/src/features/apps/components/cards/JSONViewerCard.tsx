import React from 'react';
import { BaseCard } from './BaseCard';

export const JSONViewerCard: React.FC<{ title?: string, data?: any }> = ({ title = "Raw Data", data = {
    ticker: "GOOGL",
    metrics: {
        revenue: 282.8,
        net_income: 59.9,
        cash: 113.7
    },
    flags: ["undervalued", "high_growth"]
} }) => {
    return (
        <BaseCard title={title}>
            <div className="font-mono text-[9px] bg-black/40 p-2 rounded border border-white/5 overflow-auto max-h-full scrollbar-hidden">
                <pre className="text-primary/80">
                    {JSON.stringify(data, null, 2)}
                </pre>
            </div>
        </BaseCard>
    );
};
