import { describe, it, expect } from 'vitest';
import {
  normalizeTimeline,
  normalizeAgendaItems,
  normalizeComparisonColumn,
  normalizeCalloutBox,
  normalizeStats,
  normalizeTitleMeta,
  normalizeTableData,
  findElement,
  type Slide,
} from '../features/forge/components/preview/normalizers';
import { RENDERERS } from '../features/forge/components/preview/renderers';

// ── Normalizer Tests ─────────────────────────────────────────────────────────

describe('normalizeTimeline', () => {
  it('parses pipe-delimited format', () => {
    const items = ['Q1 2024 | Launch MVP | Initial release | DONE', 'Q2 2024 | Scale | Growth phase'];
    const result = normalizeTimeline(items);
    expect(result.hasPipeFormat).toBe(true);
    expect(result.entries).toHaveLength(2);
    expect(result.entries[0]).toEqual({
      date: 'Q1 2024',
      title: 'Launch MVP',
      description: 'Initial release',
      tag: 'DONE',
    });
    expect(result.entries[1]).toEqual({
      date: 'Q2 2024',
      title: 'Scale',
      description: 'Growth phase',
      tag: '',
    });
  });

  it('returns hasPipeFormat=false for non-pipe items', () => {
    const items = ['Step one', 'Step two'];
    const result = normalizeTimeline(items);
    expect(result.hasPipeFormat).toBe(false);
    expect(result.entries[0].title).toBe('Step one');
  });
});

describe('normalizeAgendaItems', () => {
  it('parses "Title: Description" format', () => {
    const items = ['Introduction: Welcome and overview', 'Strategy: Q4 plan details', 'Plain item'];
    const result = normalizeAgendaItems(items);
    expect(result).toEqual([
      { title: 'Introduction', description: 'Welcome and overview' },
      { title: 'Strategy', description: 'Q4 plan details' },
      { title: 'Plain item', description: '' },
    ]);
  });

  it('handles items with multiple colons', () => {
    const items = ['Time: 10:00 AM'];
    const result = normalizeAgendaItems(items);
    expect(result[0]).toEqual({ title: 'Time', description: '10:00 AM' });
  });
});

describe('normalizeComparisonColumn', () => {
  it('extracts short first line as label', () => {
    const result = normalizeComparisonColumn('Option A\nThis is the body text for option A');
    expect(result.label).toBe('Option A');
    expect(result.body).toBe('This is the body text for option A');
  });

  it('does not extract long first line as label', () => {
    const longLine = 'This is a very long first line that exceeds thirty characters';
    const result = normalizeComparisonColumn(`${longLine}\nBody`);
    expect(result.label).toBe('');
    expect(result.body).toBe(`${longLine}\nBody`);
  });

  it('returns full text when no newline', () => {
    const result = normalizeComparisonColumn('Just body text');
    expect(result.label).toBe('');
    expect(result.body).toBe('Just body text');
  });
});

describe('normalizeCalloutBox', () => {
  it('parses JSON string to object', () => {
    const result = normalizeCalloutBox('{"text":"Key finding","attribution":"Source"}');
    expect(result).toEqual({ text: 'Key finding', attribution: 'Source' });
  });

  it('handles plain string', () => {
    const result = normalizeCalloutBox('Just a callout');
    expect(result).toEqual({ text: 'Just a callout', attribution: '' });
  });

  it('handles dict object', () => {
    const result = normalizeCalloutBox({ text: 'Hello', attribution: 'World' });
    expect(result).toEqual({ text: 'Hello', attribution: 'World' });
  });
});

describe('normalizeStats', () => {
  it('parses array of stat objects', () => {
    const items = [{ value: '98%', label: 'Accuracy' }, { value: '2M', label: 'Users' }];
    const result = normalizeStats(items);
    expect(result).toEqual([
      { value: '98%', label: 'Accuracy' },
      { value: '2M', label: 'Users' },
    ]);
  });

  it('parses JSON string to stat array', () => {
    const json = JSON.stringify([{ value: '42', label: 'Answer' }]);
    const result = normalizeStats(json);
    expect(result).toEqual([{ value: '42', label: 'Answer' }]);
  });

  it('limits to 3 stats', () => {
    const items = [
      { value: '1', label: 'a' },
      { value: '2', label: 'b' },
      { value: '3', label: 'c' },
      { value: '4', label: 'd' },
    ];
    const result = normalizeStats(items);
    expect(result).toHaveLength(3);
  });

  it('returns empty for invalid input', () => {
    expect(normalizeStats('not json')).toEqual([]);
    expect(normalizeStats(null)).toEqual([]);
  });
});

describe('normalizeTitleMeta', () => {
  const makeSlide = (overrides: Partial<Slide> = {}): Slide => ({
    id: 'test',
    slide_type: 'title',
    title: 'Test Title',
    elements: [],
    ...overrides,
  });

  it('detects closing slide', () => {
    const result = normalizeTitleMeta(makeSlide(), 9, 10);
    expect(result.isClosing).toBe(true);
  });

  it('does not mark first slide as closing', () => {
    const result = normalizeTitleMeta(makeSlide(), 0, 10);
    expect(result.isClosing).toBe(false);
  });

  it('splits multi-line title', () => {
    const result = normalizeTitleMeta(makeSlide({ title: 'Line One\nLine Two' }), 0, 1);
    expect(result.titleLines).toEqual(['Line One', 'Line Two']);
  });

  it('extracts metadata', () => {
    const result = normalizeTitleMeta(
      makeSlide({ metadata: { badge: 'NEW', date: '2024', category: 'Tech' } }),
      0, 1,
    );
    expect(result.badge).toBe('NEW');
    expect(result.date).toBe('2024');
    expect(result.category).toBe('Tech');
  });
});

describe('normalizeTableData', () => {
  it('parses dict content', () => {
    const result = normalizeTableData({
      headers: ['Name', 'Status'],
      rows: [['Alice', 'Active'], ['Bob', 'Inactive']],
      badge_column: 1,
    });
    expect(result.headers).toEqual(['Name', 'Status']);
    expect(result.rows).toHaveLength(2);
    expect(result.badge_column).toBe(1);
  });

  it('parses JSON string content', () => {
    const json = JSON.stringify({ headers: ['Col'], rows: [['Val']] });
    const result = normalizeTableData(json);
    expect(result.headers).toEqual(['Col']);
    expect(result.rows).toEqual([['Val']]);
  });

  it('handles null badge_column', () => {
    const result = normalizeTableData({ headers: ['A'], rows: [] });
    expect(result.badge_column).toBeNull();
  });
});

describe('findElement', () => {
  it('finds element by type', () => {
    const slide: Slide = {
      id: 'test',
      slide_type: 'content',
      elements: [
        { id: '1', type: 'kicker', content: 'Hello' },
        { id: '2', type: 'title', content: 'World' },
      ],
    };
    const el = findElement(slide, 'kicker');
    expect(el?.content).toBe('Hello');
  });

  it('returns undefined for missing type', () => {
    const slide: Slide = { id: 'test', slide_type: 'content', elements: [] };
    expect(findElement(slide, 'missing')).toBeUndefined();
  });
});

// ── Renderer Dispatch Map Tests ──────────────────────────────────────────────

describe('RENDERERS dispatch map', () => {
  const expectedTypes = [
    'title', 'content', 'two_column', 'comparison', 'timeline',
    'chart', 'image_text', 'image_full', 'quote', 'code',
    'team', 'stat', 'stats', 'section_divider', 'agenda', 'table',
  ];

  it('has all 16 entries (15 types + stats alias)', () => {
    expect(Object.keys(RENDERERS)).toHaveLength(16);
  });

  it.each(expectedTypes)('has renderer for "%s"', (type) => {
    expect(RENDERERS[type]).toBeDefined();
    expect(typeof RENDERERS[type]).toBe('function');
  });

  it('"stats" maps to same component as "stat"', () => {
    expect(RENDERERS.stats).toBe(RENDERERS.stat);
  });
});
