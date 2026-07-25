import { useEffect, useRef } from 'react';

/**
 * Dynamically loads Google Fonts declared in content_tree.metadata.fonts.
 * Uses fontsource CDN (cdn.jsdelivr.net) which is already in our CSP.
 * Loads weights 400 (regular) and 700 (bold) for each font.
 */
export function useSlideFonts(fonts?: string[]) {
  const loadedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!fonts || fonts.length === 0) return;

    for (const fontName of fonts.slice(0, 3)) {
      if (loadedRef.current.has(fontName)) continue;
      loadedRef.current.add(fontName);

      // fontsource slug: lowercase, spaces → hyphens
      const slug = fontName.toLowerCase().replace(/\s+/g, '-');

      for (const weight of [400, 700]) {
        const href = `https://cdn.jsdelivr.net/fontsource/fonts/${slug}@latest/latin-${weight}-normal.min.css`;
        // Avoid duplicate <link> elements
        if (document.querySelector(`link[href="${href}"]`)) continue;

        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href;
        link.crossOrigin = 'anonymous';
        document.head.appendChild(link);
      }
    }
  }, [fonts]);
}
