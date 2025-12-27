import React from 'react';
import { BaseCard } from './BaseCard';
import { ImageIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

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
            <div className="w-full h-full flex flex-col overflow-hidden bg-black/20 rounded">
                {/* Image container - uses absolute positioning to prevent stretching */}
                <div className="flex-1 relative min-h-0">
                    {url ? (
                        <img
                            src={url}
                            alt={alt}
                            className={cn(
                                "absolute inset-0 transition-transform duration-500",
                                // Both modes use object-fit to ALWAYS preserve aspect ratio
                                // Fill mode: cover (crops to fill, centered)
                                // Contain mode: contain (fits inside, may have letterboxing)
                                config.fillArea
                                    ? "w-full h-full object-cover object-center"
                                    : "w-full h-full object-contain object-center"
                            )}
                        />
                    ) : (
                        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 opacity-20">
                            <ImageIcon className="w-8 h-8" />
                            <span className="text-[10px] uppercase font-bold tracking-widest text-white">No Image</span>
                        </div>
                    )}
                </div>
                {caption && config.showCaption !== false && (
                    <div className="px-3 py-1.5 bg-black/40 backdrop-blur-sm border-t border-white/5 shrink-0">
                        <p className="text-[10px] text-gray-400 italic text-center truncate">{caption}</p>
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
