import React, { useState } from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

// Vibrant color palette for auto-assigning colors when not specified
const DEFAULT_CHART_COLORS = [
    '#4ecdc4', // Teal
    '#ff6b6b', // Coral
    '#F5C542', // Neon Yellow
    '#a29bfe', // Lavender
    '#00cec9', // Cyan
    '#fd79a8', // Pink
    '#6c5ce7', // Purple
    '#00b894', // Mint
    '#e17055', // Burnt Orange
    '#74b9ff', // Sky Blue
];

export interface ChartCardProps {
    title: string;
    type: 'line' | 'bar' | 'area';
    data?: any;
    config?: any;
    style?: any;
}

// Default sample data
const DEFAULT_LINE_DATA = {
    series: [
        {
            name: 'Revenue',
            color: '#4ecdc4',
            data: [
                { x: 'Jan', y: 120 },
                { x: 'Feb', y: 150 },
                { x: 'Mar', y: 180 },
                { x: 'Apr', y: 160 },
                { x: 'May', y: 200 },
                { x: 'Jun', y: 220 }
            ]
        },
        {
            name: 'Cost',
            color: '#ff6b6b',
            data: [
                { x: 'Jan', y: 80 },
                { x: 'Feb', y: 90 },
                { x: 'Mar', y: 100 },
                { x: 'Apr', y: 95 },
                { x: 'May', y: 110 },
                { x: 'Jun', y: 120 }
            ]
        }
    ]
};

const DEFAULT_BAR_DATA = {
    points: [
        { x: 'Q1', y: 45, color: '#F5C542' },
        { x: 'Q2', y: 62, color: '#4ecdc4' },
        { x: 'Q3', y: 58, color: '#ff6b6b' },
        { x: 'Q4', y: 75, color: '#a29bfe' }
    ]
};

export const ChartCard: React.FC<ChartCardProps> = ({
    title,
    type,
    data = {},
    config = {},
    style = {}
}) => {
    const [tooltip, setTooltip] = useState<{ x: number; y: number; content: string; visible: boolean }>({ x: 0, y: 0, content: '', visible: false });

    // Feature toggles
    const showLegend = config.showLegend !== false;
    const showGrid = config.showGrid !== false;
    const showAxis = config.showAxis !== false;
    const showValues = config.showValues === true;
    const animate = config.animate !== false;
    const isCurved = config.tension !== false;
    const isThick = config.strokeWidth === true;

    // Style
    const accentColor = style.accentColor || '#F5C542';
    const textColor = style.textColor || '#ffffff';

    // Data Parsing with defaults - title undefined means use data.title, empty string means no title
    const chartTitle = title !== undefined ? title : (data.title || '');
    const xLabel = data.xLabel || '';
    const yLabel = data.yLabel || '';

    // Normalize Data to Series with defaults + auto-assign colors
    let series: any[] = [];
    if (type === 'line' || type === 'area') {
        if (data.series?.length > 0) {
            // Auto-assign colors to series if not provided
            series = data.series.map((s: any, idx: number) => ({
                ...s,
                color: s.color || DEFAULT_CHART_COLORS[idx % DEFAULT_CHART_COLORS.length]
            }));
        } else if (data.points?.length > 0) {
            series = [{ name: 'Data', data: data.points, color: accentColor }];
        } else {
            series = DEFAULT_LINE_DATA.series;
        }
    }

    // Auto-assign colors to bar points if not provided
    const rawBarPoints = (type === 'bar')
        ? (data.points?.length > 0 ? data.points : DEFAULT_BAR_DATA.points)
        : [];
    const barPoints = rawBarPoints.map((p: any, idx: number) => ({
        ...p,
        color: p.color || DEFAULT_CHART_COLORS[idx % DEFAULT_CHART_COLORS.length]
    }));

    // Determine Global Min/Max for Scaling (Line/Area)
    let minVal = 0;
    let maxVal = 100;

    if ((type === 'line' || type === 'area') && series.length > 0) {
        const allValues = series.flatMap(s => s.data.map((p: any) => p.y));
        if (allValues.length > 0) {
            minVal = Math.min(...allValues);
            maxVal = Math.max(...allValues);
            const range = maxVal - minVal;
            maxVal += range * 0.1;
            minVal = Math.max(0, minVal - (range * 0.1));
        }
    }

    // Generate percentage coordinates for both SVG and HTML overlay
    const getPercentCoordinates = (p: any, i: number, total: number) => {
        const x = (i / (total - 1)) * 100;
        const y = 100 - ((p.y - minVal) / (maxVal - minVal)) * 100;
        return { x, y };
    };

    const generatePath = (dataPoints: any[]) => {
        if (dataPoints.length === 0) return '';
        const coords = dataPoints.map((p, i) => getPercentCoordinates(p, i, dataPoints.length));

        if (!isCurved) {
            return `M ${coords.map(c => `${c.x},${c.y}`).join(' L ')}`;
        }

        let d = `M ${coords[0].x},${coords[0].y}`;
        for (let i = 0; i < coords.length - 1; i++) {
            const p0 = coords[i === 0 ? 0 : i - 1];
            const p1 = coords[i];
            const p2 = coords[i + 1];
            const p3 = coords[i + 2] || p2;

            const cp1x = p1.x + (p2.x - p0.x) * 0.15;
            const cp1y = p1.y + (p2.y - p0.y) * 0.15;
            const cp2x = p2.x - (p3.x - p1.x) * 0.15;
            const cp2y = p2.y - (p3.y - p1.y) * 0.15;

            d += ` C ${cp1x},${cp1y} ${cp2x},${cp2y} ${p2.x},${p2.y}`;
        }
        return d;
    };

    const showTooltip = (e: React.MouseEvent, content: string) => {
        const parentRect = (e.currentTarget.closest('.chart-container') as HTMLElement)?.getBoundingClientRect();
        if (parentRect) {
            setTooltip({
                x: e.clientX - parentRect.left,
                y: e.clientY - parentRect.top - 10,
                content,
                visible: true
            });
        }
    };

    const hideTooltip = () => setTooltip(prev => ({ ...prev, visible: false }));

    return (
        <BaseCard title={chartTitle}>
            <div className="w-full h-full flex flex-col relative p-4 chart-container">
                {/* Legend */}
                {showLegend && (
                    ((type === 'line' || type === 'area') && series.length > 1) ||
                    (type === 'bar' && barPoints.length > 1)
                ) && (
                        <div className="flex flex-wrap gap-4 mb-2">
                            {type === 'bar' ? (
                                barPoints.map((p: any, i: number) => (
                                    <div key={i} className="flex items-center gap-1.5">
                                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color || accentColor }} />
                                        <span className="text-[10px] text-muted-foreground font-medium">{p.x}</span>
                                    </div>
                                ))
                            ) : (
                                series.map((s: any, i: number) => (
                                    <div key={i} className="flex items-center gap-1.5">
                                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color || accentColor }} />
                                        <span className="text-[10px] text-muted-foreground font-medium">{s.name}</span>
                                    </div>
                                ))
                            )}
                        </div>
                    )}

                {/* Tooltip */}
                {tooltip.visible && (
                    <div
                        className="absolute z-50 px-2 py-1.5 bg-popover text-popover-foreground text-[10px] rounded border border-border shadow-xl pointer-events-none whitespace-nowrap"
                        style={{ left: tooltip.x, top: tooltip.y, transform: 'translate(-50%, -100%)' }}
                    >
                        {tooltip.content}
                    </div>
                )}

                {/* Chart Area */}
                <div className="flex-1 relative">
                    {/* Grid & Axis Lines */}
                    {showGrid && (
                        <div className="absolute inset-0 flex flex-col justify-between pointer-events-none opacity-30">
                            {[0, 1, 2, 3, 4].map(i => (
                                <div key={i} className="w-full border-t border-foreground" />
                            ))}
                        </div>
                    )}

                    {/* Y-Axis Labels */}
                    {showAxis && (type === 'line' || type === 'area') && (
                        <div className="absolute inset-y-0 left-0 flex flex-col justify-between text-[8px] text-muted-foreground pointer-events-none translate-y-1.5">
                            {[maxVal, (maxVal + minVal) * 0.75, (maxVal + minVal) * 0.5, (maxVal + minVal) * 0.25, minVal].map((val, i) => (
                                <span key={i} style={{ color: textColor, opacity: 0.5 }}>{Math.round(val)}</span>
                            ))}
                        </div>
                    )}

                    {/* SVG Layer for Line/Area (lines only) */}
                    <div className="absolute inset-0 ml-6 mb-4">
                        {type !== 'bar' ? (
                            <>
                                {/* SVG for line paths only */}
                                <svg className="w-full h-full overflow-visible" viewBox="0 0 100 100" preserveAspectRatio="none">
                                    {series.map((s: any, i: number) => {
                                        const pathD = generatePath(s.data);
                                        const fillColor = s.color || accentColor;
                                        return (
                                            <g key={i}>
                                                {/* Area fill (only for area charts) */}
                                                {type === 'area' && pathD && (
                                                    <path
                                                        d={`${pathD} L 100,100 L 0,100 Z`}
                                                        fill={fillColor}
                                                        fillOpacity={0.2}
                                                        className={cn("transition-all duration-300", animate && "animate-in fade-in duration-1000")}
                                                    />
                                                )}
                                                {/* Line stroke */}
                                                <path
                                                    d={pathD}
                                                    fill="none"
                                                    stroke={fillColor}
                                                    strokeWidth={isThick ? 3 : 1.5}
                                                    vectorEffect="non-scaling-stroke"
                                                    className={cn("transition-all duration-300", animate && "animate-in fade-in zoom-in-95 duration-1000")}
                                                    style={{ opacity: 0.9 }}
                                                />
                                            </g>
                                        );
                                    })}
                                </svg>

                                {/* HTML overlay for data points (fixed pixel size) */}
                                <div className="absolute inset-0">
                                    {series.map((s: any, seriesIdx: number) =>
                                        s.data.map((p: any, i: number) => {
                                            const coords = getPercentCoordinates(p, i, s.data.length);
                                            return (
                                                <div
                                                    key={`${seriesIdx}-${i}`}
                                                    className="absolute rounded-full cursor-crosshair hover:scale-150 transition-transform z-10 group"
                                                    style={{
                                                        left: `${coords.x}%`,
                                                        top: `${coords.y}%`,
                                                        width: '6px',
                                                        height: '6px',
                                                        backgroundColor: s.color || accentColor,
                                                        transform: 'translate(-50%, -50%)',
                                                        boxShadow: '0 1px 3px rgba(0,0,0,0.5)'
                                                    }}
                                                    onMouseEnter={(e) => showTooltip(e, `${s.name}: ${p.y} (${p.x})`)}
                                                    onMouseMove={(e) => showTooltip(e, `${s.name}: ${p.y} (${p.x})`)}
                                                    onMouseLeave={hideTooltip}
                                                />
                                            );
                                        })
                                    )}
                                </div>
                            </>
                        ) : (
                            /* Bar Chart with tooltips */
                            <div className="flex items-end justify-between h-full gap-1">
                                {barPoints.map((point: any, i: number) => {
                                    const maxY = Math.max(...barPoints.map((p: any) => p.y || 0));
                                    const heightPercent = ((point.y || 0) / (maxY * 1.1)) * 100;
                                    return (
                                        <div key={i} className="relative flex-1 h-full flex items-end group">
                                            <div
                                                className={cn(
                                                    "w-full rounded-t-sm transition-all duration-300 cursor-crosshair hover:brightness-125",
                                                    animate && "origin-bottom animate-in slide-in-from-bottom-2"
                                                )}
                                                style={{ height: `${heightPercent}%`, backgroundColor: point.color || accentColor, opacity: 0.85 }}
                                                onMouseEnter={(e) => showTooltip(e, `${point.x}: ${point.y}`)}
                                                onMouseMove={(e) => showTooltip(e, `${point.x}: ${point.y}`)}
                                                onMouseLeave={hideTooltip}
                                            >
                                                {showValues && (
                                                    <div className="absolute -top-4 left-1/2 -translate-x-1/2 text-[8px] font-bold" style={{ color: textColor }}>
                                                        {point.y}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    {/* X-Axis Labels */}
                    {showAxis && (
                        <div className="absolute bottom-0 left-6 right-0 flex justify-between text-[8px] text-muted-foreground mt-1">
                            {(type === 'bar' ? barPoints : series?.[0]?.data)?.map((p: any, i: number, arr: any[]) => (
                                (type === 'bar' || i === 0 || i === arr.length - 1 || i === Math.floor(arr.length / 2)) && (
                                    <span key={i} className={cn(type === 'bar' && "truncate text-center w-full")} style={{ color: textColor, opacity: 0.5 }}>{p.x}</span>
                                )
                            ))}
                        </div>
                    )}
                </div>

                {/* Axis Titles */}
                <div className="flex justify-between w-full mt-2 pl-6">
                    {yLabel && <div className="text-[8px] text-muted-foreground opacity-50 absolute -left-2 bottom-1/2 -rotate-90 origin-center">{yLabel}</div>}
                    {xLabel && <div className="text-[8px] text-muted-foreground opacity-50 ml-auto">{xLabel}</div>}
                </div>
            </div>
        </BaseCard>
    );
};
