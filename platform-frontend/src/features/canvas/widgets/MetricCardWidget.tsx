import React from 'react';
import { useTheme } from '@/components/theme';

interface Metric {
    label: string;
    value: string | number;
    delta?: string;
    deltaType?: 'positive' | 'negative' | 'neutral';
    icon?: string;
}

interface MetricCardWidgetProps {
    title?: string;
    metrics: Metric[];
}

const MetricCardWidget: React.FC<MetricCardWidgetProps> = ({ title, metrics = [] }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';

    return (
        <div className={`w-full rounded-lg border ${isDark ? 'bg-gray-800/50 border-gray-700' : 'bg-white border-gray-200 shadow-sm'}`}>
            {title && (
                <div className={`px-4 py-2 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                    <h3 className={`text-sm font-semibold ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{title}</h3>
                </div>
            )}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-px" style={{ gridTemplateColumns: `repeat(${Math.min(metrics.length, 4)}, 1fr)` }}>
                {metrics.map((m, i) => (
                    <div key={i} className={`p-4 ${i > 0 ? (isDark ? 'border-l border-gray-700/50' : 'border-l border-gray-100') : ''}`}>
                        <div className={`text-xs uppercase tracking-wider font-semibold mb-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                            {m.label}
                        </div>
                        <div className={`text-2xl font-bold tabular-nums ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>
                            {m.value}
                        </div>
                        {m.delta && (
                            <div className={`text-xs font-medium mt-1 ${
                                m.deltaType === 'positive' ? 'text-green-500' :
                                m.deltaType === 'negative' ? 'text-red-500' :
                                isDark ? 'text-gray-400' : 'text-gray-500'
                            }`}>
                                {m.deltaType === 'positive' ? '↑ ' : m.deltaType === 'negative' ? '↓ ' : ''}{m.delta}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
};

export default MetricCardWidget;
