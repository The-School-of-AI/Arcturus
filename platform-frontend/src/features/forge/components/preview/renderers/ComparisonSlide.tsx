import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement, findElements, normalizeComparisonColumn, normalizeCalloutBox } from '../normalizers';
import { KickerElement, TakeawayElement, AnimatedElement } from './elements';
import { cardStyles } from './theme-utils';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function ComparisonSlide({ slide, theme, isThumb }: Props) {
  const cs = cardStyles(slide.metadata?.visual_style?.card_style, theme, !!isThumb);
  const kickerEl = findElement(slide, 'kicker');
  const bodyEls = findElements(slide, 'body');
  const takeawayEl = findElement(slide, 'takeaway');
  const calloutEl = findElement(slide, 'callout_box');

  const left = normalizeComparisonColumn(bodyEls[0]?.content ?? '');
  const right = normalizeComparisonColumn(bodyEls[1]?.content ?? '');

  const callout = calloutEl ? normalizeCalloutBox(calloutEl.content) : null;

  return (
    <div className={`flex flex-col h-full ${isThumb ? 'p-2' : 'p-[6%]'}`}>
      <AnimatedElement animation="fade" delay={0} isThumb={isThumb}>
        {kickerEl?.content && (
          <KickerElement content={kickerEl.content} theme={theme} isThumb={isThumb} />
        )}
      </AnimatedElement>

      {slide.title && (
        <AnimatedElement animation="rise" delay={80} isThumb={isThumb}>
          <div
            className={isThumb ? 'text-[5px] font-bold mb-1' : 'text-xl font-bold mb-4'}
            style={{
              color: theme.colors.primary,
              fontFamily: `"${theme.font_heading}", "Segoe UI", system-ui, sans-serif`,
            }}
          >
            {slide.title}
          </div>
        </AnimatedElement>
      )}

      <div className={`flex-1 grid grid-cols-2 ${isThumb ? 'gap-1' : 'gap-4'} min-h-0`}>
        {/* Left column */}
        <div>
          {left.label && (
            <div
              className={isThumb ? 'text-[3.5px] font-bold mb-0.5' : 'text-sm font-bold mb-2 pb-1 border-b'}
              style={{
                color: theme.colors.secondary,
                borderColor: theme.colors.secondary + '40',
              }}
            >
              {left.label}
            </div>
          )}
          <div
            className={`${isThumb ? 'text-[3px] p-1 rounded' : 'text-sm p-3 rounded-lg'} ${cs.className}`}
            style={{
              ...cs.inlineStyle,
              color: theme.colors.text,
            }}
          >
            {left.body}
          </div>
        </div>

        {/* Right column */}
        <div>
          {right.label && (
            <div
              className={isThumb ? 'text-[3.5px] font-bold mb-0.5' : 'text-sm font-bold mb-2 pb-1 border-b'}
              style={{
                color: theme.colors.accent,
                borderColor: theme.colors.accent + '40',
              }}
            >
              {right.label}
            </div>
          )}
          <div
            className={`${isThumb ? 'text-[3px] p-1 rounded' : 'text-sm p-3 rounded-lg'} ${cs.className}`}
            style={{
              ...cs.inlineStyle,
              color: theme.colors.text,
            }}
          >
            {right.body}
          </div>
        </div>
      </div>

      {/* Callout box */}
      {callout && callout.text && !isThumb && (
        <div
          className="mt-3 px-4 py-2 rounded-lg text-xs italic"
          style={{
            backgroundColor: theme.colors.primary + '12',
            color: theme.colors.text_light,
          }}
        >
          &ldquo;{callout.text}&rdquo;
          {callout.attribution && (
            <span className="not-italic ml-2">&mdash; {callout.attribution}</span>
          )}
        </div>
      )}

      {takeawayEl?.content && (
        <TakeawayElement content={takeawayEl.content} theme={theme} isThumb={isThumb} />
      )}
    </div>
  );
}
