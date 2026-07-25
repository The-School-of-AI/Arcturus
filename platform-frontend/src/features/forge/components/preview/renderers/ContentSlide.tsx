import type { SlideTheme } from './SlideFrame';
import { resolveSlideColors } from './theme-utils';
import type { Slide } from '../normalizers';
import { findElement } from '../normalizers';
import { KickerElement, BulletListElement, BodyElement, TakeawayElement, AnimatedElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function ContentSlide({ slide, theme, isThumb }: Props) {
  const sc = resolveSlideColors(slide.metadata?.slide_style, theme);
  const kickerEl = findElement(slide, 'kicker');
  const bodyEl = findElement(slide, 'body');
  const bulletEl = findElement(slide, 'bullet_list');
  const takeawayEl = findElement(slide, 'takeaway');

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

      <div className="flex-1 min-h-0">
        <AnimatedElement animation="rise" delay={160} isThumb={isThumb}>
          {bodyEl?.content && typeof bodyEl.content === 'string' && (
            <BodyElement content={bodyEl.content} theme={theme} isThumb={isThumb} bodyColor={sc.bodyColor} bodyStyle={sc.bodyStyle} accentColor={sc.accentColor} />
          )}
          {bulletEl?.content && Array.isArray(bulletEl.content) && (
            <div className={isThumb ? '' : 'mt-2'}>
              <BulletListElement items={bulletEl.content} theme={theme} isThumb={isThumb} bodyColor={sc.bodyColor} bodyStyle={sc.bodyStyle} accentColor={sc.accentColor} />
            </div>
          )}
        </AnimatedElement>
      </div>

      {takeawayEl?.content && (
        <AnimatedElement animation="fade" delay={280} isThumb={isThumb}>
          <TakeawayElement content={takeawayEl.content} theme={theme} isThumb={isThumb} accentColor={sc.accentColor} />
        </AnimatedElement>
      )}
    </div>
  );
}
