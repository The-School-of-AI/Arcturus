import type { SlideTheme } from './SlideFrame';
import { resolveSlideColors } from './theme-utils';
import type { Slide } from '../normalizers';
import { findElement } from '../normalizers';
import { CodeBlockElement, BodyElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function CodeSlide({ slide, theme, isThumb }: Props) {
  const sc = resolveSlideColors(slide.metadata?.slide_style, theme);
  const codeEl = findElement(slide, 'code');
  const bodyEl = findElement(slide, 'body');

  return (
    <div className={`flex flex-col h-full ${isThumb ? 'p-2' : 'p-[6%]'}`}>
      {slide.title && (
        <div
          className={isThumb ? 'text-[5px] font-bold mb-1' : 'text-xl font-bold mb-4'}
          style={{
            color: sc.titleColor,
            fontFamily: sc.titleFont,
            ...sc.titleStyle,
          }}
        >
          {slide.title}
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-hidden">
        {codeEl?.content && (
          <CodeBlockElement content={codeEl.content} theme={theme} isThumb={isThumb} />
        )}
      </div>

      {bodyEl?.content && typeof bodyEl.content === 'string' && !isThumb && (
        <div className="mt-3">
          <BodyElement content={bodyEl.content} theme={theme} isThumb={isThumb} bodyColor={sc.bodyColor} bodyStyle={sc.bodyStyle} accentColor={sc.accentColor} />
        </div>
      )}
    </div>
  );
}
