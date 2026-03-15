import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement, normalizeStats } from '../normalizers';
import { KickerElement, TakeawayElement, StatCalloutElement, BodyElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function StatSlide({ slide, theme, isThumb }: Props) {
  const kickerEl = findElement(slide, 'kicker');
  const statEl = findElement(slide, 'stat_callout');
  const bodyEl = findElement(slide, 'body');
  const takeawayEl = findElement(slide, 'takeaway');

  const stats = statEl ? normalizeStats(statEl.content) : [];

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
        <StatCalloutElement stats={stats} theme={theme} isThumb={isThumb} />
      </div>

      {bodyEl?.content && typeof bodyEl.content === 'string' && !isThumb && (
        <div className="mt-2">
          <BodyElement content={bodyEl.content} theme={theme} />
        </div>
      )}

      {takeawayEl?.content && (
        <TakeawayElement content={takeawayEl.content} theme={theme} isThumb={isThumb} />
      )}
    </div>
  );
}
