import React from 'react';
import { BaseCard } from './BaseCard';

export interface JSONViewerCardProps {
    title?: string;
    jsonData?: any;
    data?: any;
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
    data = {},
    config = {},
    style = {}
}) => {
    // Feature toggles from config
    const showTitle = config.showTitle !== false;
    const highlight = config.highlight !== false;
    const lineNumbers = config.lineNumbers === true;

    // Use data.json if available, otherwise fall back to direct prop or default
    const displayData = data.json || jsonData || DEFAULT_DATA;
    const accentColor = style.accentColor || 'var(--primary)';

    // Format JSON with optional line numbers
    const jsonString = JSON.stringify(displayData, null, 2);
    const lines = jsonString.split('\n');

    return (
        <BaseCard title={showTitle ? title : undefined}>
            <div className=" text-[9px] bg-muted p-2 rounded border border-border/50 overflow-auto max-h-full scrollbar-hidden">
                {lineNumbers ? (
                    <div className="flex">
                        <div className="pr-2 border-r border-border mr-2 text-muted-foreground/50 select-none">
                            {lines.map((_, i) => (
                                <div key={i}>{i + 1}</div>
                            ))}
                        </div>
                        <pre className="text-foreground/80" style={{ color: highlight ? `${accentColor}cc` : undefined }}>
                            {jsonString}
                        </pre>
                    </div>
                ) : (
                    <pre className="text-foreground/80" style={{ color: highlight ? `${accentColor}cc` : undefined }}>
                        {jsonString}
                    </pre>
                )}
            </div>
        </BaseCard>
    );
};
