import React from 'react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer
} from 'recharts';
import { useTheme } from '@/components/theme';

interface LineChartWidgetProps {
    data: any[];
    xKey: string;
    lines: { key: string; color: string; name?: string }[];
    title?: string;
}

const LineChartWidget: React.FC<LineChartWidgetProps> = ({ data, xKey, lines, title }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';

    const gridColor = isDark ? '#374151' : '#e5e7eb';
    const axisColor = isDark ? '#9CA3AF' : '#6b7280';
    const tooltipBg = isDark ? '#1F2937' : '#ffffff';
    const tooltipBorder = isDark ? '#374151' : '#e5e7eb';
    const tooltipText = isDark ? '#F3F4F6' : '#1f2937';

    return (
        <div className={`w-full h-64 p-4 rounded-lg border ${isDark ? 'bg-gray-800/50 border-gray-700' : 'bg-white border-gray-200 shadow-sm'}`}>
            {title && <h3 className={`text-sm font-semibold mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{title}</h3>}
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                    <XAxis
                        dataKey={xKey}
                        stroke={axisColor}
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                    />
                    <YAxis
                        stroke={axisColor}
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                    />
                    <Tooltip
                        contentStyle={{ backgroundColor: tooltipBg, border: `1px solid ${tooltipBorder}`, borderRadius: '4px', fontSize: '12px' }}
                        itemStyle={{ color: tooltipText }}
                    />
                    <Legend wrapperStyle={{ fontSize: '10px' }} />
                    {lines.map((line) => (
                        <Line
                            key={line.key}
                            type="monotone"
                            dataKey={line.key}
                            stroke={line.color}
                            name={line.name || line.key}
                            dot={false}
                            strokeWidth={2}
                        />
                    ))}
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
};

export default LineChartWidget;
