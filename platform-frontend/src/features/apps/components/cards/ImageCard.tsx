import React from 'react';
import { ImageIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ImageCardProps {
    data?: any;
    config?: any;
    style?: any;
    title?: string; // Fallback for direct usage
}

export const ImageCard: React.FC<ImageCardProps> = ({ data = {}, config = {}, style = {} }) => {
    const url = data.url || "";
    const alt = data.alt || "Dashboard Image";
    const caption = data.caption || "";

    return (
        <div className="w-full h-full flex flex-col overflow-hidden relative" style={style}>
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
                            (config.fillArea || data.fill)
                                ? "w-full h-full object-cover object-center"
                                : "w-full h-full object-contain object-center"
                        )}
                    />
                ) : (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 opacity-20">
                        <ImageIcon className="w-8 h-8" />
                        <span className="text-[10px] uppercase font-bold tracking-widest text-foreground">No Image</span>
                    </div>
                )}
            </div>
            {caption && config.showCaption !== false && (
                <div className="absolute bottom-0 left-0 right-0 px-3 py-2 bg-gradient-to-t from-black/60 to-transparent">
                    <p className="text-[10px] text-foreground/90 italic text-center truncate drop-shadow-md">{caption}</p>
                </div>
            )}
        </div>
    );
};
