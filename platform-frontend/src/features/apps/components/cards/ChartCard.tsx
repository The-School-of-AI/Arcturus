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
    const showValues = config.showValues === true; // Default false for values
    const animate = config.animate !== false;

    // Get data points from data prop
    const points = data.points || [];
    const xLabel = data.xLabel || '';
    const yLabel = data.yLabel || '';
    const chartTitle = title || data.title || '';

    // Style
    const accentColor = style.accentColor || '#eaff00';
    const textColor = style.textColor || '#ffffff';

    // Calculate scaling for bars
    const maxY = points.length > 0
        ? Math.max(...points.map((p: any) => p.y || 0)) * 1.1 // Add 10% headroom
        : 100;

    return (
        <BaseCard title={chartTitle}>
            <div className="w-full h-full flex flex-col relative p-2">
                {/* Chart area */}
                <div className="flex-1 flex items-end justify-center relative gap-2">
                    {/* Grid lines */}
                    {showGrid && (
                        <div className="absolute inset-0 pointer-events-none z-0">
                            {[0.25, 0.5, 0.75].map(ratio => (
                                <div
                                    key={ratio}
                                    className="absolute left-0 right-0 border-t border-white/5"
                                    style={{ bottom: `${ratio * 100}%` }}
                                />
                            ))}
                        </div>
                    )}

                    {/* render bars dynamically */}
                    {type === 'bar' && points.map((point: any, i: number) => {
                        const heightPercent = maxY > 0 ? (point.y / maxY) * 100 : 0;
                        return (
                            <div key={i} className="group relative flex-1 flex flex-col items-center justify-end h-full z-10">
                                {/* Value Label */}
                                {showValues && (
                                    <div
                                        className="text-[8px] font-bold mb-1 opacity-80"
                                        style={{ color: textColor }}
                                    >
                                        {point.y}
                                    </div>
                                )}
                                {/* Bar */}
                                <div
                                    className={cn("w-full rounded-t-sm transition-all duration-500", animate && "origin-bottom animate-in slide-in-from-bottom-4 fade-in")}
                                    style={{
                                        height: `${heightPercent}%`,
                                        backgroundColor: point.color || accentColor,
                                        opacity: 0.9
                                    }}
                                />
                                {/* X-Axis Label */}
                                {showAxis && (
                                    <div className="text-[8px] text-muted-foreground mt-1 truncate w-full text-center">
                                        {point.x}
                                    </div>
                                )}
                            </div>
                        );
                    })}

                    {/* Fallback for other chart types using SVG for now (Line/Area not yet fully dynamic in this pass) */}
                    {type !== 'bar' && (
                        <svg className="w-full h-full text-primary z-10" viewBox="0 0 100 40" preserveAspectRatio="none">
                            {type === 'line' && (
                                <path
                                    d="M0,35 Q20,10 40,25 T80,15 T100,5"
                                    fill="none"
                                    stroke={accentColor}
                                    strokeWidth="2"
                                    className={animate ? "animate-pulse" : ""}
                                />
                            )}
                            {type === 'area' && (
                                <>
                                    <path
                                        d="M0,35 Q20,10 40,25 T80,15 T100,5 L100,40 L0,40 Z"
                                        fill={accentColor}
                                        fillOpacity="0.2"
                                        style={{ stroke: 'none' }}
                                        className={animate ? "animate-pulse" : ""}
                                    />
                                    <path
                                        d="M0,35 Q20,10 40,25 T80,15 T100,5"
                                        fill="none"
                                        stroke={accentColor}
                                        strokeWidth="2"
                                        className={animate ? "animate-pulse" : ""}
                                    />
                                </>
                            )}
                        </svg>
                    )}

                    {/* Axis container overrides */}
                    {showAxis && type !== 'bar' && (
                        <>
                            <div className="absolute bottom-0 left-0 right-0 h-px bg-white/20" />
                            <div className="absolute left-0 top-0 bottom-0 w-px bg-white/20" />
                        </>
                    )}
                </div>

                {/* Additional Axis labels for non-bar charts or global Y label */}
                {showAxis && (
                    <div className="flex justify-between w-full mt-1">
                        {yLabel && <div className="text-[8px] text-muted-foreground opacity-50">{yLabel}</div>}
                        {xLabel && type !== 'bar' && <div className="text-[8px] text-muted-foreground opacity-50">{xLabel}</div>}
                        {type === 'bar' && xLabel && <div className="text-[8px] text-muted-foreground opacity-50 ml-auto">{xLabel}</div>}
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
