import React from 'react';
import { cn } from '@/lib/utils';

export interface BaseCardProps {
    title?: string;
    className?: string;
    children: React.ReactNode;
    headerAction?: React.ReactNode;
}

export const BaseCard: React.FC<BaseCardProps> = ({ title, className, children, headerAction }) => {
    return (
        <div className={cn("w-full h-full flex flex-col bg-transparent", className)}>
            {title && (
                <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 shrink-0">
                    <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider truncate">{title}</h3>
                    {headerAction && <div>{headerAction}</div>}
                </div>
            )}
            <div className="flex-1 overflow-auto p-4 relative min-h-0">
                {children}
            </div>
        </div>
    );
};
