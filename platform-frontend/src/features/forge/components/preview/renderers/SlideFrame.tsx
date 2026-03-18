import type { ReactNode } from 'react';
import { isDarkBackground, sanitizeCss } from './theme-utils';
import type { SlideTheme, SlideStyle } from './theme-utils';

// Types and utils re-exported from theme-utils for convenience
export type { SlideTheme, SlideThemeColors, SlideStyle } from './theme-utils';

interface SlideFrameProps {
  theme: SlideTheme;
  slideIndex: number;
  totalSlides: number;
  isThumb?: boolean;
  /** Use title_background instead of background (for title/section_divider slides) */
  useTitleBg?: boolean;
  /** Per-slide LLM-driven styling */
  slideStyle?: SlideStyle;
  children: ReactNode;
}

function resolveBackground(theme: SlideTheme, useTitleBg: boolean, slideStyle?: SlideStyle): React.CSSProperties {
  const bgValue = slideStyle?.background?.value;
  if (bgValue) {
    // LLM-specified background — use as CSS background (handles gradients + solid)
    if (bgValue.includes('gradient') || bgValue.includes('url(')) {
      return { background: bgValue };
    }
    return { backgroundColor: bgValue };
  }
  // Fallback: theme background
  const baseBg = useTitleBg && theme.colors.title_background
    ? theme.colors.title_background
    : theme.colors.background;
  return { backgroundColor: baseBg };
}

function getEffectiveBg(theme: SlideTheme, useTitleBg: boolean, slideStyle?: SlideStyle): string {
  const bgValue = slideStyle?.background?.value;
  if (bgValue) {
    // Extract first hex color from CSS value for dark/light detection
    const hexMatch = bgValue.match(/#[0-9a-fA-F]{3,8}/);
    if (hexMatch) {
      const hex = hexMatch[0];
      if (hex.length === 4) {
        return `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`;
      }
      return hex.substring(0, 7);
    }
    // Try rgb/rgba
    const rgbMatch = bgValue.match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
    if (rgbMatch) {
      const toHex = (n: string) => parseInt(n).toString(16).padStart(2, '0');
      return `#${toHex(rgbMatch[1])}${toHex(rgbMatch[2])}${toHex(rgbMatch[3])}`;
    }
  }
  if (useTitleBg && theme.colors.title_background) return theme.colors.title_background;
  return theme.colors.background;
}

export function SlideFrame({
  theme,
  slideIndex,
  totalSlides,
  isThumb = false,
  useTitleBg = false,
  slideStyle,
  children,
}: SlideFrameProps) {
  const bgStyles = resolveBackground(theme, useTitleBg, slideStyle);
  const effectiveBg = getEffectiveBg(theme, useTitleBg, slideStyle);
  const dark = isDarkBackground(effectiveBg);
  const chromeColor = dark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.25)';
  const progress = totalSlides > 1 ? ((slideIndex + 1) / totalSlides) * 100 : 100;

  return (
    <div
      className={`relative w-full aspect-[16/9] overflow-hidden select-none${isThumb ? '' : ' shadow-sm rounded-lg'}`}
      style={{
        ...bgStyles,
        fontFamily: `"${theme.font_body}", "Segoe UI", system-ui, sans-serif`,
      }}
    >
      {/* LLM-defined decorations */}
      {slideStyle?.decorations?.map((dec, i) => (
        <div
          key={i}
          className="pointer-events-none"
          style={sanitizeCss({
            position: 'absolute',
            ...dec.css,
          })}
        />
      ))}

      {children}

      {/* Bottom chrome: progress bar + slide number */}
      {!isThumb && (
        <div className="absolute bottom-0 left-0 right-0 z-20">
          <div className="h-[3px] w-full" style={{ backgroundColor: dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)' }}>
            <div
              className="h-full transition-all duration-300"
              style={{ width: `${progress}%`, backgroundColor: theme.colors.accent }}
            />
          </div>
          <div
            className="absolute bottom-1.5 right-3 text-xs font-mono"
            style={{ color: chromeColor }}
          >
            {slideIndex + 1}
          </div>
        </div>
      )}
    </div>
  );
}
