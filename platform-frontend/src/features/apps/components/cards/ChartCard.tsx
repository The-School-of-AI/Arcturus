import React from 'react';
import { BaseCard } from './BaseCard';

export interface ChartCardProps {
    title: string;
    type: 'line' | 'bar' | 'area';
}

export const ChartCard: React.FC<ChartCardProps> = ({ title, type }) => {
    return (
        <BaseCard>
            <div className="w-full h-full flex items-center justify-center opacity-50 relative">
                {/* Simulated Chart Placeholder */}
                <svg className="w-full h-full text-primary" viewBox="0 0 100 40" preserveAspectRatio="none">
                    {type === 'line' && (
                        <path d="M0,35 Q20,10 40,25 T80,15 T100,5" fill="none" stroke="currentColor" strokeWidth="2" />
                    )}
                    {type === 'area' && (
                        <path d="M0,35 Q20,10 40,25 T80,15 T100,5 L100,40 L0,40 Z" fill="currentColor" fillOpacity="0.2" stroke="currentColor" strokeWidth="2" />
                    )}
                    {type === 'bar' && (
                        <>
                            <rect x="5" y="20" width="10" height="20" fill="currentColor" />
                            <rect x="25" y="10" width="10" height="30" fill="currentColor" />
                            <rect x="45" y="25" width="10" height="15" fill="currentColor" />
                            <rect x="65" y="5" width="10" height="35" fill="currentColor" />
                            <rect x="85" y="15" width="10" height="25" fill="currentColor" />
                        </>
                    )}
                </svg>
                <div className="absolute bottom-0 left-0 right-0 h-px bg-white/10" />
                <div className="absolute left-0 top-0 bottom-0 w-px bg-white/10" />
            </div>
        </BaseCard>
    );
};
