import type { SlideTheme } from './theme-utils';
import { isDarkBackground } from './theme-utils';
import type { Slide } from '../normalizers';
import { findElement } from '../normalizers';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function SectionDividerSlide({ slide, theme, isThumb }: Props) {
  const titleBg = theme.colors.title_background || theme.colors.primary;
  const dark = isDarkBackground(titleBg);
  const titleColor = dark ? '#ffffff' : theme.colors.primary;
  const subtitleColor = dark ? 'rgba(255,255,255,0.7)' : theme.colors.text_light;
  const subtitleEl = findElement(slide, 'subtitle');

  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-[10%]">
      <div
        className={isThumb ? 'text-[6px] font-bold' : 'text-2xl font-bold'}
        style={{
          color: titleColor,
          fontFamily: `"${theme.font_heading}", "Segoe UI", system-ui, sans-serif`,
        }}
      >
        {slide.title}
      </div>
      {subtitleEl?.content && (
        <div
          className={isThumb ? 'text-[3.5px] mt-0.5' : 'text-sm mt-3'}
          style={{ color: subtitleColor }}
        >
          {subtitleEl.content}
        </div>
      )}
    </div>
  );
}
