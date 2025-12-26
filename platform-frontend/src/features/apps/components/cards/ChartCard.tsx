import React from 'react';
import { BaseCard } from './BaseCard';

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
    const animate = config.animate !== false;

    // Get data points from data prop
    const points = data.points || [];
    const xLabel = data.xLabel || '';
    const yLabel = data.yLabel || '';

    return (
        <BaseCard title={title}>
            <div className="w-full h-full flex flex-col relative">
                {/* Chart area */}
                <div className="flex-1 flex items-center justify-center relative">
                    {/* Grid lines */}
                    {showGrid && (
                        <>
                            <div className="absolute inset-0 pointer-events-none">
                                {[25, 50, 75].map(y => (
                                    <div key={y} className="absolute left-0 right-0 border-t border-white/5" style={{ top: `${y}%` }} />
                                ))}
                                {[25, 50, 75].map(x => (
                                    <div key={x} className="absolute top-0 bottom-0 border-l border-white/5" style={{ left: `${x}%` }} />
                                ))}
                            </div>
                        </>
                    )}

                    {/* Chart SVG */}
                    <svg className="w-full h-full text-primary" viewBox="0 0 100 40" preserveAspectRatio="none">
                        {type === 'line' && (
                            <path
                                d="M0,35 Q20,10 40,25 T80,15 T100,5"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                className={animate ? "animate-pulse" : ""}
                            />
                        )}
                        {type === 'area' && (
                            <path
                                d="M0,35 Q20,10 40,25 T80,15 T100,5 L100,40 L0,40 Z"
                                fill="currentColor"
                                fillOpacity="0.2"
                                stroke="currentColor"
                                strokeWidth="2"
                                className={animate ? "animate-pulse" : ""}
                            />
                        )}
                        {type === 'bar' && (
                            <>
                                <rect x="5" y="20" width="10" height="20" fill="currentColor" className={animate ? "animate-pulse" : ""} />
                                <rect x="25" y="10" width="10" height="30" fill="currentColor" className={animate ? "animate-pulse" : ""} />
                                <rect x="45" y="25" width="10" height="15" fill="currentColor" className={animate ? "animate-pulse" : ""} />
                                <rect x="65" y="5" width="10" height="35" fill="currentColor" className={animate ? "animate-pulse" : ""} />
                                <rect x="85" y="15" width="10" height="25" fill="currentColor" className={animate ? "animate-pulse" : ""} />
                            </>
                        )}
                    </svg>

                    {/* Axis lines */}
                    {showAxis && (
                        <>
                            <div className="absolute bottom-0 left-0 right-0 h-px bg-white/20" />
                            <div className="absolute left-0 top-0 bottom-0 w-px bg-white/20" />
                        </>
                    )}
                </div>

                {/* Axis labels */}
                {showAxis && (xLabel || yLabel) && (
                    <div className="flex justify-between text-[8px] text-muted-foreground mt-1">
                        {yLabel && <span className="opacity-50">{yLabel}</span>}
                        {xLabel && <span className="opacity-50">{xLabel}</span>}
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
