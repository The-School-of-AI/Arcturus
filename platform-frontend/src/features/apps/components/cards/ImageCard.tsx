import React from 'react';
import { BaseCard } from './BaseCard';
import { ImageIcon } from 'lucide-react';

export interface ImageCardProps {
    data?: any;
    config?: any;
    style?: any;
    title?: string; // Fallback for direct usage
}

export const ImageCard: React.FC<ImageCardProps> = ({ data = {}, config = {}, style = {}, title }) => {
    const url = data.url || "";
    const alt = data.alt || "Dashboard Image";
    const caption = data.caption || "";

    return (
        <BaseCard style={style}>
            <div className="w-full h-full flex flex-col p-0 overflow-hidden bg-black/20 rounded">
                <div className="flex-1 w-full h-full flex items-center justify-center relative group">
                    {url ? (
                        <img
                            src={url}
                            alt={alt}
                            className="w-full h-full object-contain transition-transform duration-500"
                        />
                    ) : (
                        <div className="flex flex-col items-center gap-2 opacity-20">
                            <ImageIcon className="w-8 h-8" />
                            <span className="text-[10px] uppercase font-bold tracking-widest text-white">No Image</span>
                        </div>
                    )}
                </div>
                {caption && config.showCaption !== false && (
                    <div className="px-3 py-1.5 bg-black/40 backdrop-blur-sm border-t border-white/5">
                        <p className="text-[10px] text-gray-400 italic text-center truncate">{caption}</p>
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
