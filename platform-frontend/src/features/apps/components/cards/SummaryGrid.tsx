import React from 'react';
import { BaseCard } from './BaseCard';
import { CheckCircle2, AlertTriangle, HelpCircle } from 'lucide-react';

export interface SummaryGridProps {
    title?: string;
    data?: any;
    style?: any;
}

const DEFAULT_FINDINGS = [
    { label: "Solvency", status: "pass", text: "Healthy debt-to-equity ratio of 0.45" },
    { label: "Profitability", status: "pass", text: "ROE consistently above 20% for 3 years" },
    { label: "Valuation", status: "warn", text: "Trading at 5% premium to historical P/E" },
    { label: "Momentum", status: "info", text: "RSI indicating neutral territory (54)" },
];

export const SummaryGrid: React.FC<SummaryGridProps> = ({
    title = "Executive Summary",
    data = {},
    style = {}
}) => {
    const findings = data.findings || DEFAULT_FINDINGS;

    const passColor = style.passColor || '#4ade80';
    const warnColor = style.warnColor || '#F5C542';
    const infoColor = style.infoColor || '#3b82f6';
    const textColor = style.textColor;

    return (
        <BaseCard title={title} textColor={textColor}>
            <div className="grid grid-cols-1 gap-3">
                {findings.map((f: any) => (
                    <div key={f.label} className="flex gap-3 items-start">
                        <div className="mt-0.5">
                            {f.status === 'pass' && <CheckCircle2 className="w-3.5 h-3.5" style={{ color: passColor }} />}
                            {f.status === 'warn' && <AlertTriangle className="w-3.5 h-3.5" style={{ color: warnColor }} />}
                            {f.status === 'info' && <HelpCircle className="w-3.5 h-3.5" style={{ color: infoColor }} />}
                        </div>
                        <div className="space-y-0.5 min-w-0">
                            <div className="text-[10px] font-bold text-foreground leading-none" style={textColor ? { color: textColor } : {}}>{f.label}</div>
                            <div className="text-[10px] text-muted-foreground leading-tight" style={textColor ? { color: textColor, opacity: 0.7 } : {}}>{f.text}</div>
                        </div>
                    </div>
                ))}
            </div>
        </BaseCard>
    );
};
