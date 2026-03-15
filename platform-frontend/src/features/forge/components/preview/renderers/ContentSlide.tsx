import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement } from '../normalizers';
import { KickerElement, BulletListElement, BodyElement, TakeawayElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function ContentSlide({ slide, theme, isThumb }: Props) {
  const kickerEl = findElement(slide, 'kicker');
  const bodyEl = findElement(slide, 'body');
  const bulletEl = findElement(slide, 'bullet_list');
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

      <div className="flex-1 min-h-0">
        {bodyEl?.content && typeof bodyEl.content === 'string' && (
          <BodyElement content={bodyEl.content} theme={theme} isThumb={isThumb} />
        )}
        {bulletEl?.content && Array.isArray(bulletEl.content) && (
          <div className={isThumb ? '' : 'mt-2'}>
            <BulletListElement items={bulletEl.content} theme={theme} isThumb={isThumb} />
          </div>
        )}
      </div>

      {takeawayEl?.content && (
        <TakeawayElement content={takeawayEl.content} theme={theme} isThumb={isThumb} />
      )}
    </div>
  );
}
