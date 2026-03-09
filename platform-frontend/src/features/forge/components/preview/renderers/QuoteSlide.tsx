import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement } from '../normalizers';
import { QuoteElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function QuoteSlide({ slide, theme, isThumb }: Props) {
  const quoteEl = findElement(slide, 'quote');
  const bodyEl = findElement(slide, 'body');

  const quoteText = quoteEl?.content ?? '';
  const attribution = bodyEl?.content && typeof bodyEl.content === 'string' ? bodyEl.content : '';

  return (
    <div className="flex items-center justify-center h-full">
      <QuoteElement quote={quoteText} attribution={attribution} theme={theme} isThumb={isThumb} />
    </div>
  );
}
