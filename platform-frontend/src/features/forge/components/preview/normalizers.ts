/**
 * Content normalization layer for slide preview rendering.
 *
 * Mirrors parsing logic embedded in the PPTX exporter (core/studio/slides/exporter.py)
 * so that HTML previews match exported output.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

// ── Types ────────────────────────────────────────────────────────────────────

export interface SlideElement {
  id: string;
  type: string;
  content: any;
}

export interface Slide {
  id: string;
  slide_type: string;
  title?: string;
  elements: SlideElement[];
  speaker_notes?: string;
  metadata?: Record<string, any>;
  html?: string;
}

export interface TimelineItem {
  date: string;
  title: string;
  description: string;
  tag: string;
}

export interface AgendaItem {
  title: string;
  description: string;
}

export interface ComparisonColumn {
  label: string;
  body: string;
}

export interface CalloutBox {
  text: string;
  attribution: string;
}

export interface StatItem {
  value: string;
  label: string;
}

export interface TableData {
  headers: string[];
  rows: any[][];
  badge_column?: number | null;
}

export interface TitleMeta {
  badge?: string;
  date?: string;
  category?: string;
  isClosing: boolean;
  titleLines: string[];
}

// ── Helpers ──────────────────────────────────────────────────────────────────

export function findElement(slide: Slide, type: string): SlideElement | undefined {
  return slide.elements.find(el => el.type === type);
}

export function findElements(slide: Slide, type: string): SlideElement[] {
  return slide.elements.filter(el => el.type === type);
}

// ── Normalizers ──────────────────────────────────────────────────────────────

/**
 * Timeline pipe-delimited parsing (exporter.py:1489-1505).
 * Bullet items containing `|` → parsed as `Date | Title | Description | TAG`.
 */
export function normalizeTimeline(items: any[]): { hasPipeFormat: boolean; entries: TimelineItem[] } {
  const stringItems = items.map(i => String(i));
  const hasPipeFormat = stringItems.some(item => item.includes('|'));

  if (!hasPipeFormat) {
    return {
      hasPipeFormat: false,
      entries: stringItems.map(item => ({ date: '', title: item, description: '', tag: '' })),
    };
  }

  const entries = stringItems.map(item => {
    const parts = item.split('|').map(p => p.trim());
    return {
      date: parts[0] || '',
      title: parts[1] || '',
      description: parts[2] || '',
      tag: parts[3] || '',
    };
  });

  return { hasPipeFormat: true, entries };
}

/**
 * Agenda "Title: Description" parsing (exporter.py:2101-2108).
 * Bullet items containing `:` split into title + description.
 */
export function normalizeAgendaItems(items: any[]): AgendaItem[] {
  return items.map(item => {
    const str = String(item);
    if (str.includes(':')) {
      const [title, ...rest] = str.split(':');
      return { title: title.trim(), description: rest.join(':').trim() };
    }
    return { title: str, description: '' };
  });
}

/**
 * Comparison column header extraction (exporter.py:1361-1370).
 * First line of body element (if <30 chars + has \n) becomes column label.
 */
export function normalizeComparisonColumn(text: string): ComparisonColumn {
  if (typeof text !== 'string') return { label: '', body: String(text ?? '') };
  if (text.includes('\n')) {
    const [firstLine, ...rest] = text.split('\n');
    if (firstLine.length < 30) {
      return { label: firstLine, body: rest.join('\n') };
    }
  }
  return { label: '', body: text };
}

/**
 * Callout box JSON parsing (exporter.py:1425-1459).
 * Content may be JSON string → parse to {text, attribution} dict.
 */
export function normalizeCalloutBox(content: any): CalloutBox {
  if (typeof content === 'string') {
    try {
      const parsed = JSON.parse(content);
      if (typeof parsed === 'object' && parsed !== null) {
        return { text: parsed.text || '', attribution: parsed.attribution || '' };
      }
    } catch {
      return { text: content, attribution: '' };
    }
  }
  if (typeof content === 'object' && content !== null) {
    return { text: content.text || '', attribution: content.attribution || '' };
  }
  return { text: String(content ?? ''), attribution: '' };
}

/**
 * Stat JSON-string payload parsing (exporter.py:1847-1865).
 * stat_callout content may be JSON string encoding [{value, label}] → parse to array.
 */
export function normalizeStats(content: any): StatItem[] {
  let items: any[] = [];

  if (Array.isArray(content)) {
    items = content;
  } else if (typeof content === 'string') {
    try {
      const parsed = JSON.parse(content);
      if (Array.isArray(parsed)) {
        items = parsed;
      }
    } catch {
      return [];
    }
  }

  return items
    .filter(item => typeof item === 'object' && item !== null && 'value' in item)
    .slice(0, 3)
    .map(item => ({
      value: String(item.value ?? ''),
      label: String(item.label ?? ''),
    }));
}

/**
 * Title metadata extraction (exporter.py:1077-1086) +
 * multi-line title split (exporter.py:1088-1109) +
 * closing title detection (exporter.py:1074).
 */
export function normalizeTitleMeta(
  slide: Slide,
  slideIndex: number,
  totalSlides: number,
): TitleMeta {
  const metadata = slide.metadata ?? {};
  const isClosing = slideIndex === totalSlides - 1 && totalSlides > 1;
  const titleText = slide.title || '';
  const titleLines = titleText.includes('\n') ? titleText.split('\n', 2) : [titleText];

  return {
    badge: metadata.badge,
    date: metadata.date,
    category: metadata.category,
    isClosing,
    titleLines,
  };
}

/**
 * Table data normalization (exporter.py:2195-2277).
 * Content may be JSON string → parse to dict. badge_column → int.
 */
export function normalizeTableData(content: any): TableData {
  let data: any = {};

  if (typeof content === 'string') {
    try {
      data = JSON.parse(content);
    } catch {
      return { headers: [], rows: [], badge_column: null };
    }
  } else if (typeof content === 'object' && content !== null) {
    data = content;
  }

  const headers: string[] = Array.isArray(data.headers) ? data.headers.map(String) : [];
  const rows: any[][] = Array.isArray(data.rows) ? data.rows : [];

  let badge_column: number | null = null;
  if (data.badge_column != null) {
    const parsed = Number(data.badge_column);
    if (!isNaN(parsed)) badge_column = parsed;
  }

  return { headers, rows, badge_column };
}
