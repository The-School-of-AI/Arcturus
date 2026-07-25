import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { SlideRenderer } from './SlideRenderer';
import type { SlideTheme } from './renderers';
import type { Slide } from './normalizers';

interface SlideFilmstripProps {
  slides: Slide[];
  theme: SlideTheme;
  currentIndex: number;
  onSelect: (index: number) => void;
  imageBaseUrl?: string;
  availableImageIds?: ReadonlySet<string>;
}

/** Canonical render size for thumbnails (scaled down) */
const THUMB_W = 960;
const THUMB_H = 540;
const SCALE = 0.22;
const DISPLAY_W = Math.round(THUMB_W * SCALE);  // ~211px
const DISPLAY_H = Math.round(THUMB_H * SCALE);  // ~119px

export function SlideFilmstrip({ slides, theme, currentIndex, onSelect, imageBaseUrl, availableImageIds }: SlideFilmstripProps) {
  return (
    <ScrollArea className="h-full w-56 border-r border-border[0.06] bg-[#08090b] shrink-0">
      <div className="p-3 space-y-2">
        {slides.map((slide, i) => (
          <button
            key={slide.id || i}
            onClick={() => onSelect(i)}
            className={cn(
              'w-full rounded-lg overflow-hidden transition-all duration-200',
              i === currentIndex
                ? 'ring-2 ring-blue-500/70 shadow-sm shadow-blue-500/10 scale-[1.02]'
                : 'ring-1 ring-white/[0.06] hover:ring-white/[0.12] opacity-50 hover:opacity-90 hover:shadow-md'
            )}
          >
            {/* Slide number */}
            <div className={cn(
              'text-2xs font-mono text-left px-1.5 py-0.5',
              i === currentIndex ? 'text-blue-400/80' : 'text-white/20'
            )}>
              {i + 1}
            </div>
            {/* Scaled slide */}
            <div
              style={{
                width: DISPLAY_W,
                height: DISPLAY_H,
                overflow: 'hidden',
                position: 'relative',
              }}
            >
              <div
                style={{
                  width: THUMB_W,
                  height: THUMB_H,
                  transform: `scale(${SCALE})`,
                  transformOrigin: 'top left',
                  pointerEvents: 'none',
                }}
              >
                <SlideRenderer
                  slide={slide}
                  theme={theme}
                  slideIndex={i}
                  totalSlides={slides.length}
                  imageBaseUrl={imageBaseUrl}
                  availableImageIds={availableImageIds}
                />
              </div>
            </div>
          </button>
        ))}
      </div>
    </ScrollArea>
  );
}
