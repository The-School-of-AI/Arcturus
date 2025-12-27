import React from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';

export interface ScatterCardProps {
    title: string;
    data?: any;
    config?: any;
    style?: any;
    isInteractive?: boolean;
}

export const ScatterCard: React.FC<ScatterCardProps> = ({
    title,
    data = {},
    config = {},
    style = {},
    isInteractive = false
}) => {
    const accentColor = style.accentColor || '#eaff00';

    // Sample data
    const points = data.points || Array.from({ length: 15 }, (_, i) => ({
        x: Math.random() * 100,
        y: Math.random() * 100,
        label: `Pt ${i + 1}`,
        value: Math.random() * 100
    }));

    const xLabel = data.xLabel || 'X Axis';
    const yLabel = data.yLabel || 'Y Axis';

    return (
        <BaseCard title={title}>
            <div className="w-full h-full flex flex-col p-4 relative select-none">
                <div className="flex-1 relative border-l border-b border-white/10 mb-5 ml-5">
                    {/* Grid lines */}
                    <div className="absolute inset-0 flex flex-col justify-between opacity-10 pointer-events-none">
                        {[0, 1, 2, 3, 4].map(i => <div key={i} className="w-full border-t border-white" />)}
                    </div>
                    <div className="absolute inset-0 flex justify-between opacity-10 pointer-events-none">
                        {[0, 1, 2, 3, 4].map(i => <div key={i} className="h-full border-r border-white" />)}
                    </div>

                    {/* Points */}
                    {points.map((pt: any, i: number) => (
                        <div
                            key={i}
                            className="absolute w-2 h-2 rounded-full hover:scale-150 hover:ring-2 ring-white/20 transition-all cursor-crosshair group z-10"
                            style={{
                                left: `${pt.x}%`,
                                bottom: `${pt.y}%`,
                                backgroundColor: pt.color || accentColor,
                                transform: 'translate(-50%, 50%)'
                            }}
                        >
                            <div className="opacity-0 group-hover:opacity-100 absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-black/90 text-white text-[9px] rounded pointer-events-none whitespace-nowrap z-50 border border-white/10 shadow-xl">
                                <div className="font-bold mb-0.5">{pt.label}</div>
                                <div className="text-gray-400">x: {Math.round(pt.x)}, y: {Math.round(pt.y)}</div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Labels */}
                <div className="absolute bottom-0 left-6 right-0 text-center text-[9px] text-muted-foreground">{xLabel}</div>
                <div className="absolute top-0 bottom-6 left-0 flex items-center justify-center w-4">
                    <span className="-rotate-90 whitespace-nowrap text-[9px] text-muted-foreground">{yLabel}</span>
                </div>
            </div>
        </BaseCard>
    );
};
