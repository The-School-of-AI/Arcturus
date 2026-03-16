export interface SlideThemeColors {
  primary: string;
  secondary: string;
  accent: string;
  background: string;
  text: string;
  text_light: string;
  title_background?: string;
}

export interface SlideTheme {
  id: string;
  name: string;
  colors: SlideThemeColors;
  font_heading: string;
  font_body: string;
}

function relativeLuminance(hex: string): number {
  const h = hex.replace('#', '');
  const r = parseInt(h.substring(0, 2), 16) / 255;
  const g = parseInt(h.substring(2, 4), 16) / 255;
  const b = parseInt(h.substring(4, 6), 16) / 255;
  const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

export function isDarkBackground(hex: string): boolean {
  return relativeLuminance(hex) < 0.2;
}

/** Card style classes and inline styles from visual_style token. */
export function cardStyles(
  style: string | undefined,
  theme: SlideTheme,
  isThumb: boolean,
): { className: string; inlineStyle: React.CSSProperties } {
  switch (style) {
    case 'elevated':
      return {
        className: isThumb ? 'shadow-sm' : 'shadow-lg',
        inlineStyle: { backgroundColor: theme.colors.primary + '08' },
      };
    case 'glass':
      return {
        className: `backdrop-blur-sm ${isThumb ? '' : 'shadow-sm'}`,
        inlineStyle: {
          backgroundColor: isDarkBackground(theme.colors.background)
            ? 'rgba(255,255,255,0.06)'
            : 'rgba(255,255,255,0.7)',
          border: `1px solid ${isDarkBackground(theme.colors.background) ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)'}`,
        },
      };
    case 'outlined':
      return {
        className: '',
        inlineStyle: {
          backgroundColor: 'transparent',
          border: `1px solid ${theme.colors.primary}20`,
        },
      };
    case 'flat':
    default:
      return {
        className: '',
        inlineStyle: { backgroundColor: theme.colors.primary + '08' },
      };
  }
}

/** Blend two hex colors by a ratio (0 = pure base, 1 = pure overlay). */
export function blendColor(base: string, overlay: string, ratio: number): string {
  const parse = (h: string) => {
    const c = h.replace('#', '');
    return [parseInt(c.substring(0, 2), 16), parseInt(c.substring(2, 4), 16), parseInt(c.substring(4, 6), 16)];
  };
  const [r1, g1, b1] = parse(base);
  const [r2, g2, b2] = parse(overlay);
  const mix = (a: number, b: number) => Math.round(a + (b - a) * ratio);
  const hex = (n: number) => n.toString(16).padStart(2, '0');
  return `#${hex(mix(r1, r2))}${hex(mix(g1, g2))}${hex(mix(b1, b2))}`;
}
