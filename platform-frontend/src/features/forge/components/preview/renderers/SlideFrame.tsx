import type { ReactNode } from 'react';
import { isDarkBackground, blendColor } from './theme-utils';
import type { SlideTheme } from './theme-utils';

// Types and utils re-exported from theme-utils for convenience
export type { SlideTheme, SlideThemeColors } from './theme-utils';

export interface VisualStyle {
  bg_variant?: 'solid' | 'gradient' | 'accent_wash' | 'dark_invert';
  decoration?: 'none' | 'corner_accent' | 'top_bar' | 'side_stripe';
  card_style?: 'flat' | 'elevated' | 'glass' | 'outlined';
}

interface SlideFrameProps {
  theme: SlideTheme;
  slideIndex: number;
  totalSlides: number;
  isThumb?: boolean;
  /** Use title_background instead of background (for title/section_divider slides) */
  useTitleBg?: boolean;
  /** Per-slide visual style metadata */
  visualStyle?: VisualStyle;
  children: ReactNode;
}

function resolveBackground(theme: SlideTheme, useTitleBg: boolean, variant?: string): React.CSSProperties {
  const baseBg = useTitleBg && theme.colors.title_background
    ? theme.colors.title_background
    : theme.colors.background;

  switch (variant) {
    case 'gradient':
      return {
        background: `linear-gradient(135deg, ${baseBg}, ${blendColor(baseBg, theme.colors.primary, 0.08)})`,
      };
    case 'accent_wash':
      return {
        backgroundColor: blendColor(baseBg, theme.colors.accent, 0.05),
      };
    case 'dark_invert':
      return {
        backgroundColor: theme.colors.title_background || blendColor(theme.colors.background, '#000000', 0.85),
      };
    case 'solid':
    default:
      return { backgroundColor: baseBg };
  }
}

function getEffectiveBg(theme: SlideTheme, useTitleBg: boolean, variant?: string): string {
  if (variant === 'dark_invert') {
    return theme.colors.title_background || '#111111';
  }
  if (variant === 'accent_wash') {
    const baseBg = useTitleBg && theme.colors.title_background ? theme.colors.title_background : theme.colors.background;
    return blendColor(baseBg, theme.colors.accent, 0.05);
  }
  if (useTitleBg && theme.colors.title_background) {
    return theme.colors.title_background;
  }
  return theme.colors.background;
}

export function SlideFrame({
  theme,
  slideIndex,
  totalSlides,
  isThumb = false,
  useTitleBg = false,
  visualStyle,
  children,
}: SlideFrameProps) {
  const bgVariant = visualStyle?.bg_variant || 'solid';
  const decoration = visualStyle?.decoration || 'none';

  const bgStyles = resolveBackground(theme, useTitleBg, bgVariant);
  const effectiveBg = getEffectiveBg(theme, useTitleBg, bgVariant);
  const dark = isDarkBackground(effectiveBg);
  const chromeColor = dark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.25)';
  const progress = totalSlides > 1 ? ((slideIndex + 1) / totalSlides) * 100 : 100;

  return (
    <div
      className={`relative w-full aspect-[16/9] overflow-hidden select-none${isThumb ? '' : ' shadow-2xl rounded-lg'}`}
      style={{
        ...bgStyles,
        fontFamily: `"${theme.font_body}", "Segoe UI", system-ui, sans-serif`,
      }}
    >
      {/* Decorations */}
      {decoration === 'corner_accent' && (
        <div
          className="absolute top-0 right-0 pointer-events-none"
          style={{
            width: isThumb ? '20%' : '15%',
            height: isThumb ? '20%' : '15%',
            background: `linear-gradient(225deg, ${theme.colors.accent}20 0%, transparent 60%)`,
            borderBottomLeftRadius: '100%',
          }}
        />
      )}
      {decoration === 'top_bar' && (
        <div
          className="absolute top-0 left-0 right-0 pointer-events-none"
          style={{
            height: isThumb ? 2 : 4,
            background: `linear-gradient(90deg, ${theme.colors.primary}, ${theme.colors.accent})`,
          }}
        />
      )}
      {decoration === 'side_stripe' && (
        <div
          className="absolute top-0 left-0 bottom-0 pointer-events-none"
          style={{
            width: isThumb ? 2 : 5,
            backgroundColor: theme.colors.accent,
          }}
        />
      )}

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
