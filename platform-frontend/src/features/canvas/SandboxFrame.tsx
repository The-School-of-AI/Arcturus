import React, { useRef, useEffect, useState, useMemo } from 'react';

type Theme = 'light' | 'dark';

interface SandboxFrameProps {
    html: string;
    css?: string;
    js?: string;
    title?: string;
    theme?: Theme;
    onEvent?: (event: any) => void;
}

/* Arcturus theme colors so embedded content matches app (light/dark) */
const THEME_VARS = {
  light: `
    --app-bg: hsl(210, 40%, 98%);
    --app-fg: hsl(222, 47%, 11%);
    --app-surface: hsl(0, 0%, 100%);
    --app-border: hsl(214.3, 31.8%, 91.4%);
  `,
  dark: `
    --app-bg: hsl(222, 47%, 11%);
    --app-fg: hsl(210, 40%, 98%);
    --app-surface: hsl(217, 33%, 17%);
    --app-border: hsl(217, 33%, 17.5%);
  `,
};

/* Match Arcturus app dark theme: deep navy + electric blue (same as index.css .dark) */
const VISUAL_EXPLAINER_DARK_OVERRIDES = `
  :root {
    --bg: hsl(222, 47%, 11%);
    --surface: hsl(217, 33%, 17%);
    --surface2: hsl(217, 33%, 20%);
    --surface-elevated: hsl(217, 33%, 21%);
    --border: rgba(255, 255, 255, 0.1);
    --border-bright: rgba(255, 255, 255, 0.14);
    --text: hsl(210, 40%, 98%);
    --text-dim: hsl(215, 20%, 65%);
    --accent: hsl(217, 91%, 60%);
    --accent-dim: rgba(56, 189, 248, 0.15);
  }
`;

/** Detect full HTML document that is the Visual Explainer Mermaid page (has mermaid script + pre.mermaid). */
function isMermaidDocument(html: string): boolean {
  const trimmed = html.trim();
  return (
    (trimmed.startsWith('<!DOCTYPE') || trimmed.startsWith('<html')) &&
    /mermaid\.min\.mjs|mermaid\.esm/i.test(html) &&
    /<pre\s+class=["']mermaid["']/i.test(html)
  );
}

/** Extract title and mermaid code from the backend-generated Mermaid HTML. */
function parseMermaidDocument(html: string): { title: string; code: string } {
  const titleMatch = /<title[^>]*>([^<]*)<\/title>/i.exec(html);
  const title = titleMatch ? titleMatch[1].trim() : 'Diagram';
  const preMatch = /<pre\s+class=["']mermaid["'][^>]*>([\s\S]*?)<\/pre>/i.exec(html);
  const code = preMatch ? preMatch[1].replace(/\\\//g, '/').trim() : '';
  return { title, code };
}

/** Build static HTML wrapper for pre-rendered Mermaid SVG (no script in iframe). */
function buildMermaidWrapper(title: string, svgOrError: string, theme: Theme): string {
  const themeStyle = theme === 'dark' ? `<style>${VISUAL_EXPLAINER_DARK_OVERRIDES}</style>` : '';
  const bodyBg = theme === 'dark' ? 'hsl(222, 47%, 11%)' : 'hsl(210, 40%, 98%)';
  const bodyFg = theme === 'dark' ? 'hsl(210, 40%, 98%)' : 'hsl(222, 47%, 11%)';
  const escapedTitle = title.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const isError = svgOrError.startsWith('<p') || !svgOrError.trim().startsWith('<');
  const wrapContent = isError ? svgOrError : `<div class="mermaid-wrap">${svgOrError}</div>`;
  return `<!DOCTYPE html>
<html lang="en" style="color-scheme: ${theme};">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escapedTitle}</title>
${themeStyle}
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: ${bodyBg}; color: ${bodyFg}; font-family: system-ui, sans-serif; padding: 24px; min-height: 100vh; }
  h1 { font-size: 28px; margin-bottom: 16px; }
  .mermaid-wrap { margin-top: 16px; min-height: 120px; }
  .mermaid-wrap svg { max-width: 100%; height: auto; }
</style>
</head>
<body>
<h1>${escapedTitle}</h1>
${wrapContent}
</body>
</html>`;
}

const SandboxFrame: React.FC<SandboxFrameProps> = ({ html, css = '', js = '', title = 'Arcturus Sandbox', theme = 'dark', onEvent }) => {
    const iframeRef = useRef<HTMLIFrameElement>(null);
    const [mermaidSvg, setMermaidSvg] = useState<string | null>(null);

    const isMermaid = isMermaidDocument(html);
    const mermaidParsed = useMemo(() => (isMermaid ? parseMermaidDocument(html) : null), [isMermaid, html]);

    useEffect(() => {
        if (!isMermaid || !mermaidParsed?.code) {
            setMermaidSvg(null);
            return;
        }
        let cancelled = false;
        import('mermaid')
            .then((m) => {
                if (cancelled) return;
                return m.default.render('mermaid-' + Date.now(), mermaidParsed!.code);
            })
            .then((result) => {
                if (cancelled) return;
                if (result?.svg) setMermaidSvg(result.svg);
                else setMermaidSvg('<p style="color:#e11d48;">Diagram failed to load.</p>');
            })
            .catch((err) => {
                if (!cancelled) {
                    setMermaidSvg('<p style="color:#e11d48;">Diagram failed to load. ' + (err?.message || String(err)) + '</p>');
                }
            });
        return () => { cancelled = true; };
    }, [isMermaid, mermaidParsed?.code]);

    const fullContent = isMermaid && mermaidParsed
      ? buildMermaidWrapper(mermaidParsed.title, mermaidSvg ?? '<p style="color:var(--text-dim);">Loading diagram…</p>', theme)
      : `
    <!DOCTYPE html>
    <html lang="en" style="color-scheme: ${theme};">
    <head>
      <meta charset="UTF-8">
      <meta name="color-scheme" content="${theme}">
      <script>document.documentElement.style.colorScheme = '${theme}';</script>
      <style>
        :root { ${THEME_VARS[theme]} }
        body {
          margin: 0;
          font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          background: var(--app-bg);
          color: var(--app-fg);
        }
        ${css}
      </style>
    </head>
    <body>
      <div id="root">${html}</div>
      ${theme === 'dark' ? `<style>${VISUAL_EXPLAINER_DARK_OVERRIDES}</style>` : ''}
      <script>
        // PostMessage bridge for callbacks
        window.Agent = {
          send: (type, data) => {
            window.parent.postMessage({ type, data, surface: 'sandbox' }, '*');
          }
        };

        // Inject dynamic scripts
        ${js}

        // Listen for parent messages
        window.addEventListener('message', (event) => {
          if (event.data.type === 'eval') {
            try {
              eval(event.data.code);
            } catch (e) {
              console.error('Eval error:', e);
            }
          }
        });
      </script>
    </body>
    </html>
  `;

    useEffect(() => {
        const handleMessage = (event: MessageEvent) => {
            if (event.data.surface === 'sandbox' && onEvent) {
                onEvent(event.data);
            }
        };

        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, [onEvent]);

    return (
        <iframe
            ref={iframeRef}
            title={title}
            srcDoc={fullContent}
            className="w-full h-full border-none bg-background rounded-lg shadow-sm"
            sandbox="allow-scripts allow-forms allow-popups allow-modals"
        />
    );
};

export default SandboxFrame;
