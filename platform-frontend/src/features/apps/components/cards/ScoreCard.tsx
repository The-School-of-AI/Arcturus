import React from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

export interface ScoreCardProps {
    title: string;
    score: number; // 0-100
    max?: number;
    subtext?: string;
    style?: any;
    config?: any;
    data?: any;
}

export const ScoreCard: React.FC<ScoreCardProps> = ({
    title,
    score,
    max = 100,
    subtext,
    style = {},
    config = {},
    data = {}
}) => {
    const displayScore = data.score ?? score;
    const displayMax = data.max ?? max;
    const displaySubtext = data.subtext ?? subtext;
    const percentage = Math.min(100, Math.max(0, (displayScore / displayMax) * 100));

    const successColor = style.successColor || '#4ade80';
    const warnColor = style.warnColor || '#F5C542';
    const dangerColor = style.dangerColor || '#f87171';
    const textColor = style.textColor;

    // Color logic
    const getColor = (p: number) => {
        if (p >= 80) return successColor;
        if (p >= 50) return warnColor;
        return dangerColor;
    };

    return (
        <BaseCard title={title} textColor={textColor}>
            <div className="flex flex-col justify-center h-full gap-2">
                <div className="flex items-end justify-between mb-1">
                    <span className="text-3xl font-bold text-foreground" style={textColor ? { color: textColor } : {}}>{displayScore}</span>
                    <span className="text-xs text-muted-foreground mb-1" style={textColor ? { color: textColor, opacity: 0.6 } : {}}>/ {displayMax}</span>
                </div>

                {/* Progress Bar Container */}
                <div className="h-2 w-full bg-muted rounded-full overflow-hidden border border-border/50">
                    <div
                        className={cn("h-full transition-all duration-1000 ease-out")}
                        style={{ width: `${percentage}%`, backgroundColor: getColor(percentage) }}
                    />
                </div>

                {displaySubtext && <div className="text-xs text-muted-foreground mt-1" style={textColor ? { color: textColor, opacity: 0.7 } : {}}>{displaySubtext}</div>}
            </div>
        </BaseCard>
    );
};
