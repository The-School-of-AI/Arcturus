import React from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

export interface GradeCardProps {
    title: string;
    grade: 'A+' | 'A' | 'A-' | 'B+' | 'B' | 'B-' | 'C+' | 'C' | 'C-' | 'D' | 'F';
    subtext?: string;
    style?: {
        accentColor?: string;
        textColor?: string;
    };
    config?: {
        useGradeColors?: boolean; // If true, uses grade-based colors, otherwise uses accentColor
    };
}

export const GradeCard: React.FC<GradeCardProps> = ({
    title,
    grade,
    subtext,
    style = {},
    config = {}
}) => {
    const useGradeColors = config.useGradeColors !== false; // Default to true for backward compatibility
    const accentColor = style.accentColor || '#F5C542';
    const textColor = style.textColor || '#ffffff';

    // Helper to determine color based on grade
    const getGradeColor = (g: string) => {
        if (g.startsWith('A')) return { color: '#22c55e', bg: 'rgba(34, 197, 94, 0.1)' }; // green-500
        if (g.startsWith('B')) return { color: '#4ade80', bg: 'rgba(74, 222, 128, 0.1)' }; // green-400
        if (g.startsWith('C')) return { color: '#eab308', bg: 'rgba(234, 179, 8, 0.1)' }; // yellow-500
        if (g.startsWith('D')) return { color: '#f97316', bg: 'rgba(249, 115, 22, 0.1)' }; // orange-500
        return { color: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)' }; // red-500
    };

    const gradeStyles = getGradeColor(grade);

    // Use grade colors or accent color based on config
    const displayColor = useGradeColors ? gradeStyles.color : accentColor;
    const displayBg = useGradeColors ? gradeStyles.bg : `${accentColor}15`;

    return (
        <BaseCard title={title}>
            <div className="flex flex-col items-center justify-center h-full gap-2">
                <div
                    className="w-16 h-16 rounded-xl border-2 flex items-center justify-center text-4xl font-bold shadow-[0_0_15px_rgba(0,0,0,0.3)]"
                    style={{
                        color: displayColor,
                        borderColor: displayColor,
                        backgroundColor: displayBg
                    }}
                >
                    {grade}
                </div>
                {subtext && (
                    <div
                        className="text-xs text-center max-w-[80%]"
                        style={{ color: textColor, opacity: 0.7 }}
                    >
                        {subtext}
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
