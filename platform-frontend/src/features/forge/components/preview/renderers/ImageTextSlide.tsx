import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement } from '../normalizers';
import { BodyElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function ImageTextSlide({ slide, theme, isThumb }: Props) {
  const imageEl = findElement(slide, 'image');
  const bodyEl = findElement(slide, 'body');

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

      {/* Image placeholder */}
      <div
        className={`flex-1 flex items-center justify-center ${isThumb ? 'text-[4px]' : 'text-sm'}`}
        style={{
          backgroundColor: theme.colors.primary + '10',
          color: theme.colors.text_light,
        }}
      >
        {imageEl?.content ? (
          <span className="text-center px-2 truncate">{typeof imageEl.content === 'string' ? imageEl.content : '[Image]'}</span>
        ) : (
          <span>[Image]</span>
        )}
      </div>
    </div>
  );
}
