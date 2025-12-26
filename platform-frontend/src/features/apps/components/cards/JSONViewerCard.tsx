import React from 'react';
import { BaseCard } from './BaseCard';

export interface JSONViewerCardProps {
    title?: string;
    jsonData?: any;
    config?: any;
    style?: any;
}

const DEFAULT_DATA = {
    ticker: "GOOGL",
    metrics: {
        revenue: 282.8,
        net_income: 59.9,
        cash: 113.7
    },
    flags: ["undervalued", "high_growth"]
};

export const JSONViewerCard: React.FC<JSONViewerCardProps> = ({ 
    title = "Raw Data", 
    jsonData,
    style = {}
}) => {
    const displayData = jsonData || DEFAULT_DATA;
    const accentColor = style.accentColor || 'var(--primary)';
    
    return (
        <BaseCard title={title}>
            <div className="font-mono text-[9px] bg-black/40 p-2 rounded border border-white/5 overflow-auto max-h-full scrollbar-hidden">
                <pre style={{ color: `${accentColor}cc` }}>
                    {JSON.stringify(displayData, null, 2)}
                </pre>
            </div>
        </BaseCard>
    );
};
