import type { SlideTheme } from './SlideFrame';
import { resolveSlideColors } from './theme-utils';
import type { Slide } from '../normalizers';
import { findElement } from '../normalizers';
import { KickerElement, TakeawayElement, ChartPlaceholder, BodyElement, AnimatedElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function ChartSlide({ slide, theme, isThumb }: Props) {
  const sc = resolveSlideColors(slide.metadata?.slide_style, theme);
  const kickerEl = findElement(slide, 'kicker');
  const chartEl = findElement(slide, 'chart');
  const bodyEl = findElement(slide, 'body');
  const takeawayEl = findElement(slide, 'takeaway');

  return (
    <div className={`flex flex-col h-full ${isThumb ? 'p-2' : 'p-[6%]'}`}>
      {kickerEl?.content && (
        <AnimatedElement animation="fade" delay={0} isThumb={isThumb}>
          <KickerElement content={kickerEl.content} theme={theme} isThumb={isThumb} accentColor={sc.accentColor} />
        </AnimatedElement>
      )}

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

      <div className="flex-1 flex items-center justify-center min-h-0">
        <AnimatedElement animation="scale" delay={200} isThumb={isThumb}>
          {chartEl?.content && (
            <ChartPlaceholder content={chartEl.content} theme={theme} isThumb={isThumb} />
          )}
        </AnimatedElement>
      </div>

      {bodyEl?.content && (
        <AnimatedElement animation="fade" delay={280} isThumb={isThumb}>
          <BodyElement content={bodyEl.content} theme={theme} isThumb={isThumb} bodyColor={sc.bodyColor} bodyStyle={sc.bodyStyle} accentColor={sc.accentColor} />
        </AnimatedElement>
      )}

      {takeawayEl?.content && (
        <AnimatedElement animation="fade" delay={320} isThumb={isThumb}>
          <TakeawayElement content={takeawayEl.content} theme={theme} isThumb={isThumb} accentColor={sc.accentColor} />
        </AnimatedElement>
      )}
    </div>
  );
}
