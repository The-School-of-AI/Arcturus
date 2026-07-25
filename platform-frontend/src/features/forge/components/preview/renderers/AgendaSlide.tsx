import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement, normalizeAgendaItems } from '../normalizers';
import { KickerElement, BodyElement, AnimatedElement } from './elements';
import { resolveSlideColors, resolveCardStyle } from './theme-utils';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function AgendaSlide({ slide, theme, isThumb }: Props) {
  const sc = resolveSlideColors(slide.metadata?.slide_style, theme);
  const cs = resolveCardStyle(slide.metadata?.slide_style?.card, theme, !!isThumb);
  const kickerEl = findElement(slide, 'kicker');
  const bodyEl = findElement(slide, 'body');
  const bulletEl = findElement(slide, 'bullet_list');

  const items = bulletEl?.content && Array.isArray(bulletEl.content) ? bulletEl.content : [];
  const agendaItems = normalizeAgendaItems(items);

  const cols = agendaItems.length <= 3 ? agendaItems.length : agendaItems.length <= 6 ? 3 : 4;

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

      {bodyEl?.content && typeof bodyEl.content === 'string' && (
        <AnimatedElement animation="rise" delay={120} isThumb={isThumb}>
          <div className={isThumb ? 'mb-0.5' : 'mb-3'}>
            <BodyElement content={bodyEl.content} theme={theme} isThumb={isThumb} bodyColor={sc.bodyColor} bodyStyle={sc.bodyStyle} accentColor={sc.accentColor} />
          </div>
        </AnimatedElement>
      )}

      <div
        className={`flex-1 grid min-h-0 ${isThumb ? 'gap-0.5' : 'gap-3'}`}
        style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
      >
        {agendaItems.map((item, i) => (
          <div
            key={i}
            className={`${isThumb ? 'p-0.5 rounded' : 'p-4 rounded-lg'} ${cs.className}`}
            style={cs.inlineStyle}
          >
            {/* Numbered badge */}
            <div
              className={isThumb
                ? 'w-2 h-2 rounded-full flex items-center justify-center text-[2.5px] font-bold text-white mb-0.5'
                : 'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white mb-2'
              }
              style={{ backgroundColor: sc.accentColor }}
            >
              {i + 1}
            </div>
            <div
              className={isThumb ? 'text-[3px] font-bold' : 'text-sm font-semibold'}
              style={{ color: sc.bodyColor }}
            >
              {item.title}
            </div>
            {item.description && !isThumb && (
              <div className="text-xs mt-1" style={{ color: theme.colors.text_light }}>
                {item.description}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
