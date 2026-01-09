import React from 'react';
import { BaseCard } from './BaseCard';
import { CheckCircle2, AlertTriangle, HelpCircle } from 'lucide-react';

export interface SummaryGridProps {
    title?: string;
    data?: any;
    // Removing generic style prop requirement, preferring strict props or classNames
    className?: string;
    cardId?: string;
    autoFit?: boolean;
    context?: string;
}

const DEFAULT_FINDINGS = [
    { label: "Solvency", status: "pass", text: "Healthy debt-to-equity ratio of 0.45" },
    { label: "Profitability", status: "pass", text: "ROE consistently above 20% for 3 years" },
    { label: "Valuation", status: "warn", text: "Trading at 5% premium to historical P/E" },
    { label: "Momentum", status: "info", text: "RSI indicating neutral territory (54)" },
];

export const SummaryGrid: React.FC<SummaryGridProps> = ({
    title: propTitle,
    data = {},
    cardId,
    autoFit,
    context
}) => {
    const title = data.title || propTitle || "Executive Summary";
    const findings = data.findings || DEFAULT_FINDINGS;

    return (
        <BaseCard title={title} cardId={cardId} autoFit={autoFit}>
            <div className="grid grid-cols-1 gap-3">
                {findings.map((f: any) => (
                    <div key={f.label} className="flex gap-3 items-start group">
                        <div className="mt-0.5 transition-transform duration-200 group-hover:scale-110">
                            {f.status === 'pass' && <CheckCircle2 className="w-3.5 h-3.5 text-green-500 dark:text-green-400" />}
                            {f.status === 'warn' && <AlertTriangle className="w-3.5 h-3.5 text-yellow-500 dark:text-yellow-400" />}
                            {f.status === 'info' && <HelpCircle className="w-3.5 h-3.5 text-blue-500 dark:text-blue-400" />}
                        </div>
                        <div className="space-y-0.5 min-w-0">
                            <div className="text-[12px] font-bold text-foreground leading-none tracking-tight">
                                {f.label}
                            </div>
                            <div className="text-[12px] text-muted-foreground leading-tight opacity-90">
                                {f.text}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </BaseCard>
    );
};
