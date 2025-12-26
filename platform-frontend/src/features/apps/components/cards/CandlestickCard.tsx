import React from 'react';
import { BaseCard } from './BaseCard';

export const CandlestickCard: React.FC<{ title: string }> = ({ title }) => {
    return (
        <BaseCard title={title}>
            <div className="w-full h-full flex items-center justify-center pt-2">
                <svg className="w-full h-full text-muted-foreground opacity-50" preserveAspectRatio="none" viewBox="0 0 100 40">
                    {[10, 25, 40, 55, 70, 85].map((x, i) => (
                        <g key={i}>
                            <line x1={x} y1="5" x2={x} y2="35" stroke="currentColor" strokeWidth="1" />
                            <rect x={x - 3} y={10 + (i % 2) * 10} width="6" height="10" fill={i % 2 === 0 ? "#10b981" : "#ef4444"} />
                        </g>
                    ))}
                </svg>
            </div>
        </BaseCard>
    );
};
