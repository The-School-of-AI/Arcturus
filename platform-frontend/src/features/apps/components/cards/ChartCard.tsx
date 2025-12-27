import React from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

export interface ChartCardProps {
    title: string;
    type: 'line' | 'bar' | 'area';
    data?: any;
    config?: any;
    style?: any;
}

export const ChartCard: React.FC<ChartCardProps> = ({
    title,
    type,
    data = {},
    config = {},
    style = {}
}) => {
    // Feature toggles
    const showLegend = config.showLegend !== false;
    const showGrid = config.showGrid !== false;
    const showAxis = config.showAxis !== false;
    const showValues = config.showValues === true;
    const animate = config.animate !== false;
    const isCurved = config.tension !== false; // Default to curved
    const isThick = config.strokeWidth === true; // "Thick Lines" toggle

    // Style
    const accentColor = style.accentColor || '#eaff00';
    const textColor = style.textColor || '#ffffff';

    // Data Parsing
    const chartTitle = title || data.title || '';
    const xLabel = data.xLabel || '';
    const yLabel = data.yLabel || '';

    // Normalize Data to Series
    let series: any[] = [];
    if (type === 'line' || type === 'area') {
        if (data.series) {
            series = data.series;
        } else if (data.points) {
            // Legacy/Single series fallback
            series = [{ name: 'Data', data: data.points, color: accentColor }];
        }
    } else {
        // Bar chart logic remains mostly single series for now, or unified later
        // For now, mapping bar chart points to a single series structure for unified scaling if needed
        // But render logic below handles bar separately.
    }

    // Determine Global Min/Max for Scaling (Line/Area)
    let minVal = 0;
    let maxVal = 100;

    if ((type === 'line' || type === 'area') && series.length > 0) {
        const allValues = series.flatMap(s => s.data.map((p: any) => p.y));
        if (allValues.length > 0) {
            minVal = Math.min(...allValues);
            maxVal = Math.max(...allValues);
            // Add padding
            const range = maxVal - minVal;
            maxVal += range * 0.1;
            minVal = Math.max(0, minVal - (range * 0.1)); // Don't go below 0 unless data is negative? Assuming 0 baseline for now.
        }
    }

    // Generate Path Helpers
    const getCoordinates = (p: any, i: number, total: number) => {
        const x = (i / (total - 1)) * 100;
        const y = 100 - ((p.y - minVal) / (maxVal - minVal)) * 100;
        return { x, y };
    };

    const generatePath = (dataPoints: any[]) => {
        if (dataPoints.length === 0) return '';

        const coords = dataPoints.map((p, i) => getCoordinates(p, i, dataPoints.length));

        if (!isCurved) {
            return `M ${coords.map(c => `${c.x},${c.y}`).join(' L ')}`;
        }

        // Catmull-Rom to Cubic Bezier conversion logic or simple smoothing
        // Simple smoothing strategy: control points based on neighbors
        let d = `M ${coords[0].x},${coords[0].y}`;
        for (let i = 0; i < coords.length - 1; i++) {
            const p0 = coords[i === 0 ? 0 : i - 1];
            const p1 = coords[i];
            const p2 = coords[i + 1];
            const p3 = coords[i + 2] || p2;

            const cp1x = p1.x + (p2.x - p0.x) * 0.15; // Tension factor
            const cp1y = p1.y + (p2.y - p0.y) * 0.15;
            const cp2x = p2.x - (p3.x - p1.x) * 0.15;
            const cp2y = p2.y - (p3.y - p1.y) * 0.15;

            d += ` C ${cp1x},${cp1y} ${cp2x},${cp2y} ${p2.x},${p2.y}`;
        }
        return d;
    };

    return (
        <BaseCard title={chartTitle}>
            <div className="w-full h-full flex flex-col relative p-4">
                {/* Legend */}
                {showLegend && series.length > 1 && (type === 'line' || type === 'area') && (
                    <div className="flex flex-wrap gap-4 mb-2">
                        {series.map((s, i) => (
                            <div key={i} className="flex items-center gap-1.5">
                                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color || accentColor }} />
                                <span className="text-[10px] text-muted-foreground font-medium">{s.name}</span>
                            </div>
                        ))}
                    </div>
                )}

                {/* Chart Area */}
                <div className="flex-1 relative">
                    {/* Grid & Axis Lines */}
                    {showGrid && (
                        <div className="absolute inset-0 flex flex-col justify-between pointer-events-none opacity-20">
                            {[0, 1, 2, 3, 4].map(i => (
                                <div key={i} className="w-full border-t border-white" />
                            ))}
                        </div>
                    )}

                    {/* Y-Axis Labels (Overlay) */}
                    {showAxis && (type === 'line' || type === 'area') && (
                        <div className="absolute inset-y-0 left-0 flex flex-col justify-between text-[8px] text-muted-foreground pointer-events-none translate-y-1.5">
                            {[maxVal, (maxVal + minVal) * 0.75, (maxVal + minVal) * 0.5, (maxVal + minVal) * 0.25, minVal].map((val, i) => (
                                <span key={i} style={{ color: textColor, opacity: 0.5 }}>{Math.round(val)}</span>
                            ))}
                        </div>
                    )}

                    {/* SVG Layer */}
                    <div className="absolute inset-0 ml-6 mb-4"> {/* Margin for axes */}
                        {type !== 'bar' ? (
                            <svg className="w-full h-full overflow-visible" viewBox="0 0 100 100" preserveAspectRatio="none">
                                {series.map((s: any, i: number) => (
                                    <path
                                        key={i}
                                        d={generatePath(s.data)}
                                        fill="none"
                                        stroke={s.color || accentColor}
                                        strokeWidth={isThick ? 3 : 1.5}
                                        vectorEffect="non-scaling-stroke"
                                        className={cn("transition-all duration-300", animate && "animate-in fade-in zoom-in-95 duration-1000")}
                                        style={{ opacity: 0.9 }}
                                    />
                                ))}
                            </svg>
                        ) : (
                            /* Bar Chart Logic (Simplified from original for now, keeping separate if needed or could unify) */
                            <div className="flex items-end justify-between h-full gap-1">
                                {(data.points || []).map((point: any, i: number) => {
                                    const heightPercent = ((point.y || 0) / (Math.max(...(data.points || []).map((p: any) => p.y || 0)) * 1.1)) * 100;
                                    return (
                                        <div key={i} className="relative flex-1 h-full flex items-end group">
                                            <div
                                                className={cn("w-full rounded-t-sm transition-all duration-500 hover:opacity-100", animate && "origin-bottom animate-in slide-in-from-bottom-2")}
                                                style={{ height: `${heightPercent}%`, backgroundColor: point.color || accentColor, opacity: 0.8 }}
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
                            {/* Simplistic X-Axis strategy: show first and last, or distributed? */}
                            {/* Let's show labels from the first series for now */}
                            {series?.[0]?.data?.map((p: any, i: number, arr: any[]) => (
                                (i === 0 || i === arr.length - 1 || i === Math.floor(arr.length / 2)) && (
                                    <span key={i} style={{ color: textColor, opacity: 0.5 }}>{p.x}</span>
                                )
                            ))}
                            {type === 'bar' && (data.points || []).map((p: any, i: number) => (
                                <span key={i} className="truncate text-center w-full" style={{ color: textColor, opacity: 0.5 }}>{p.x}</span>
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
