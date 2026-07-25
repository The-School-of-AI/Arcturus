import React, { useState } from 'react';
import { useTheme } from '@/components/theme';

interface ImageItem {
    src: string;
    alt?: string;
    caption?: string;
}

interface ImageViewerWidgetProps {
    images: ImageItem[];
    title?: string;
    layout?: 'grid' | 'carousel';
}

const ImageViewerWidget: React.FC<ImageViewerWidgetProps> = ({ images = [], title, layout = 'grid' }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';
    const [selected, setSelected] = useState<number | null>(null);

    if (layout === 'carousel') {
        const idx = selected ?? 0;
        const img = images[idx];
        return (
            <div className={`w-full rounded-lg border overflow-hidden ${isDark ? 'bg-gray-800/50 border-gray-700' : 'bg-white border-gray-200 shadow-sm'}`}>
                {title && <div className={`px-4 py-2 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}><h3 className={`text-sm font-semibold ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{title}</h3></div>}
                {img && (
                    <div className="relative">
                        <img src={img.src} alt={img.alt || ''} className="w-full h-64 object-contain bg-black/20" />
                        {img.caption && <p className={`text-xs p-2 text-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{img.caption}</p>}
                    </div>
                )}
                {images.length > 1 && (
                    <div className={`flex items-center justify-center gap-2 p-2 border-t ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                        <button onClick={() => setSelected(Math.max(0, idx - 1))} disabled={idx === 0} className="px-2 py-0.5 text-xs rounded border disabled:opacity-30 text-muted-foreground">←</button>
                        <span className="text-xs text-muted-foreground">{idx + 1}/{images.length}</span>
                        <button onClick={() => setSelected(Math.min(images.length - 1, idx + 1))} disabled={idx >= images.length - 1} className="px-2 py-0.5 text-xs rounded border disabled:opacity-30 text-muted-foreground">→</button>
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className={`w-full rounded-lg border overflow-hidden ${isDark ? 'bg-gray-800/50 border-gray-700' : 'bg-white border-gray-200 shadow-sm'}`}>
            {title && <div className={`px-4 py-2 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}><h3 className={`text-sm font-semibold ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{title}</h3></div>}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 p-3">
                {images.map((img, i) => (
                    <div key={i} className={`rounded-md overflow-hidden border cursor-pointer hover:ring-2 hover:ring-primary/40 transition-all ${isDark ? 'border-gray-700' : 'border-gray-200'}`} onClick={() => setSelected(selected === i ? null : i)}>
                        <img src={img.src} alt={img.alt || ''} className="w-full h-32 object-cover" />
                        {img.caption && <p className={`text-xs p-1.5 truncate ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{img.caption}</p>}
                    </div>
                ))}
            </div>
        </div>
    );
};

export default ImageViewerWidget;
