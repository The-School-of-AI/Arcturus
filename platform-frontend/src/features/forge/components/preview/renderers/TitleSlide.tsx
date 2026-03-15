import type { SlideTheme } from './theme-utils';
import { isDarkBackground } from './theme-utils';
import type { Slide } from '../normalizers';
import { findElement, normalizeTitleMeta, normalizeStats } from '../normalizers';
import { StatCalloutElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  slideIndex: number;
  totalSlides: number;
  isThumb?: boolean;
}

export function TitleSlide({ slide, theme, slideIndex, totalSlides, isThumb }: Props) {
  const meta = normalizeTitleMeta(slide, slideIndex, totalSlides);
  const titleBg = theme.colors.title_background || theme.colors.primary;
  const dark = isDarkBackground(titleBg);
  const titleColor = dark ? '#ffffff' : theme.colors.primary;
  const subtitleColor = dark ? 'rgba(255,255,255,0.7)' : theme.colors.text_light;

  const subtitleEl = findElement(slide, 'subtitle');
  const statEl = findElement(slide, 'stat_callout');
  const closingStats = meta.isClosing && statEl ? normalizeStats(statEl.content) : [];

  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-[8%]">
      {/* Badge */}
      {meta.badge && !isThumb && (
        <div
          className="inline-block px-3 py-1 rounded-full text-[10px] font-bold uppercase mb-3"
          style={{ backgroundColor: theme.colors.accent, color: '#ffffff' }}
        >
          {meta.badge}
        </div>
      )}

      {/* Title — multi-line: line1 in primary, line2 in accent */}
      {meta.titleLines.map((line, i) => (
        <div
          key={i}
          className={isThumb ? 'text-[7px] font-bold leading-tight' : 'text-3xl font-bold leading-tight'}
          style={{
            color: i === 0 ? titleColor : theme.colors.accent,
            fontFamily: `"${theme.font_heading}", "Segoe UI", system-ui, sans-serif`,
          }}
        >
          {line}
        </div>
      ))}

      {/* Subtitle */}
      {subtitleEl?.content && (
        <div
          className={isThumb ? 'text-[4px] mt-1' : 'text-base mt-4'}
          style={{ color: subtitleColor }}
        >
          {subtitleEl.content}
        </div>
      )}

      {/* Date / Category footer */}
      {!isThumb && (meta.date || meta.category) && (
        <div className="mt-4 text-xs" style={{ color: subtitleColor }}>
          {[meta.date, meta.category].filter(Boolean).join(' · ')}
        </div>
      )}

      {/* Closing stats footer */}
      {closingStats.length > 0 && (
        <div className={isThumb ? 'mt-2' : 'mt-8'}>
          <StatCalloutElement stats={closingStats} theme={theme} isThumb={isThumb} />
        </div>
      )}
    </div>
  );
}
