import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement, findElements } from '../normalizers';
import { KickerElement, BulletListElement, BodyElement, TakeawayElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function TwoColumnSlide({ slide, theme, isThumb }: Props) {
  const kickerEl = findElement(slide, 'kicker');
  const bodyEls = findElements(slide, 'body');
  const bulletEls = findElements(slide, 'bullet_list');
  const takeawayEl = findElement(slide, 'takeaway');

  const leftBody = bodyEls[0]?.content;
  const rightBody = bodyEls[1]?.content;
  const leftBullets = bulletEls[0]?.content;
  const rightBullets = bulletEls[1]?.content;

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

      <div className={`flex-1 grid grid-cols-2 ${isThumb ? 'gap-1' : 'gap-6'} min-h-0`}>
        {/* Left column */}
        <div className="flex flex-col">
          {leftBody && typeof leftBody === 'string' && (
            <BodyElement content={leftBody} theme={theme} isThumb={isThumb} />
          )}
          {leftBullets && Array.isArray(leftBullets) && (
            <BulletListElement items={leftBullets} theme={theme} isThumb={isThumb} />
          )}
        </div>
        {/* Right column */}
        <div className="flex flex-col">
          {rightBody && typeof rightBody === 'string' && (
            <BodyElement content={rightBody} theme={theme} isThumb={isThumb} />
          )}
          {rightBullets && Array.isArray(rightBullets) && (
            <BulletListElement items={rightBullets} theme={theme} isThumb={isThumb} />
          )}
        </div>
      </div>

      {takeawayEl?.content && (
        <TakeawayElement content={takeawayEl.content} theme={theme} isThumb={isThumb} />
      )}
    </div>
  );
}
