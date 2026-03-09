import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement, normalizeAgendaItems } from '../normalizers';
import { KickerElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function AgendaSlide({ slide, theme, isThumb }: Props) {
  const kickerEl = findElement(slide, 'kicker');
  const bulletEl = findElement(slide, 'bullet_list');

  const items = bulletEl?.content && Array.isArray(bulletEl.content) ? bulletEl.content : [];
  const agendaItems = normalizeAgendaItems(items);

  const cols = agendaItems.length <= 3 ? agendaItems.length : agendaItems.length <= 6 ? 3 : 4;

  return (
    <div className={`flex flex-col h-full ${isThumb ? 'p-2' : 'p-[6%]'}`}>
      {kickerEl?.content && (
        <KickerElement content={kickerEl.content} theme={theme} isThumb={isThumb} />
      )}

      {slide.title && (
        <div
          className={isThumb ? 'text-[5px] font-bold mb-1' : 'text-xl font-bold mb-4'}
          style={{
            color: theme.colors.primary,
            fontFamily: `"${theme.font_heading}", "Segoe UI", system-ui, sans-serif`,
          }}
        >
          {slide.title}
        </div>
      )}

      <div
        className={`flex-1 grid min-h-0 ${isThumb ? 'gap-0.5' : 'gap-3'}`}
        style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
      >
        {agendaItems.map((item, i) => (
          <div
            key={i}
            className={isThumb ? 'p-0.5 rounded' : 'p-4 rounded-lg'}
            style={{ backgroundColor: theme.colors.primary + '08' }}
          >
            {/* Numbered badge */}
            <div
              className={isThumb
                ? 'w-2 h-2 rounded-full flex items-center justify-center text-[2.5px] font-bold text-white mb-0.5'
                : 'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white mb-2'
              }
              style={{ backgroundColor: theme.colors.accent }}
            >
              {i + 1}
            </div>
            <div
              className={isThumb ? 'text-[3px] font-bold' : 'text-sm font-semibold'}
              style={{ color: theme.colors.text }}
            >
              {item.title}
            </div>
            {item.description && !isThumb && (
              <div className="text-xs mt-1" style={{ color: theme.colors.text_light }}>
                {item.description}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
