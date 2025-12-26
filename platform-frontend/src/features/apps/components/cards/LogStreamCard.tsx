import React from 'react';
import { BaseCard } from './BaseCard';

export const LogStreamCard: React.FC<{ title?: string }> = ({ title = "Execution Logs" }) => {
    const logs = [
        { time: "09:41:02", type: "info", text: "Initializing Research Agent..." },
        { time: "09:41:05", type: "info", text: "Fetching financial statements from SEC EDGAR..." },
        { time: "09:41:12", type: "warn", text: "Rate limit approach for ticker GOOGL, slowing down..." },
        { time: "09:41:18", type: "success", text: "Data successfully normalized (4 statements)." },
        { time: "09:41:19", type: "info", text: "Running valuation model v2.1..." },
    ];

    return (
        <BaseCard title={title}>
            <div className="font-mono text-[9px] space-y-1.5">
                {logs.map((log, i) => (
                    <div key={i} className="flex gap-2 leading-tight">
                        <span className="text-muted-foreground/40 shrink-0">{log.time}</span>
                        <span className={cn(
                            "uppercase font-bold shrink-0",
                            log.type === 'info' ? "text-blue-400" :
                                log.type === 'warn' ? "text-yellow-400" :
                                    log.type === 'success' ? "text-green-400" : "text-red-400"
                        )}>{log.type}</span>
                        <span className="text-foreground/80 break-words">{log.text}</span>
                    </div>
                ))}
                <div className="pt-2 animate-pulse flex items-center gap-1">
                    <div className="w-1 h-3 bg-primary" />
                    <span className="text-[8px] text-primary/60 italic uppercase tracking-widest">Listening for events...</span>
                </div>
            </div>
        </BaseCard>
    );
};

// Internal cn helper for simple cards if needed
const cn = (...classes: any[]) => classes.filter(Boolean).join(' ');
