import React from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

export interface ScoreCardProps {
    title: string;
    score: number; // 0-100
    max?: number;
    subtext?: string;
}

export const ScoreCard: React.FC<ScoreCardProps> = ({ title, score, max = 100, subtext }) => {
    const percentage = Math.min(100, Math.max(0, (score / max) * 100));

    // Color logic
    const getColor = (p: number) => {
        if (p >= 80) return "bg-green-500";
        if (p >= 50) return "bg-yellow-500";
        return "bg-red-500";
    };

    return (
        <BaseCard title={title}>
            <div className="flex flex-col justify-center h-full gap-2">
                <div className="flex items-end justify-between mb-1">
                    <span className="text-3xl font-bold text-foreground">{score}</span>
                    <span className="text-xs text-muted-foreground  mb-1">/ {max}</span>
                </div>

                {/* Progress Bar Container */}
                <div className="h-2 w-full bg-charcoal-900 rounded-full overflow-hidden border border-white/5">
                    <div
                        className={cn("h-full transition-all duration-1000 ease-out", getColor(percentage))}
                        style={{ width: `${percentage}%` }}
                    />
                </div>

                {subtext && <div className="text-xs text-muted-foreground mt-1">{subtext}</div>}
            </div>
        </BaseCard>
    );
};
