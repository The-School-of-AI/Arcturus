import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement } from '../normalizers';
import { BodyElement, AnimatedElement } from './elements';
import { resolveSlideColors, resolveCardStyle } from './theme-utils';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function TeamSlide({ slide, theme, isThumb }: Props) {
  const sc = resolveSlideColors(slide.metadata?.slide_style, theme);
  const cs = resolveCardStyle(slide.metadata?.slide_style?.card, theme, !!isThumb);
  const bulletEl = findElement(slide, 'bullet_list');
  const bodyEl = findElement(slide, 'body');
  const items = bulletEl?.content && Array.isArray(bulletEl.content) ? bulletEl.content : [];

  const cols = items.length <= 3 ? items.length : items.length <= 6 ? 3 : 4;

  return (
    <div className={`flex flex-col h-full ${isThumb ? 'p-2' : 'p-[6%]'}`}>
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

      {items.length === 0 && bodyEl?.content ? (
        <BodyElement content={bodyEl.content} theme={theme} isThumb={isThumb} bodyColor={sc.bodyColor} bodyStyle={sc.bodyStyle} accentColor={sc.accentColor} />
      ) : (
        <div
          className={`flex-1 grid min-h-0 ${isThumb ? 'gap-0.5' : 'gap-3'}`}
          style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
        >
          {items.map((item, i) => {
            const text = String(item);
            const [name, ...roleParts] = text.split('\n');
            const role = roleParts.join(' ').trim();

            return (
              <div
                key={i}
                className={`flex flex-col items-center justify-center rounded-lg ${isThumb ? 'p-0.5' : 'p-3'} ${cs.className}`}
                style={cs.inlineStyle}
              >
                {/* Avatar placeholder */}
                <div
                  className={isThumb ? 'w-2 h-2 rounded-full mb-0.5' : 'w-10 h-10 rounded-full mb-2'}
                  style={{ backgroundColor: sc.accentColor + '30' }}
                />
                <div
                  className={isThumb ? 'text-[3px] font-bold text-center' : 'text-sm font-semibold text-center'}
                  style={{ color: sc.bodyColor }}
                >
                  {name}
                </div>
                {role && (
                  <div
                    className={isThumb ? 'text-[2.5px] text-center' : 'text-xs text-center mt-0.5'}
                    style={{ color: theme.colors.text_light }}
                  >
                    {role}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
