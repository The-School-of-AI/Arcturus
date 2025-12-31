import React from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

export interface GradeCardProps {
    title: string;
    grade: 'A+' | 'A' | 'A-' | 'B+' | 'B' | 'B-' | 'C+' | 'C' | 'C-' | 'D' | 'F';
    subtext?: string;
    style?: any;
    config?: any;
    data?: any;
}

export const GradeCard: React.FC<GradeCardProps> = ({
    title,
    grade,
    subtext,
    style = {},
    config = {},
    data = {}
}) => {
    const displayGrade = data.grade || grade || 'A';
    const displaySubtext = data.subtext || subtext;
    const useGradeColors = config.useGradeColors !== false; // Default to true for backward compatibility
    const accentColor = style.accentColor || '#F5C542';
    const textColor = style.textColor;

    // Support custom grade colors from style or fall back to defaults
    const gradeAColor = style.gradeA || '#22c55e';
    const gradeBColor = style.gradeB || '#4ade80';
    const gradeCColor = style.gradeC || '#eab308';
    const gradeDColor = style.gradeD || '#f97316';
    const gradeFColor = style.gradeF || '#ef4444';

    // Helper to determine color based on grade
    const getGradeColor = (g: string) => {
        if (g.startsWith('A')) return { color: gradeAColor, bg: `${gradeAColor}15` };
        if (g.startsWith('B')) return { color: gradeBColor, bg: `${gradeBColor}15` };
        if (g.startsWith('C')) return { color: gradeCColor, bg: `${gradeCColor}15` };
        if (g.startsWith('D')) return { color: gradeDColor, bg: `${gradeDColor}15` };
        return { color: gradeFColor, bg: `${gradeFColor}15` };
    };

    const gradeStyles = getGradeColor(displayGrade);

    // Use grade colors or accent color based on config
    const displayColor = useGradeColors ? gradeStyles.color : accentColor;
    const displayBg = useGradeColors ? gradeStyles.bg : `${accentColor}15`;

    return (
        <BaseCard title={title} textColor={textColor}>
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
