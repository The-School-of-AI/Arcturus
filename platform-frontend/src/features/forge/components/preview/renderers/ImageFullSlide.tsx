import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement } from '../normalizers';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function ImageFullSlide({ slide, theme, isThumb }: Props) {
  const imageEl = findElement(slide, 'image');
  const bodyEl = findElement(slide, 'body');

  return (
    <div
      className="flex items-center justify-center h-full relative"
      style={{
        backgroundColor: theme.colors.primary + '10',
        color: theme.colors.text_light,
      }}
    >
      {/* Image placeholder */}
      <div className={isThumb ? 'text-[4px]' : 'text-sm'}>
        {imageEl?.content ? (
          <span>{typeof imageEl.content === 'string' ? imageEl.content : '[Full Image]'}</span>
        ) : (
          <span>[Full Bleed Image]</span>
        )}
      </div>

      {/* Title overlay */}
      {slide.title && (
        <div
          className={`absolute bottom-0 left-0 right-0 ${isThumb ? 'p-1' : 'p-6'}`}
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
