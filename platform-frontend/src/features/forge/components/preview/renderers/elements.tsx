/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import {
  ResponsiveContainer,
  BarChart, Bar,
  LineChart, Line,
  AreaChart, Area,
  PieChart, Pie, Cell,
  ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts';
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

// ── Chart Preview (recharts) ────────────────────────────────────────────────

interface ChartPlaceholderProps extends ElementProps {
  content: any;
}

/** Generate a palette from theme colors + fallbacks for multi-series charts. */
function chartPalette(theme: SlideTheme): string[] {
  return [
    theme.colors.primary,
    theme.colors.accent,
    theme.colors.secondary,
    '#6366f1',
    '#f59e0b',
    '#10b981',
    '#ef4444',
    '#8b5cf6',
  ];
}

export function ChartPlaceholder({ content, theme, isThumb }: ChartPlaceholderProps) {
  if (!content || typeof content !== 'object') {
    // String content (e.g. "Revenue growth chart") — show a labeled placeholder
    const label = typeof content === 'string' ? content : 'Chart';
    return (
      <div
        className={`flex items-center justify-center ${isThumb ? 'text-[4px]' : 'text-xs py-6'}`}
        style={{ color: theme.colors.text_light }}
      >
        [{label}]
      </div>
    );
  }

  const chartType = (content.chart_type || content.type || 'bar').toLowerCase();
  const title: string = content.title || '';
  const categories: string[] = Array.isArray(content.categories) ? content.categories : [];
  const series: { name: string; values: number[] }[] = Array.isArray(content.series) ? content.series : [];
  const points: { x: number; y: number }[] = Array.isArray(content.points) ? content.points : [];

  // Need at least some data to render a chart
  const hasCartesianData = categories.length > 0 && series.length > 0;
  const hasPieData = hasCartesianData;
  const hasScatterData = points.length > 0 || (series.length > 0 && series[0]?.values?.length > 0);

  const canRender =
    (chartType === 'scatter' && hasScatterData) ||
    (chartType === 'pie' || chartType === 'doughnut' ? hasPieData : hasCartesianData);

  // Fall back to a simple label if data is insufficient
  if (!canRender) {
    return (
      <div
        className={`flex items-center justify-center ${isThumb ? 'text-[4px]' : 'text-xs py-6'}`}
        style={{ color: theme.colors.text_light }}
      >
        [{chartType} chart]
      </div>
    );
  }

  const PALETTE = chartPalette(theme);
  const textColor = theme.colors.text_light;
  const gridColor = theme.colors.text_light + '20';

  // Data transforms
  const cartesianData = categories.map((cat, i) => {
    const row: Record<string, string | number> = { name: cat };
    series.forEach(s => { row[s.name] = s.values?.[i] ?? 0; });
    return row;
  });

  const pieData = categories.map((cat, i) => ({
    name: cat,
    value: series[0]?.values?.[i] ?? 0,
  }));

  const scatterData = points.length > 0
    ? points
    : (series[0]?.values || []).map((v, i) => ({ x: i, y: v }));

  const compact = !!isThumb;

  function renderChart(): React.ReactElement {
    switch (chartType) {
      case 'pie':
      case 'doughnut':
        return (
          <PieChart>
            <Pie
              data={pieData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={chartType === 'doughnut' ? (compact ? '35%' : '45%') : 0}
              outerRadius={compact ? '85%' : '75%'}
              label={compact ? false : ({ name, percent }: any) =>
                `${name} ${(percent * 100).toFixed(0)}%`
              }
              labelLine={!compact}
              fontSize={compact ? 3 : 10}
            >
              {pieData.map((_, i) => (
                <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
              ))}
            </Pie>
            {!compact && <Tooltip />}
          </PieChart>
        );

      case 'scatter':
        return (
          <ScatterChart>
            {!compact && <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />}
            <XAxis dataKey="x" hide={compact} tick={{ fill: textColor, fontSize: 10 }} />
            <YAxis dataKey="y" hide={compact} tick={{ fill: textColor, fontSize: 10 }} />
            <Scatter data={scatterData} fill={PALETTE[0]} r={compact ? 2 : 4} />
            {!compact && <Tooltip />}
          </ScatterChart>
        );

      case 'line':
        return (
          <LineChart data={cartesianData}>
            {!compact && <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />}
            <XAxis dataKey="name" hide={compact} tick={{ fill: textColor, fontSize: 10 }} />
            <YAxis hide={compact} tick={{ fill: textColor, fontSize: 10 }} />
            {series.map((s, i) => (
              <Line
                key={s.name}
                type="monotone"
                dataKey={s.name}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={compact ? 1.5 : 2}
                dot={!compact}
              />
            ))}
            {!compact && <Tooltip />}
          </LineChart>
        );

      case 'area':
        return (
          <AreaChart data={cartesianData}>
            {!compact && <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />}
            <XAxis dataKey="name" hide={compact} tick={{ fill: textColor, fontSize: 10 }} />
            <YAxis hide={compact} tick={{ fill: textColor, fontSize: 10 }} />
            {series.map((s, i) => (
              <Area
                key={s.name}
                type="monotone"
                dataKey={s.name}
                fill={PALETTE[i % PALETTE.length] + '40'}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={compact ? 1 : 2}
              />
            ))}
            {!compact && <Tooltip />}
          </AreaChart>
        );

      case 'bar':
      case 'column':
      case 'funnel':
      default:
        return (
          <BarChart data={cartesianData}>
            {!compact && <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />}
            <XAxis dataKey="name" hide={compact} tick={{ fill: textColor, fontSize: 10 }} />
            <YAxis hide={compact} tick={{ fill: textColor, fontSize: 10 }} />
            {series.map((s, i) => (
              <Bar
                key={s.name}
                dataKey={s.name}
                fill={PALETTE[i % PALETTE.length]}
                radius={[2, 2, 0, 0]}
              />
            ))}
            {!compact && <Tooltip />}
          </BarChart>
        );
    }
  }

  if (isThumb) {
    return (
      <div className="w-full h-full" style={{ minHeight: 16 }}>
        <ResponsiveContainer width="100%" height="100%">
          {renderChart()}
        </ResponsiveContainer>
      </div>
    );
  }

  return (
    <div className="w-full">
      {title && (
        <div
          className="text-xs font-medium mb-2 text-center"
          style={{ color: textColor }}
        >
          {title}
        </div>
      )}
      <ResponsiveContainer width="100%" height={220}>
        {renderChart()}
      </ResponsiveContainer>
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
