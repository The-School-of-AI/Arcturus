import React from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

export interface TableCardProps {
    title: string;
    headers?: string[];
    rows?: string[][];
    data?: any;
    config?: any;
    style?: any;
}

export const TableCard: React.FC<TableCardProps> = ({
    title,
    headers,
    rows,
    data = {},
    config = {},
    style = {}
}) => {
    // Use data prop if available, otherwise fall back to direct props or defaults
    const tableHeaders = data.headers || headers || ["Col A", "Col B", "Col C"];
    const tableRows = data.rows || rows || [["Data 1", "100", "High"], ["Data 2", "50", "Low"], ["Data 3", "75", "Medium"]];
    const tableTitle = data.title || title;

    // Feature toggles from config
    const showHeader = config.showHeader !== false;
    const striped = config.striped !== false;
    const hoverHighlight = config.hoverHighlight !== false;
    const showBorders = config.showBorders !== false;
    const textColor = (style.textColor && style.textColor !== '#ffffff' && style.textColor !== '#fff') ? style.textColor : undefined;

    return (
        <BaseCard title={tableTitle} textColor={textColor}>
            <div className={cn(
                "w-full text-xs text-left text-muted-foreground min-w-[200px]",
                showBorders && "border border-border rounded"
            )}>
                {/* Headers */}
                {showHeader && (
                    <div className={cn(
                        "flex pb-2 mb-2 font-bold text-foreground",
                        showBorders ? "border-b border-border px-2 pt-2" : "border-b border-border"
                    )} style={textColor ? { color: textColor, borderColor: `${textColor}30` } : {}}>
                        {tableHeaders.map((h: string, i: number) => (
                            <div key={i} className="flex-1 px-1">{h}</div>
                        ))}
                    </div>
                )}

                {/* Rows */}
                <div className={cn("space-y-0", showBorders && "px-2 pb-2")}>
                    {tableRows.map((row: string[], idx: number) => (
                        <div
                            key={idx}
                            className={cn(
                                "flex py-1.5 px-1 -mx-1 transition-colors rounded",
                                striped && idx % 2 === 1 && "bg-muted/50",
                                hoverHighlight && "hover:bg-muted"
                            )}
                            style={textColor ? { color: textColor } : {}}
                        >
                            {row.map((cell: string, cellIdx: number) => (
                                <div key={cellIdx} className="flex-1 px-1 truncate">{cell}</div>
                            ))}
                        </div>
                    ))}
                </div>
            </div>
        </BaseCard>
    );
};
