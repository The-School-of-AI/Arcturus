/**
 * Dispatch component: maps slide_type → per-type renderer component.
 * Wraps the selected renderer in SlideFrame (16:9 container + theme bg + chrome).
 * Falls back to ContentSlide for unknown types.
 */

import { RENDERERS, SlideFrame } from './renderers';
import type { SlideTheme } from './renderers';
import type { SlideStyle } from './renderers/SlideFrame';
import { HtmlSlide } from './renderers/HtmlSlide';
import { Code2 } from 'lucide-react';
import type { Slide } from './normalizers';

interface SlideRendererProps {
  slide: Slide;
  theme: SlideTheme;
  slideIndex: number;
  totalSlides: number;
  isThumb?: boolean;
  /** Base URL for cached slide images */
  imageBaseUrl?: string;
  /** Set of slide IDs whose images are confirmed available */
  availableImageIds?: ReadonlySet<string>;
  /** Callback when the HTML edit button is clicked */
  onEditHtml?: () => void;
}

const TITLE_BG_TYPES = new Set(['title', 'section_divider']);

export function SlideRenderer({ slide, theme, slideIndex, totalSlides, isThumb = false, imageBaseUrl, availableImageIds, onEditHtml }: SlideRendererProps) {
  // HTML-first: if LLM provided full HTML, render it directly (bypass SlideFrame)
  if (slide.html) {
    return (
      <div
        className="relative w-full overflow-hidden select-none"
        style={{ aspectRatio: '16 / 9' }}
      >
        <HtmlSlide html={slide.html} isThumb={isThumb} />
        {/* Minimal slide counter for non-thumb views */}
        {!isThumb && totalSlides > 1 && (
          <div
            className="absolute bottom-2 right-3 text-xs font-mono tabular-nums"
            style={{ color: 'rgba(255,255,255,0.35)', zIndex: 10 }}
          >
            {slideIndex + 1} / {totalSlides}
          </div>
        )}
        {/* HTML edit button */}
        {!isThumb && onEditHtml && (
          <button
            onClick={(e) => { e.stopPropagation(); onEditHtml(); }}
            className="absolute top-2.5 right-10 p-1.5 rounded-md bg-black/60 backdrop-blur-sm border border-border text-white/50 hover:text-orange-400 hover:border-orange-400/40 hover:bg-black/80 transition-colors duration-150"
            style={{ zIndex: 20 }}
            title="Edit slide HTML"
          >
            <Code2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    );
  }

  // Fallback: structured renderers for old slides without html field
  const Renderer = RENDERERS[slide.slide_type] ?? RENDERERS.content;
  const useTitleBg = TITLE_BG_TYPES.has(slide.slide_type);
  // Prefer new slide_style; fall back to old visual_style for backward compat
  const slideStyle = (slide.metadata?.slide_style ?? slide.metadata?.visual_style) as SlideStyle | undefined;

  return (
    <SlideFrame
      theme={theme}
      slideIndex={slideIndex}
      totalSlides={totalSlides}
      isThumb={isThumb}
      useTitleBg={useTitleBg}
      slideStyle={slideStyle}
    >
      <Renderer
        slide={slide}
        theme={theme}
        slideIndex={slideIndex}
        totalSlides={totalSlides}
        isThumb={isThumb}
        imageBaseUrl={imageBaseUrl}
        availableImageIds={availableImageIds}
      />
    </SlideFrame>
  );
}

export type { SlideRendererProps };
