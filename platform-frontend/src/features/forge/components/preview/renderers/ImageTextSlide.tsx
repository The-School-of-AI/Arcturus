import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement } from '../normalizers';
import { BodyElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
  imageBaseUrl?: string;
  availableImageIds?: ReadonlySet<string>;
}

export function ImageTextSlide({ slide, theme, isThumb, imageBaseUrl, availableImageIds }: Props) {
  const imageEl = findElement(slide, 'image');
  const bodyEl = findElement(slide, 'body');

  const imageReady = !!(imageBaseUrl && availableImageIds?.has(slide.id));
  const imageUrl = imageReady ? `${imageBaseUrl}/${slide.id}` : null;

  return (
    <div className={`flex h-full ${isThumb ? 'p-1' : ''}`}>
      {/* Text side */}
      <div className={`flex-1 flex flex-col justify-center ${isThumb ? 'p-1' : 'p-[6%]'}`}>
        {slide.title && (
          <div
            className={isThumb ? 'text-[5px] font-bold mb-0.5' : 'text-xl font-bold mb-3'}
            style={{
              color: theme.colors.primary,
              fontFamily: `"${theme.font_heading}", "Segoe UI", system-ui, sans-serif`,
            }}
          >
            {slide.title}
          </div>
        )}
        {bodyEl?.content && typeof bodyEl.content === 'string' && (
          <BodyElement content={bodyEl.content} theme={theme} isThumb={isThumb} />
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
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={typeof imageEl?.content === 'string' ? imageEl.content : 'Slide image'}
            className="object-cover w-full h-full"
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
            {imageEl?.content && typeof imageEl.content === 'string' ? (
              <span className={`text-center ${isThumb ? 'px-0.5 line-clamp-2' : 'px-4 italic opacity-70 text-xs'}`}>
                {imageEl.content}
              </span>
            ) : (
              <span className="opacity-50">[Image]</span>
            )}
          </>
        )}
      </div>
    </div>
  );
}
