import React from 'react';
import { cn } from '@/lib/utils';
import { AutoHeightWrapper } from './AutoHeightWrapper';

export interface BaseCardProps {
    title?: string;
    className?: string;
    children: React.ReactNode;
    headerAction?: React.ReactNode;
    style?: React.CSSProperties;
    textColor?: string;
    cardId?: string;
    autoFit?: boolean;
}

export const BaseCard: React.FC<BaseCardProps> = ({
    title,
    className,
    children,
    headerAction,
    style,
    textColor,
    cardId,
    autoFit = true
}) => {
    // When autoFit is true and we have a cardId, use AutoHeightWrapper
    // Otherwise, just render the content with scroll

    const contentArea = (
        <div className="flex-1 p-4 relative min-h-0 overflow-auto">
            {children}
        </div>
    );

    const cardContent = (
        <div
            className={cn("w-full h-full flex flex-col bg-transparent overflow-hidden", className)}
            style={style}
        >
            {title && (
                <div className="flex items-center justify-between px-4 py-4 border-b border-border/50 shrink-0">
                    <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider truncate" style={textColor ? { color: textColor } : {}}>{title}</h3>
                    {headerAction && <div>{headerAction}</div>}
                </div>
            )}
            {contentArea}
        </div>
    );

    if (cardId && autoFit) {
        return (
            <AutoHeightWrapper cardId={cardId} enabled={autoFit}>
                {cardContent}
            </AutoHeightWrapper>
        );
    }

    return cardContent;
};
