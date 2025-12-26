import React from 'react';

export interface DividerCardProps {
    orientation?: 'horizontal' | 'vertical';
}

export const DividerCard: React.FC<DividerCardProps> = ({ orientation = 'horizontal' }) => {
    return (
        <div className="w-full h-full flex items-center justify-center p-2">
            {orientation === 'horizontal' ? (
                <div className="w-full h-px bg-white/10" />
            ) : (
                <div className="w-px h-full bg-white/10" />
            )}
        </div>
    );
};
