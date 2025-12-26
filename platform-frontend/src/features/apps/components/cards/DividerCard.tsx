import React from 'react';

export interface DividerCardProps {
    orientation?: 'horizontal' | 'vertical';
    config?: any;
    data?: any;
    style?: any;
}

export const DividerCard: React.FC<DividerCardProps> = ({ orientation = 'horizontal', style = {} }) => {
    const borderColor = style.accentColor || style.borderColor || 'rgba(255,255,255,0.1)';
    
    return (
        <div className="w-full h-full flex items-center justify-center p-2">
            {orientation === 'horizontal' ? (
                <div className="w-full h-px" style={{ backgroundColor: borderColor }} />
            ) : (
                <div className="w-px h-full" style={{ backgroundColor: borderColor }} />
            )}
        </div>
    );
};
