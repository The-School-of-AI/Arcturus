import type { SlideTheme } from './SlideFrame';
import type { Slide } from '../normalizers';
import { findElement, normalizeTableData } from '../normalizers';
import { KickerElement, TakeawayElement, TableElement } from './elements';

interface Props {
  slide: Slide;
  theme: SlideTheme;
  isThumb?: boolean;
}

export function TableSlide({ slide, theme, isThumb }: Props) {
  const kickerEl = findElement(slide, 'kicker');
  const tableEl = findElement(slide, 'table_data');
  const sourceEl = findElement(slide, 'source_citation');
  const takeawayEl = findElement(slide, 'takeaway');

  const tableData = tableEl ? normalizeTableData(tableEl.content) : { headers: [], rows: [], badge_column: null };

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

      <div className="flex-1 min-h-0 overflow-hidden">
        <TableElement
          headers={tableData.headers}
          rows={tableData.rows}
          badgeColumn={tableData.badge_column}
          sourceCitation={sourceEl?.content ? String(sourceEl.content) : undefined}
          theme={theme}
          isThumb={isThumb}
        />
      </div>

      {takeawayEl?.content && (
        <TakeawayElement content={takeawayEl.content} theme={theme} isThumb={isThumb} />
      )}
    </div>
  );
}
