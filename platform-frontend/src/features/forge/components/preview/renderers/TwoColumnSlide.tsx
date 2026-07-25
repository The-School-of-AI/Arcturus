import type { SlideTheme } from './SlideFrame';
import { resolveSlideColors } from './theme-utils';
import type { Slide } from '../normalizers';
import { findElement, findElements } from '../normalizers';
import { KickerElement, BulletListElement, BodyElement, TakeawayElement, AnimatedElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function TwoColumnSlide({ slide, theme, isThumb }: Props) {
  const sc = resolveSlideColors(slide.metadata?.slide_style, theme);
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
      <AnimatedElement animation="fade" delay={0} isThumb={isThumb}>
        {kickerEl?.content && (
          <KickerElement content={kickerEl.content} theme={theme} isThumb={isThumb} accentColor={sc.accentColor} />
        )}
      </AnimatedElement>

      {slide.title && (
        <AnimatedElement animation="rise" delay={80} isThumb={isThumb}>
          <div
            className={isThumb ? 'text-[5px] font-bold mb-1' : 'text-xl font-bold mb-4'}
            style={{
              color: sc.titleColor,
              fontFamily: sc.titleFont,
              ...sc.titleStyle,
            }}
          >
            {slide.title}
          </div>
        </AnimatedElement>
      )}

      <div className={`flex-1 grid grid-cols-2 ${isThumb ? 'gap-1' : 'gap-6'} min-h-0`}>
        {/* Left column */}
        <AnimatedElement animation="rise" delay={160} isThumb={isThumb}>
          <div className="flex flex-col">
            {leftBody && typeof leftBody === 'string' && (
              <BodyElement content={leftBody} theme={theme} isThumb={isThumb} bodyColor={sc.bodyColor} bodyStyle={sc.bodyStyle} accentColor={sc.accentColor} />
            )}
            {leftBullets && Array.isArray(leftBullets) && (
              <BulletListElement items={leftBullets} theme={theme} isThumb={isThumb} bodyColor={sc.bodyColor} bodyStyle={sc.bodyStyle} accentColor={sc.accentColor} />
            )}
          </div>
        </AnimatedElement>
        {/* Right column */}
        <AnimatedElement animation="rise" delay={240} isThumb={isThumb}>
          <div className="flex flex-col">
            {rightBody && typeof rightBody === 'string' && (
              <BodyElement content={rightBody} theme={theme} isThumb={isThumb} bodyColor={sc.bodyColor} bodyStyle={sc.bodyStyle} accentColor={sc.accentColor} />
            )}
            {rightBullets && Array.isArray(rightBullets) && (
              <BulletListElement items={rightBullets} theme={theme} isThumb={isThumb} bodyColor={sc.bodyColor} bodyStyle={sc.bodyStyle} accentColor={sc.accentColor} />
            )}
          </div>
        </AnimatedElement>
      </div>

      {takeawayEl?.content && (
        <AnimatedElement animation="fade" delay={320} isThumb={isThumb}>
          <TakeawayElement content={takeawayEl.content} theme={theme} isThumb={isThumb} accentColor={sc.accentColor} />
        </AnimatedElement>
      )}
    </div>
  );
}
