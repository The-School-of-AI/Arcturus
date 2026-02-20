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

interface LineChartWidgetProps {
    data: any[];
    xKey: string;
    lines: { key: string; color: string; name?: string }[];
    title?: string;
}

const LineChartWidget: React.FC<LineChartWidgetProps> = ({ data, xKey, lines, title }) => {
    return (
        <div className="w-full h-64 bg-gray-800/50 p-4 rounded-lg border border-gray-700">
            {title && <h3 className="text-sm font-semibold mb-2 text-gray-300">{title}</h3>}
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis
                        dataKey={xKey}
                        stroke="#9CA3AF"
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                    />
                    <YAxis
                        stroke="#9CA3AF"
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                    />
                    <Tooltip
                        contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '4px', fontSize: '12px' }}
                        itemStyle={{ color: '#F3F4F6' }}
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
