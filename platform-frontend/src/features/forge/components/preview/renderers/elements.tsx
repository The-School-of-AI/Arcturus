/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import type { SlideTheme } from './theme-utils';
import { isDarkBackground } from './theme-utils';

interface ElementProps {
  theme: SlideTheme;
  isThumb?: boolean;
}

// ── Kicker ──────────────────────────────────────────────────────────────────

export function KickerElement({ content, theme, isThumb }: ElementProps & { content: string }) {
  if (!content) return null;
  return (
    <div
      className={isThumb ? 'text-[4px] uppercase tracking-wider font-bold' : 'text-[11px] uppercase tracking-wider font-bold mb-1'}
      style={{ color: theme.colors.accent }}
    >
      {content}
    </div>
  );
}

// ── Takeaway ────────────────────────────────────────────────────────────────

export function TakeawayElement({ content, theme, isThumb }: ElementProps & { content: string }) {
  if (!content) return null;
  return (
    <div
      className={isThumb ? 'mt-auto px-1 py-0.5 text-[3px]' : 'mt-auto px-4 py-2 rounded-md text-xs'}
      style={{
        backgroundColor: theme.colors.accent + '18',
        color: theme.colors.accent,
        fontFamily: `"${theme.font_body}", "Segoe UI", system-ui, sans-serif`,
      }}
    >
      {content}
    </div>
  );
}

// ── Bullet List ─────────────────────────────────────────────────────────────

export function BulletListElement({ items, theme, isThumb }: ElementProps & { items: string[] }) {
  if (!items?.length) return null;
  return (
    <ul className={isThumb ? 'space-y-0 text-[3.5px] pl-2' : 'space-y-1.5 text-sm pl-1'}>
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-1.5">
          <span
            className={isThumb ? 'mt-[1px] w-[2px] h-[2px] rounded-full shrink-0' : 'mt-[7px] w-1.5 h-1.5 rounded-full shrink-0'}
            style={{ backgroundColor: theme.colors.accent }}
          />
          <span style={{ color: theme.colors.text }}>{item}</span>
        </li>
      ))}
    </ul>
  );
}

// ── Body Text ───────────────────────────────────────────────────────────────

export function BodyElement({ content, theme, isThumb }: ElementProps & { content: string }) {
  if (!content) return null;
  return (
    <div
      className={isThumb ? 'text-[3.5px] leading-tight' : 'text-sm leading-relaxed whitespace-pre-wrap'}
      style={{ color: theme.colors.text }}
    >
      {content}
    </div>
  );
}

// ── Stat Callout ────────────────────────────────────────────────────────────

interface StatCalloutProps extends ElementProps {
  stats: { value: string; label: string }[];
}

export function StatCalloutElement({ stats, theme, isThumb }: StatCalloutProps) {
  if (!stats.length) return null;
  return (
    <div className={`flex items-center justify-center ${isThumb ? 'gap-2' : 'gap-8'}`}>
      {stats.map((stat, i) => (
        <React.Fragment key={i}>
          {i > 0 && (
            <div
              className={isThumb ? 'w-[0.5px] h-4' : 'w-px h-16'}
              style={{ backgroundColor: theme.colors.text_light + '40' }}
            />
          )}
          <div className="text-center">
            <div
              className={isThumb ? 'text-[6px] font-bold' : 'text-4xl font-bold'}
              style={{
                color: theme.colors.accent,
                fontFamily: `"${theme.font_heading}", "Segoe UI", system-ui, sans-serif`,
              }}
            >
              {stat.value}
            </div>
            <div
              className={isThumb ? 'text-[3px]' : 'text-xs mt-1'}
              style={{ color: theme.colors.text_light }}
            >
              {stat.label}
            </div>
          </div>
        </React.Fragment>
      ))}
    </div>
  );
}

// ── Chart Placeholder ───────────────────────────────────────────────────────

interface ChartPlaceholderProps extends ElementProps {
  content: any;
}

const CHART_ICONS: Record<string, string> = {
  bar: '\u2581\u2583\u2585\u2587',
  column: '\u2581\u2583\u2585\u2587',
  line: '\u279F',
  area: '\u25E2',
  pie: '\u25D4',
  doughnut: '\u25D4',
  scatter: '\u2022\u2022\u2022',
  funnel: '\u25BD',
};

export function ChartPlaceholder({ content, theme, isThumb }: ChartPlaceholderProps) {
  if (!content || typeof content !== 'object') return null;
  const chartType = content.chart_type || content.type || 'chart';
  const title = content.title || '';
  const categories = content.categories?.length || 0;
  const series = content.series?.length || 0;
  const icon = CHART_ICONS[chartType.toLowerCase()] || '\u2581\u2583\u2585\u2587';

  if (isThumb) {
    return (
      <div
        className="flex items-center justify-center text-[6px] rounded"
        style={{ backgroundColor: theme.colors.primary + '10', color: theme.colors.primary }}
      >
        {icon}
      </div>
    );
  }

  return (
    <div
      className="flex flex-col items-center justify-center py-8 rounded-lg border border-dashed"
      style={{
        borderColor: theme.colors.primary + '40',
        backgroundColor: theme.colors.primary + '08',
      }}
    >
      <div className="text-3xl mb-2" style={{ color: theme.colors.primary }}>{icon}</div>
      <div className="text-sm font-medium" style={{ color: theme.colors.primary }}>
        {chartType.charAt(0).toUpperCase() + chartType.slice(1)} Chart
      </div>
      {title && (
        <div className="text-xs mt-1" style={{ color: theme.colors.text_light }}>{title}</div>
      )}
      {(categories > 0 || series > 0) && (
        <div className="text-[10px] mt-1" style={{ color: theme.colors.text_light + 'aa' }}>
          {[
            categories > 0 && `${categories} categories`,
            series > 0 && `${series} series`,
          ].filter(Boolean).join(', ')}
        </div>
      )}
    </div>
  );
}

// ── Code Block ──────────────────────────────────────────────────────────────

export function CodeBlockElement({ content, theme, isThumb }: ElementProps & { content: string }) {
  if (!content) return null;
  return (
    <pre
      className={isThumb
        ? 'text-[3px] p-1 rounded overflow-hidden leading-tight'
        : 'text-xs p-4 rounded-lg overflow-x-auto leading-relaxed'
      }
      style={{
        backgroundColor: isDarkBackground(theme.colors.background) ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)',
        color: theme.colors.text,
        fontFamily: '"Fira Code", "Consolas", "Monaco", monospace',
      }}
    >
      <code>{content}</code>
    </pre>
  );
}

// ── Table ───────────────────────────────────────────────────────────────────

interface TableElementProps extends ElementProps {
  headers: string[];
  rows: any[][];
  badgeColumn?: number | null;
  sourceCitation?: string;
}

export function TableElement({ headers, rows, badgeColumn, sourceCitation, theme, isThumb }: TableElementProps) {
  if (!headers.length) return null;

  if (isThumb) {
    return (
      <div className="text-[3px] overflow-hidden rounded" style={{ color: theme.colors.text }}>
        <div className="flex" style={{ backgroundColor: theme.colors.primary, color: '#fff' }}>
          {headers.map((h, i) => (
            <div key={i} className="flex-1 px-0.5 py-0.5 font-bold truncate">{h}</div>
          ))}
        </div>
        {rows.slice(0, 3).map((row, ri) => (
          <div
            key={ri}
            className="flex"
            style={{ backgroundColor: ri % 2 === 1 ? theme.colors.primary + '08' : 'transparent' }}
          >
            {headers.map((_, ci) => (
              <div key={ci} className="flex-1 px-0.5 py-0.5 truncate">
                {ci < row.length ? String(row[ci]) : ''}
              </div>
            ))}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr>
            {headers.map((header, i) => (
              <th
                key={i}
                className="px-3 py-2 text-left font-semibold text-xs"
                style={{
                  backgroundColor: theme.colors.primary,
                  color: '#ffffff',
                  fontFamily: `"${theme.font_heading}", "Segoe UI", system-ui, sans-serif`,
                }}
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr
              key={ri}
              style={{
                backgroundColor: ri % 2 === 1 ? theme.colors.primary + '08' : 'transparent',
              }}
            >
              {headers.map((_, ci) => {
                const cellValue = ci < row.length ? String(row[ci]) : '';
                const isBadge = badgeColumn != null && ci === badgeColumn && cellValue;
                return (
                  <td key={ci} className="px-3 py-1.5" style={{ color: theme.colors.text }}>
                    {isBadge ? (
                      <span
                        className="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold text-white"
                        style={{ backgroundColor: theme.colors.accent }}
                      >
                        {cellValue}
                      </span>
                    ) : (
                      cellValue
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {sourceCitation && (
        <div
          className="text-right text-[10px] mt-1 pr-1"
          style={{ color: theme.colors.text_light }}
        >
          {sourceCitation}
        </div>
      )}
    </div>
  );
}

// ── Quote ───────────────────────────────────────────────────────────────────

interface QuoteElementProps extends ElementProps {
  quote: string;
  attribution?: string;
}

export function QuoteElement({ quote, attribution, theme, isThumb }: QuoteElementProps) {
  if (!quote) return null;

  if (isThumb) {
    return (
      <div className="text-center px-2">
        <span className="text-[8px] font-bold" style={{ color: theme.colors.accent }}>&ldquo;</span>
        <span className="text-[3.5px] italic" style={{ color: theme.colors.text }}>{quote}</span>
      </div>
    );
  }

  return (
    <div className="text-center px-8">
      <div className="text-5xl font-bold leading-none mb-2" style={{ color: theme.colors.accent }}>
        &ldquo;
      </div>
      <div
        className="text-lg italic leading-relaxed"
        style={{
          color: theme.colors.text,
          fontFamily: `"${theme.font_body}", "Segoe UI", system-ui, sans-serif`,
        }}
      >
        {quote}
      </div>
      {attribution && (
        <div className="mt-3 text-sm" style={{ color: theme.colors.text_light }}>
          &mdash; {attribution}
        </div>
      )}
    </div>
  );
}
