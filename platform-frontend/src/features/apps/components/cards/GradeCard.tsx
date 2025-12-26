import React from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

export interface GradeCardProps {
    title: string;
    grade: 'A+' | 'A' | 'A-' | 'B+' | 'B' | 'B-' | 'C+' | 'C' | 'C-' | 'D' | 'F';
    subtext?: string;
}

export const GradeCard: React.FC<GradeCardProps> = ({ title, grade, subtext }) => {
    // Helper to determine color based on grade
    const getColor = (g: string) => {
        if (g.startsWith('A')) return 'text-green-500 border-green-500 bg-green-500/10';
        if (g.startsWith('B')) return 'text-green-400 border-green-400 bg-green-400/10';
        if (g.startsWith('C')) return 'text-yellow-500 border-yellow-500 bg-yellow-500/10';
        if (g.startsWith('D')) return 'text-orange-500 border-orange-500 bg-orange-500/10';
        return 'text-red-500 border-red-500 bg-red-500/10';
    };

    const styles = getColor(grade);

    return (
        <BaseCard title={title}>
            <div className="flex flex-col items-center justify-center h-full gap-2">
                <div className={cn("w-16 h-16 rounded-xl border-2 flex items-center justify-center text-4xl font-bold shadow-[0_0_15px_rgba(0,0,0,0.3)]", styles)}>
                    {grade}
                </div>
                {subtext && <div className="text-xs text-muted-foreground text-center max-w-[80%]">{subtext}</div>}
            </div>
        </BaseCard>
    );
};
