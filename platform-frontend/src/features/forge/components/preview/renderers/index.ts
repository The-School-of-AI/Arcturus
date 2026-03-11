/**
 * Barrel export + renderer dispatch map.
 *
 * Mirrors the _RENDERERS dispatch table from exporter.py:2295-2312.
 * Each key is a slide_type string, and the value is the React component.
 * Includes "stats" → StatSlide alias (exporter.py:2308).
 */

import type { FC } from 'react';
import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';

import { TitleSlide } from './TitleSlide';
import { ContentSlide } from './ContentSlide';
import { TwoColumnSlide } from './TwoColumnSlide';
import { ComparisonSlide } from './ComparisonSlide';
import { TimelineSlide } from './TimelineSlide';
import { ChartSlide } from './ChartSlide';
import { ImageTextSlide } from './ImageTextSlide';
import { ImageFullSlide } from './ImageFullSlide';
import { QuoteSlide } from './QuoteSlide';
import { CodeSlide } from './CodeSlide';
import { TeamSlide } from './TeamSlide';
import { StatSlide } from './StatSlide';
import { SectionDividerSlide } from './SectionDividerSlide';
import { AgendaSlide } from './AgendaSlide';
import { TableSlide } from './TableSlide';

export interface RendererProps {
  slide: Slide;
  theme: SlideTheme;
  slideIndex: number;
  totalSlides: number;
  isThumb?: boolean;
  /** Base URL for cached slide images, e.g. "/api/studio/{id}/images" */
  imageBaseUrl?: string;
  /** Set of slide IDs whose images are confirmed available on the server */
  availableImageIds?: ReadonlySet<string>;
}

/**
 * Dispatch map: slide_type → renderer component.
 * 15 unique types + "stats" alias = 16 entries total.
 */
export const RENDERERS: Record<string, FC<RendererProps>> = {
  title: TitleSlide,
  content: ContentSlide,
  two_column: TwoColumnSlide,
  comparison: ComparisonSlide,
  timeline: TimelineSlide,
  chart: ChartSlide,
  image_text: ImageTextSlide,
  image_full: ImageFullSlide,
  quote: QuoteSlide,
  code: CodeSlide,
  team: TeamSlide,
  stat: StatSlide,
  stats: StatSlide, // alias (exporter.py:2308)
  section_divider: SectionDividerSlide,
  agenda: AgendaSlide,
  table: TableSlide,
};

export { SlideFrame } from './SlideFrame';
export type { SlideTheme, SlideThemeColors } from './SlideFrame';
