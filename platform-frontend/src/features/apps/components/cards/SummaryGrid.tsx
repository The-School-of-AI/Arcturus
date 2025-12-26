import React from 'react';
import { BaseCard } from './BaseCard';
import { CheckCircle2, AlertTriangle, HelpCircle } from 'lucide-react';

export const SummaryGrid: React.FC<{ title?: string }> = ({ title = "Executive Summary" }) => {
    const findings = [
        { label: "Solvency", status: "pass", text: "Healthy debt-to-equity ratio of 0.45" },
        { label: "Profitability", status: "pass", text: "ROE consistently above 20% for 3 years" },
        { label: "Valuation", status: "warn", text: "Trading at 5% premium to historical P/E" },
        { label: "Momentum", status: "info", text: "RSI indicating neutral territory (54)" },
    ];

    return (
        <BaseCard title={title}>
            <div className="grid grid-cols-1 gap-3">
                {findings.map(f => (
                    <div key={f.label} className="flex gap-3 items-start">
                        <div className="mt-0.5">
                            {f.status === 'pass' && <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />}
                            {f.status === 'warn' && <AlertTriangle className="w-3.5 h-3.5 text-yellow-500" />}
                            {f.status === 'info' && <HelpCircle className="w-3.5 h-3.5 text-blue-500" />}
                        </div>
                        <div className="space-y-0.5 min-w-0">
                            <div className="text-[10px] font-bold text-foreground leading-none">{f.label}</div>
                            <div className="text-[10px] text-muted-foreground leading-tight">{f.text}</div>
                        </div>
                    </div>
                ))}
            </div>
        </BaseCard>
    );
};
