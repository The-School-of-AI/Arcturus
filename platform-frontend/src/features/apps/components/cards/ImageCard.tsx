import React from 'react';
import { BaseCard } from './BaseCard';
import { ImageIcon } from 'lucide-react';

export interface ImageCardProps {
    title?: string;
    src?: string;
    alt?: string;
}

export const ImageCard: React.FC<ImageCardProps> = ({ title, src, alt = "Dashboard Image" }) => {
    return (
        <BaseCard title={title}>
            <div className="w-full h-full flex items-center justify-center p-0 overflow-hidden bg-black/20 rounded">
                {src ? (
                    <img src={src} alt={alt} className="w-full h-full object-contain" />
                ) : (
                    <div className="flex flex-col items-center gap-2 opacity-20">
                        <ImageIcon className="w-8 h-8" />
                        <span className="text-[10px] uppercase font-bold tracking-widest">No Image</span>
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
