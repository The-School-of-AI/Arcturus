import type { SlideTheme } from './SlideFrame';
import { resolveSlideColors } from './theme-utils';
import type { Slide } from '../normalizers';
import { findElement } from '../normalizers';
import { BodyElement, AnimatedElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
  imageBaseUrl?: string;
  availableImageIds?: ReadonlySet<string>;
}

/** Extract image URL and alt text from the image element content. */
function parseImageContent(content: unknown): { url: string | null; alt: string } {
  if (!content) return { url: null, alt: 'Image' };
  if (typeof content === 'string') {
    // Legacy: plain description string — check if it looks like a URL
    if (content.startsWith('http://') || content.startsWith('https://')) {
      return { url: content, alt: 'Slide image' };
    }
    // Try parsing as JSON
    try {
      const parsed = JSON.parse(content);
      if (parsed && typeof parsed === 'object') {
        return { url: parsed.url || null, alt: parsed.alt || parsed.description || 'Image' };
      }
    } catch { /* not JSON, use as description */ }
    return { url: null, alt: content };
  }
  if (typeof content === 'object' && content !== null) {
    const obj = content as Record<string, unknown>;
    return { url: (obj.url as string) || null, alt: (obj.alt as string) || (obj.description as string) || 'Image' };
  }
  return { url: null, alt: 'Image' };
}

export function ImageTextSlide({ slide, theme, isThumb, imageBaseUrl, availableImageIds }: Props) {
  const sc = resolveSlideColors(slide.metadata?.slide_style, theme);
  const imageEl = findElement(slide, 'image');
  const bodyEl = findElement(slide, 'body');

  const { url: externalUrl, alt } = parseImageContent(imageEl?.content);

  // Prefer external URL, then generated image, then placeholder
  const generatedReady = !!(imageBaseUrl && availableImageIds?.has(slide.id));
  const generatedUrl = generatedReady ? `${imageBaseUrl}/${slide.id}` : null;
  const imageUrl = externalUrl || generatedUrl;

  return (
    <div className={`flex h-full ${isThumb ? 'p-1' : ''}`}>
      {/* Text side */}
      <div className={`flex-1 flex flex-col justify-center ${isThumb ? 'p-1' : 'p-[6%]'}`}>
        {slide.title && (
          <AnimatedElement animation="rise" delay={80} isThumb={isThumb}>
            <div
              className={isThumb ? 'text-[5px] font-bold mb-0.5' : 'text-xl font-bold mb-3'}
              style={{
                color: sc.titleColor,
                fontFamily: sc.titleFont,
                ...sc.titleStyle,
              }}
            >
              {slide.title}
            </div>
          </AnimatedElement>
        )}
        {bodyEl?.content && typeof bodyEl.content === 'string' && (
          <AnimatedElement animation="rise" delay={160} isThumb={isThumb}>
            <BodyElement content={bodyEl.content} theme={theme} isThumb={isThumb} bodyColor={sc.bodyColor} bodyStyle={sc.bodyStyle} accentColor={sc.accentColor} />
          </AnimatedElement>
        )}
      </div>

      {/* Image side */}
      <div
        className={`flex-1 flex flex-col items-center justify-center overflow-hidden ${isThumb ? 'text-[4px]' : 'text-sm'}`}
        style={{
          backgroundColor: imageUrl ? undefined : theme.colors.primary + '10',
          color: theme.colors.text_light,
        }}
      >
        <AnimatedElement animation="scale" delay={200} isThumb={isThumb}>
          {imageUrl ? (
            <img
              src={imageUrl}
              alt={alt}
              className="object-cover w-full h-full"
              referrerPolicy="no-referrer"
              crossOrigin="anonymous"
            />
          ) : (
            <>
              {!isThumb && (
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke={theme.colors.primary + '60'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <path d="m21 15-5-5L5 21" />
                </svg>
              )}
              <span className={`text-center ${isThumb ? 'px-0.5 line-clamp-2' : 'px-4 italic opacity-70 text-xs'}`}>
                {alt}
              </span>
            </>
          )}
        </AnimatedElement>
      </div>
    </div>
  );
}
