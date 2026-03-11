import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement } from '../normalizers';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
  imageBaseUrl?: string;
  availableImageIds?: ReadonlySet<string>;
}

export function ImageFullSlide({ slide, theme, isThumb, imageBaseUrl, availableImageIds }: Props) {
  const imageEl = findElement(slide, 'image');
  const bodyEl = findElement(slide, 'body');

  const imageReady = !!(imageBaseUrl && availableImageIds?.has(slide.id));
  const imageUrl = imageReady ? `${imageBaseUrl}/${slide.id}` : null;

  return (
    <div
      className="flex items-center justify-center h-full relative overflow-hidden"
      style={{
        backgroundColor: theme.colors.primary + '10',
        color: theme.colors.text_light,
      }}
    >
      {/* Real image (full bleed) */}
      {imageUrl ? (
        <img
          src={imageUrl}
          alt={typeof imageEl?.content === 'string' ? imageEl.content : 'Slide image'}
          className="absolute inset-0 w-full h-full object-cover"
        />
      ) : (
        <div className={`flex flex-col items-center gap-2 ${isThumb ? 'text-[4px]' : 'text-sm'}`}>
          {!isThumb && (
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke={theme.colors.primary + '50'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <path d="m21 15-5-5L5 21" />
            </svg>
          )}
          {imageEl?.content && typeof imageEl.content === 'string' ? (
            <span className={isThumb ? 'line-clamp-1' : 'italic opacity-60 text-xs text-center px-6'}>
              {imageEl.content}
            </span>
          ) : (
            <span className="opacity-50">[Full Bleed Image]</span>
          )}
        </div>
      )}

      {/* Title overlay */}
      {slide.title && (
        <div
          className={`absolute bottom-0 left-0 right-0 ${isThumb ? 'p-1' : 'p-6'} z-10`}
          style={{ background: 'linear-gradient(transparent, rgba(0,0,0,0.7))' }}
        >
          <div
            className={isThumb ? 'text-[5px] font-bold' : 'text-xl font-bold'}
            style={{
              color: '#ffffff',
              fontFamily: `"${theme.font_heading}", "Segoe UI", system-ui, sans-serif`,
            }}
          >
            {slide.title}
          </div>
          {bodyEl?.content && (
            <div
              className={isThumb ? 'text-[3px] mt-0.5' : 'text-sm mt-2'}
              style={{ color: '#dddddd' }}
            >
              {bodyEl.content}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
