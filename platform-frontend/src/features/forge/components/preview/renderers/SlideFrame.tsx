import type { ReactNode } from 'react';
import { isDarkBackground } from './theme-utils';
import type { SlideTheme } from './theme-utils';

// Types and utils re-exported from theme-utils for convenience
export type { SlideTheme, SlideThemeColors } from './theme-utils';

interface SlideFrameProps {
  theme: SlideTheme;
  slideIndex: number;
  totalSlides: number;
  isThumb?: boolean;
  /** Use title_background instead of background (for title/section_divider slides) */
  useTitleBg?: boolean;
  children: ReactNode;
}

export function SlideFrame({
  theme,
  slideIndex,
  totalSlides,
  isThumb = false,
  useTitleBg = false,
  children,
}: SlideFrameProps) {
  const bgColor = useTitleBg && theme.colors.title_background
    ? theme.colors.title_background
    : theme.colors.background;
  const dark = isDarkBackground(bgColor);
  const chromeColor = dark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.25)';
  const progress = totalSlides > 1 ? ((slideIndex + 1) / totalSlides) * 100 : 100;

  return (
    <div
      className={`relative w-full aspect-[16/9] overflow-hidden select-none${isThumb ? '' : ' shadow-2xl rounded-lg'}`}
      style={{
        backgroundColor: bgColor,
        fontFamily: `"${theme.font_body}", "Segoe UI", system-ui, sans-serif`,
      }}
    >
      {children}

      {/* Bottom chrome: progress bar + slide number */}
      {!isThumb && (
        <div className="absolute bottom-0 left-0 right-0">
          {/* Progress bar */}
          <div className="h-[3px] w-full" style={{ backgroundColor: dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)' }}>
            <div
              className="h-full transition-all duration-300"
              style={{ width: `${progress}%`, backgroundColor: theme.colors.accent }}
            />
          </div>
          {/* Slide number */}
          <div
            className="absolute bottom-1.5 right-3 text-[10px] font-mono"
            style={{ color: chromeColor }}
          >
            {slideIndex + 1}
          </div>
        </div>
      )}
    </div>
  );
}
