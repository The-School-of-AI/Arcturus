/**
 * Dispatch component: maps slide_type → per-type renderer component.
 * Wraps the selected renderer in SlideFrame (16:9 container + theme bg + chrome).
 * Falls back to ContentSlide for unknown types.
 */

import { RENDERERS, SlideFrame } from './renderers';
import type { SlideTheme } from './renderers';
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
}

const TITLE_BG_TYPES = new Set(['title', 'section_divider']);

export function SlideRenderer({ slide, theme, slideIndex, totalSlides, isThumb = false, imageBaseUrl, availableImageIds }: SlideRendererProps) {
  const Renderer = RENDERERS[slide.slide_type] ?? RENDERERS.content;
  const useTitleBg = TITLE_BG_TYPES.has(slide.slide_type);

  return (
    <SlideFrame
      theme={theme}
      slideIndex={slideIndex}
      totalSlides={totalSlides}
      isThumb={isThumb}
      useTitleBg={useTitleBg}
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
