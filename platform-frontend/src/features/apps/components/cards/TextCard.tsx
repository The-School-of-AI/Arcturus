import React from 'react';
import { BaseCard } from './BaseCard';

export interface TextCardProps {
    text?: string;
    textColor?: string;
    cardId?: string;
    autoFit?: boolean;
}

export const TextCard: React.FC<TextCardProps> = ({
    text = 'Basic paragraph text block. Select to edit.',
    textColor,
    cardId,
    autoFit = true
}) => {
    return (
        <BaseCard cardId={cardId} autoFit={autoFit}>
            <div
                className="text-sm text-foreground/80 whitespace-pre-wrap"
                style={textColor ? { color: textColor } : {}}
            >
                {text}
            </div>
        </BaseCard>
    );
};
