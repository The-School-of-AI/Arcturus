import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement } from '../normalizers';
import { KickerElement, TakeawayElement, ChartPlaceholder, BodyElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function ChartSlide({ slide, theme, isThumb }: Props) {
  const kickerEl = findElement(slide, 'kicker');
  const chartEl = findElement(slide, 'chart');
  const bodyEl = findElement(slide, 'body');
  const takeawayEl = findElement(slide, 'takeaway');

  return (
    <div className={`flex flex-col h-full ${isThumb ? 'p-2' : 'p-[6%]'}`}>
      {kickerEl?.content && (
        <KickerElement content={kickerEl.content} theme={theme} isThumb={isThumb} />
      )}

      {slide.title && (
        <div
          className={isThumb ? 'text-[5px] font-bold mb-1' : 'text-xl font-bold mb-4'}
          style={{
            color: theme.colors.primary,
            fontFamily: `"${theme.font_heading}", "Segoe UI", system-ui, sans-serif`,
          }}
        >
          {slide.title}
        </div>
      )}

      <div className="flex-1 flex items-center justify-center min-h-0">
        {chartEl?.content && (
          <ChartPlaceholder content={chartEl.content} theme={theme} isThumb={isThumb} />
        )}
      </div>

      {bodyEl?.content && (
        <BodyElement content={bodyEl.content} theme={theme} isThumb={isThumb} />
      )}

      {takeawayEl?.content && (
        <TakeawayElement content={takeawayEl.content} theme={theme} isThumb={isThumb} />
      )}
    </div>
  );
}
