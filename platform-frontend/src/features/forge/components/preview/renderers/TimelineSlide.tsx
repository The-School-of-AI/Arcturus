import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement, normalizeTimeline } from '../normalizers';
import { KickerElement, BodyElement, TakeawayElement, AnimatedElement } from './elements';
import { resolveSlideColors, resolveCardStyle } from './theme-utils';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function TimelineSlide({ slide, theme, isThumb }: Props) {
  const sc = resolveSlideColors(slide.metadata?.slide_style, theme);
  const cs = resolveCardStyle(slide.metadata?.slide_style?.card, theme, !!isThumb);
  const kickerEl = findElement(slide, 'kicker');
  const bodyEl = findElement(slide, 'body');
  const bulletEl = findElement(slide, 'bullet_list');
  const takeawayEl = findElement(slide, 'takeaway');

  const items = bulletEl?.content && Array.isArray(bulletEl.content) ? bulletEl.content : [];
  const { hasPipeFormat, entries } = normalizeTimeline(items);

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

      <div className="flex-1 min-h-0 overflow-hidden">
        {hasPipeFormat ? (
          <div className={isThumb ? 'space-y-0.5' : 'space-y-2'}>
            {entries.map((entry, i) => (
              <div
                key={i}
                className={`${isThumb ? 'flex items-center gap-0.5 text-[3px] p-0.5 rounded' : 'flex items-start gap-3 p-3 rounded-lg'} ${cs.className}`}
                style={cs.inlineStyle}
              >
                {/* Timeline dot + line */}
                {!isThumb && (
                  <div className="flex flex-col items-center shrink-0 pt-1">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: sc.accentColor }} />
                    {i < entries.length - 1 && (
                      <div className="w-px flex-1 mt-1" style={{ backgroundColor: sc.accentColor + '30' }} />
                    )}
                  </div>
                )}

                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    {entry.date && (
                      <span
                        className={isThumb ? 'font-bold' : 'text-xs font-bold shrink-0'}
                        style={{ color: sc.accentColor }}
                      >
                        {entry.date}
                      </span>
                    )}
                    <span
                      className={isThumb ? 'font-bold' : 'text-sm font-semibold'}
                      style={{ color: sc.bodyColor }}
                    >
                      {entry.title}
                    </span>
                  </div>
                  {entry.description && !isThumb && (
                    <div className="text-xs mt-0.5" style={{ color: theme.colors.text_light }}>
                      {entry.description}
                    </div>
                  )}
                </div>

                {entry.tag && !isThumb && (
                  <span
                    className="shrink-0 px-2 py-0.5 rounded-full text-xs font-bold text-white"
                    style={{ backgroundColor: sc.accentColor }}
                  >
                    {entry.tag}
                  </span>
                )}
              </div>
            ))}
          </div>
        ) : (
          /* Fallback: simple bullet timeline */
          <div className={isThumb ? 'space-y-0.5' : 'space-y-2'}>
            {entries.map((entry, i) => (
              <div key={i} className="flex items-start gap-2">
                <div
                  className={isThumb ? 'w-[2px] h-[2px] rounded-full mt-[1px] shrink-0' : 'w-2 h-2 rounded-full mt-1.5 shrink-0'}
                  style={{ backgroundColor: sc.accentColor }}
                />
                <span
                  className={isThumb ? 'text-[3.5px]' : 'text-sm'}
                  style={{ color: sc.bodyColor }}
                >
                  {entry.title}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {takeawayEl?.content && (
        <TakeawayElement content={takeawayEl.content} theme={theme} isThumb={isThumb} accentColor={sc.accentColor} />
      )}
    </div>
  );
}
