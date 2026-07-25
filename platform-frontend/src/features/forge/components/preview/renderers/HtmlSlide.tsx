import DOMPurify from 'dompurify';

interface HtmlSlideProps {
  html: string;
  isThumb?: boolean;
}

// DOMPurify config — strict whitelist, inline styles only, SVG allowed
const PURIFY_CONFIG: DOMPurify.Config = {
  ALLOWED_TAGS: [
    // HTML
    'div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'strong', 'em', 'b', 'i', 'br', 'hr',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'img', 'pre', 'code', 'blockquote', 'a', 'sup', 'sub', 'mark', 'small',
    'section', 'article', 'header', 'footer', 'figure', 'figcaption',
    // SVG
    'svg', 'path', 'circle', 'rect', 'line', 'polyline', 'polygon',
    'ellipse', 'g', 'defs', 'clipPath', 'use', 'text', 'tspan',
    'linearGradient', 'radialGradient', 'stop', 'filter',
    'feGaussianBlur', 'feOffset', 'feMerge', 'feMergeNode', 'feFlood', 'feComposite',
  ],
  ALLOWED_ATTR: [
    'style', 'class', 'id',
    'src', 'alt', 'width', 'height', 'loading',
    'href', 'target', 'rel',
    'data-placeholder',
    // SVG attributes
    'viewBox', 'xmlns', 'd', 'fill', 'stroke', 'stroke-width',
    'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray', 'stroke-dashoffset',
    'cx', 'cy', 'r', 'rx', 'ry', 'x', 'y', 'x1', 'y1', 'x2', 'y2',
    'transform', 'opacity', 'font-size', 'text-anchor', 'dominant-baseline',
    'points', 'clip-path', 'clip-rule', 'fill-rule', 'fill-opacity', 'stroke-opacity',
    'offset', 'stop-color', 'stop-opacity', 'gradientUnits', 'gradientTransform',
    'spreadMethod', 'stdDeviation', 'dx', 'dy', 'result', 'in', 'in2',
    'flood-color', 'flood-opacity', 'operator', 'preserveAspectRatio',
  ],
  FORBID_TAGS: [
    'script', 'iframe', 'object', 'embed', 'form', 'input',
    'textarea', 'select', 'button', 'link', 'meta', 'style',
    'base', 'applet', 'frame', 'frameset',
  ],
  FORBID_ATTR: [
    'onerror', 'onload', 'onclick', 'onmouseover', 'onmouseout',
    'onfocus', 'onblur', 'onsubmit', 'onkeydown', 'onkeyup', 'onkeypress',
    'onmousedown', 'onmouseup', 'ondblclick', 'onchange', 'oninput',
  ],
  ALLOW_DATA_ATTR: true,
};

// Block dangerous CSS patterns in inline styles
const DANGEROUS_CSS = /expression\s*\(|javascript:|url\s*\(\s*["']?\s*(?:data:(?!image)|javascript:)|@import|behavior\s*:/i;

// Register hook once
let hookRegistered = false;
function ensureSanitizeHook() {
  if (hookRegistered) return;
  hookRegistered = true;
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node.hasAttribute('style')) {
      const style = node.getAttribute('style') || '';
      if (DANGEROUS_CSS.test(style)) {
        node.removeAttribute('style');
      }
    }
    // Force links to open in new tab
    if (node.tagName === 'A') {
      node.setAttribute('target', '_blank');
      node.setAttribute('rel', 'noopener noreferrer');
    }
    // Add referrerPolicy to images (no crossorigin — external servers often lack CORS headers)
    if (node.tagName === 'IMG') {
      node.setAttribute('referrerpolicy', 'no-referrer');
    }
  });
}

export function HtmlSlide({ html, isThumb = false }: HtmlSlideProps) {
  ensureSanitizeHook();
  const sanitized = DOMPurify.sanitize(html, PURIFY_CONFIG);

  return (
    <div
      className="w-full h-full"
      style={{
        position: 'relative',
        overflow: 'hidden',
        // Scale down pointer events for thumbnails
        pointerEvents: isThumb ? 'none' : undefined,
      }}
      dangerouslySetInnerHTML={{ __html: sanitized }}
    />
  );
}
