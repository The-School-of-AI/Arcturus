import type React from 'react';

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

// ── SlideStyle: LLM-driven per-slide CSS-level styling ─────────────────────

export interface SlideStyle {
  background?: { value: string };
  decorations?: Array<{ type: string; css: Record<string, string> }>;
  title?: Record<string, string>;
  body?: Record<string, string>;
  card?: Record<string, string>;
  accentColor?: string;
}

// ── CSS Sanitization ───────────────────────────────────────────────────────

const CSS_WHITELIST = new Set([
  'position', 'top', 'right', 'bottom', 'left',
  'width', 'height', 'minWidth', 'maxWidth', 'minHeight', 'maxHeight',
  'background', 'backgroundColor', 'backgroundImage', 'backgroundSize', 'backgroundPosition',
  'color', 'opacity',
  'border', 'borderTop', 'borderRight', 'borderBottom', 'borderLeft',
  'borderRadius', 'borderColor', 'borderWidth', 'borderStyle',
  'boxShadow', 'textShadow',
  'fontSize', 'fontWeight', 'fontFamily', 'fontStyle',
  'textTransform', 'letterSpacing', 'lineHeight', 'textAlign',
  'padding', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
  'margin', 'marginTop', 'marginRight', 'marginBottom', 'marginLeft',
  'transform', 'transformOrigin',
  'backdropFilter', 'filter',
  'display', 'flexDirection', 'alignItems', 'justifyContent', 'gap',
  'zIndex', 'overflow',
]);

const DANGEROUS_PATTERNS = /expression\s*\(|javascript:|url\s*\(\s*["']?\s*(?:data:(?!image)|javascript:)|@import|behavior\s*:/i;

/** Whitelist-based CSS sanitizer. Allows safe design properties, blocks injection vectors. */
export function sanitizeCss(css: Record<string, string | number | undefined>): React.CSSProperties {
  const result: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(css)) {
    if (value === undefined || value === null) continue;
    if (!CSS_WHITELIST.has(key)) continue;
    const strVal = String(value);
    if (DANGEROUS_PATTERNS.test(strVal)) continue;
    result[key] = value;
  }
  return result as React.CSSProperties;
}

// ── Color Utilities ────────────────────────────────────────────────────────

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

// ── Slide Color Resolution ─────────────────────────────────────────────────

export interface ResolvedSlideColors {
  titleColor: string;
  titleFont: string;
  titleStyle: React.CSSProperties;
  bodyColor: string;
  bodyStyle: React.CSSProperties;
  accentColor: string;
}

/** Merge per-slide style overrides with theme defaults. */
export function resolveSlideColors(
  slideStyle: SlideStyle | undefined,
  theme: SlideTheme,
): ResolvedSlideColors {
  const titleOverrides = slideStyle?.title ?? {};
  const bodyOverrides = slideStyle?.body ?? {};

  return {
    titleColor: titleOverrides.color ?? theme.colors.primary,
    titleFont: titleOverrides.fontFamily ?? `"${theme.font_heading}", "Segoe UI", system-ui, sans-serif`,
    titleStyle: sanitizeCss({
      fontSize: titleOverrides.fontSize,
      fontWeight: titleOverrides.fontWeight,
      textTransform: titleOverrides.textTransform,
      letterSpacing: titleOverrides.letterSpacing,
      textShadow: titleOverrides.textShadow,
    }),
    bodyColor: bodyOverrides.color ?? theme.colors.text,
    bodyStyle: sanitizeCss({
      fontSize: bodyOverrides.fontSize,
      lineHeight: bodyOverrides.lineHeight,
    }),
    accentColor: slideStyle?.accentColor ?? theme.colors.accent,
  };
}

// ── Card Style Resolution ──────────────────────────────────────────────────

/** Resolve card styling from slide_style.card or theme defaults. */
export function resolveCardStyle(
  cardOverride: SlideStyle['card'],
  theme: SlideTheme,
  isThumb: boolean,
): { className: string; inlineStyle: React.CSSProperties } {
  if (cardOverride && Object.keys(cardOverride).length > 0) {
    return {
      className: cardOverride.backdropFilter ? 'backdrop-blur-sm' : '',
      inlineStyle: sanitizeCss({
        background: cardOverride.background,
        border: cardOverride.border,
        borderRadius: cardOverride.borderRadius ?? (isThumb ? '4px' : '8px'),
        boxShadow: cardOverride.boxShadow,
        backdropFilter: cardOverride.backdropFilter,
      }),
    };
  }
  // Default: flat card from theme
  return {
    className: '',
    inlineStyle: { backgroundColor: theme.colors.primary + '08' },
  };
}
