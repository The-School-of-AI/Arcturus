import React from 'react';
import { useTheme } from '@/components/theme';

interface ProgressStep {
    label: string;
    status: 'done' | 'active' | 'pending';
    detail?: string;
}

interface ProgressWidgetProps {
    title?: string;
    steps: ProgressStep[];
    percentage?: number;
}

const ProgressWidget: React.FC<ProgressWidgetProps> = ({ title, steps = [], percentage }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';

    const doneCount = steps.filter(s => s.status === 'done').length;
    const pct = percentage ?? (steps.length ? Math.round((doneCount / steps.length) * 100) : 0);

    return (
        <div className={`w-full rounded-lg border overflow-hidden ${isDark ? 'bg-gray-800/50 border-gray-700' : 'bg-white border-gray-200 shadow-sm'}`}>
            {title && (
                <div className={`px-4 py-2 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                    <div className="flex items-center justify-between">
                        <h3 className={`text-sm font-semibold ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{title}</h3>
                        <span className={`text-lg font-bold tabular-nums ${pct === 100 ? 'text-green-500' : isDark ? 'text-blue-400' : 'text-blue-600'}`}>{pct}%</span>
                    </div>
                    <div className={`mt-2 h-2 rounded-full overflow-hidden ${isDark ? 'bg-gray-700' : 'bg-gray-200'}`}>
                        <div className={`h-full rounded-full transition-all duration-500 ${pct === 100 ? 'bg-green-500' : 'bg-blue-500'}`} style={{ width: `${pct}%` }} />
                    </div>
                </div>
            )}
            <div className="p-3 space-y-1">
                {steps.map((step, i) => (
                    <div key={i} className="flex items-start gap-3 py-1.5">
                        <div className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold ${
                            step.status === 'done' ? 'bg-green-500 text-white' :
                            step.status === 'active' ? 'bg-blue-500 text-white animate-pulse' :
                            isDark ? 'bg-gray-700 text-gray-500' : 'bg-gray-200 text-gray-400'
                        }`}>
                            {step.status === 'done' ? '✓' : i + 1}
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className={`text-sm font-medium ${
                                step.status === 'done' ? (isDark ? 'text-gray-400 line-through' : 'text-gray-500 line-through') :
                                step.status === 'active' ? (isDark ? 'text-blue-400' : 'text-blue-600') :
                                isDark ? 'text-gray-500' : 'text-gray-400'
                            }`}>{step.label}</div>
                            {step.detail && <div className={`text-xs mt-0.5 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>{step.detail}</div>}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default ProgressWidget;
