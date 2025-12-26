import React from 'react';
import { BaseCard } from './BaseCard';

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

    return (
        <BaseCard title={tableTitle}>
            <div className="w-full text-xs text-left text-muted-foreground min-w-[200px]">
                {/* Headers */}
                <div className="flex border-b border-white/10 pb-2 mb-2 font-bold text-foreground">
                    {tableHeaders.map((h: string, i: number) => (
                        <div key={i} className="flex-1 px-1">{h}</div>
                    ))}
                </div>

                {/* Rows */}
                <div className="space-y-1">
                    {tableRows.map((row: string[], idx: number) => (
                        <div key={idx} className="flex py-1 hover:bg-white/5 rounded px-1 -mx-1 transition-colors">
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
