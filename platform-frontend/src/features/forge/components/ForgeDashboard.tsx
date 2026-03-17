import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
    Hammer, Plus, RefreshCw, CheckCircle, XCircle, ChevronRight, ChevronDown,
    History, FileText, Presentation, Table2, Loader2, AlertCircle,
    Send, AlertTriangle, Eye, Trash2, RotateCcw, Pencil, Palette, Maximize2,
    Code2, Check
} from 'lucide-react';
import { useAppStore } from '@/store';
import { api, API_BASE } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { ExportPanel } from './ExportPanel';
import { SlidePreviewModal } from './preview/SlidePreviewModal';
import { SlideRenderer } from './preview/SlideRenderer';
import { ArtifactPromptBanner } from './ArtifactPromptBanner';
import type { SlideTheme } from './preview/renderers';
import type { Slide } from './preview/normalizers';

/** Default theme used when no theme info is available */
const DEFAULT_THEME: SlideTheme = {
    id: 'corporate-blue',
    name: 'Corporate Blue',
    colors: {
        primary: '#1E3A5F',
        secondary: '#4A7FB5',
        accent: '#A87A22',
        background: '#F5F6F8',
        text: '#1C2D3F',
        text_light: '#7B8FA3',
        title_background: '#152C47',
    },
    font_heading: 'Calibri',
    font_body: 'Corbel',
};

/** Slide render dimensions (SlideFrame uses aspect-[16/9] so 960×540 is the canonical size) */
const SLIDE_W = 960;
const SLIDE_H = 540;

// --- Type helpers ---

const TYPE_META: Record<string, { icon: React.ElementType; color: string; label: string }> = {
    slides: { icon: Presentation, color: 'text-blue-400', label: 'Slides' },
    document: { icon: FileText, color: 'text-emerald-400', label: 'Document' },
    sheet: { icon: Table2, color: 'text-amber-400', label: 'Sheet' },
};

const STATUS_STYLE: Record<string, string> = {
    pending: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    approved: 'bg-green-500/10 text-green-400 border-green-500/20',
    rejected: 'bg-red-500/10 text-red-400 border-red-500/20',
};

// --- Collapsible JSON viewer ---

function JsonTree({ data, depth = 0 }: { data: unknown; depth?: number }) {
    const [collapsed, setCollapsed] = useState(depth > 1);

    if (data === null || data === undefined) {
        return <span className="text-muted-foreground italic">null</span>;
    }

    if (typeof data !== 'object') {
        if (typeof data === 'string') return <span className="text-emerald-400">"{data}"</span>;
        if (typeof data === 'number') return <span className="text-blue-400">{String(data)}</span>;
        if (typeof data === 'boolean') return <span className="text-amber-400">{String(data)}</span>;
        return <span>{String(data)}</span>;
    }

    const isArray = Array.isArray(data);
    const entries = isArray
        ? (data as unknown[]).map((v, i) => [String(i), v] as [string, unknown])
        : Object.entries(data as Record<string, unknown>);

    if (entries.length === 0) {
        return <span className="text-muted-foreground">{isArray ? '[]' : '{}'}</span>;
    }

    return (
        <div className="font-mono text-xs">
            <button
                onClick={() => setCollapsed(c => !c)}
                className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground"
            >
                {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                <span>{isArray ? `[${entries.length}]` : `{${entries.length}}`}</span>
            </button>
            {!collapsed && (
                <div className="ml-4 border-l border-border/30 pl-3 mt-1 space-y-0.5">
                    {entries.map(([key, val]) => (
                        <div key={key}>
                            <span className="text-purple-400">{isArray ? `[${key}]` : key}</span>
                            <span className="text-muted-foreground">: </span>
                            <JsonTree data={val} depth={depth + 1} />
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// --- Editable Outline tree viewer ---

interface OutlineEdit {
    title?: string;
    description?: string;
}

/** Flatten outline items to get a global index for slide mapping.
 *  Only LEAF items (no children) map to actual slides.
 *  Parent items with children are section headers — they don't get slides.
 */
function flattenOutlineIds(items: any[]): string[] {
    const flat: string[] = [];
    const walk = (list: any[]) => {
        for (const item of list) {
            if (item.children?.length) {
                // Parent/section header — skip, recurse into children
                walk(item.children);
            } else {
                // Leaf item — maps to an actual slide
                flat.push(item.id);
            }
        }
    };
    walk(items);
    return flat;
}

function EditableOutlineTree({
    items,
    edits,
    onEdit,
    editable,
    slides,
    theme,
    artifact,
    depth = 0,
    rootFlatItems,
}: {
    items: any[];
    edits: Record<string, OutlineEdit>;
    onEdit: (id: string, field: 'title' | 'description', value: string) => void;
    editable: boolean;
    slides?: Slide[];
    theme: SlideTheme;
    artifact: any;
    depth?: number;
    /** Global flat leaf-item IDs — computed once at root, passed to all children. */
    rootFlatItems?: string[];
}) {
    // Compute global flat list only at root level (depth 0), reuse for children
    const flatItems = useMemo(
        () => rootFlatItems ?? flattenOutlineIds(items || []),
        [rootFlatItems, items],
    );

    if (!items?.length) return <span className="text-muted-foreground text-xs italic">No outline items</span>;

    return (
        <div className="space-y-4">
            {items.map((item: any) => {
                const globalIdx = flatItems.indexOf(item.id);
                const slide = slides && globalIdx >= 0 ? slides[globalIdx] : undefined;
                const editData = edits[item.id];

                return (
                    <OutlineItemWithSlide
                        key={item.id}
                        item={item}
                        editData={editData}
                        onEdit={onEdit}
                        editable={editable}
                        slide={slide}
                        slideIndex={globalIdx}
                        totalSlides={slides?.length ?? 0}
                        theme={theme}
                        artifact={artifact}
                        depth={depth}
                    >
                        {item.children?.length > 0 && (
                            <div className="ml-4 mt-2">
                                <EditableOutlineTree
                                    items={item.children}
                                    edits={edits}
                                    onEdit={onEdit}
                                    editable={editable}
                                    slides={slides}
                                    theme={theme}
                                    artifact={artifact}
                                    depth={depth + 1}
                                    rootFlatItems={flatItems}
                                />
                            </div>
                        )}
                    </OutlineItemWithSlide>
                );
            })}
        </div>
    );
}

// --- Helper: extract text content from a slide element ---
function getElementText(el: any): string {
    if (typeof el.content === 'string') return el.content;
    if (Array.isArray(el.content)) {
        // Bullet lists, etc. — join items
        return el.content.map((item: any) => (typeof item === 'string' ? item : item?.text || JSON.stringify(item))).join('\n');
    }
    if (typeof el.content === 'object' && el.content !== null) {
        return JSON.stringify(el.content);
    }
    return '';
}

// --- Single outline item with inline slide preview + edit ---

function OutlineItemWithSlide({
    item,
    editData,
    onEdit,
    editable,
    slide,
    slideIndex,
    totalSlides,
    theme,
    artifact,
    depth,
    children,
}: {
    item: any;
    editData?: OutlineEdit;
    onEdit: (id: string, field: 'title' | 'description', value: string) => void;
    editable: boolean;
    slide?: Slide;
    slideIndex: number;
    totalSlides: number;
    theme: SlideTheme;
    artifact: any;
    depth: number;
    children?: React.ReactNode;
}) {
    const [aiEditOpen, setAiEditOpen] = useState(false);
    const [textEditOpen, setTextEditOpen] = useState(false);
    const [htmlEditOpen, setHtmlEditOpen] = useState(false);
    const [activeTab, setActiveTab] = useState<'html' | 'text' | 'ai'>('html');
    const [editInstruction, setEditInstruction] = useState('');
    const [editLoading, setEditLoading] = useState(false);
    const [directEdits, setDirectEdits] = useState<Record<string, string>>({});
    const [savingDirect, setSavingDirect] = useState(false);
    const [htmlDraft, setHtmlDraft] = useState('');
    const [htmlSaving, setHtmlSaving] = useState(false);
    const [htmlSaved, setHtmlSaved] = useState(false);
    const applyEditInstruction = useAppStore(s => s.applyEditInstruction);
    const patchSlideContent = useAppStore(s => s.patchSlideContent);
    const loadArtifact = useAppStore(s => s.loadArtifact);

    // Sync HTML draft when slide changes
    useEffect(() => {
        setHtmlDraft(slide?.html || '');
        setHtmlSaved(false);
    }, [slide?.id, slide?.html]);

    const handleHtmlSave = useCallback(async () => {
        if (!slide || htmlDraft === (slide.html || '')) return;
        setHtmlSaving(true);
        try {
            await patchSlideContent(artifact.id, { [slideIndex]: { html: htmlDraft } }, artifact.revision_head_id);
            setHtmlSaved(true);
            setTimeout(() => setHtmlSaved(false), 2000);
            await loadArtifact(artifact.id);
        } catch (e: any) {
            console.error('HTML save failed', e);
        } finally {
            setHtmlSaving(false);
        }
    }, [slide, slideIndex, htmlDraft, artifact, patchSlideContent, loadArtifact]);

    // Measure container for responsive slide scaling
    const slideContainerRef = useRef<HTMLDivElement>(null);
    const [containerWidth, setContainerWidth] = useState(0);
    useEffect(() => {
        const el = slideContainerRef.current;
        if (!el) return;
        const ro = new ResizeObserver(entries => {
            for (const entry of entries) setContainerWidth(entry.contentRect.width);
        });
        ro.observe(el);
        return () => ro.disconnect();
    }, []);
    // Reset direct edits when slide changes
    useEffect(() => {
        setDirectEdits({});
    }, [slide?.id]);

    const handleAiEdit = useCallback(async () => {
        if (!editInstruction.trim() || !slide) return;
        setEditLoading(true);
        const prefix = `On slide ${slideIndex + 1} (${slide.slide_type}, title: '${slide.title || 'untitled'}'): `;
        try {
            await applyEditInstruction(artifact.id, prefix + editInstruction.trim(), artifact.revision_head_id);
            const { editError: err, editConflict: conflict } = useAppStore.getState();
            if (!err && !conflict) {
                setEditInstruction('');
                setAiEditOpen(false);
                await loadArtifact(artifact.id);
            }
        } finally {
            setEditLoading(false);
        }
    }, [editInstruction, slide, slideIndex, artifact, applyEditInstruction, loadArtifact]);

    const handleDirectSave = useCallback(async () => {
        if (!slide || Object.keys(directEdits).length === 0) return;
        setSavingDirect(true);
        try {
            await patchSlideContent(artifact.id, { [slideIndex]: directEdits }, artifact.revision_head_id);
            const { editError: err, editConflict: conflict } = useAppStore.getState();
            if (!err && !conflict) {
                setDirectEdits({});
                setTextEditOpen(false);
                await loadArtifact(artifact.id);
            }
        } finally {
            setSavingDirect(false);
        }
    }, [slide, slideIndex, directEdits, artifact, patchSlideContent, loadArtifact]);

    const displayTitle = editData?.title ?? item.title;
    // Clean description: strip outline metadata (slide_type, headline_text, etc.)
    const rawDesc = editData?.description ?? item.description;
    const displayDesc = useMemo(() => {
        if (!rawDesc) return rawDesc;
        // If description contains metadata fields, extract just the meaningful parts
        if (/^slide_type:/m.test(rawDesc) || /\bheadline_text:/m.test(rawDesc)) {
            const parts: string[] = [];
            const supportingMatch = rawDesc.match(/supporting_text:\s*(.+?)(?:\n|$)/);
            if (supportingMatch) parts.push(supportingMatch[1].trim());
            const speakerMatch = rawDesc.match(/speaker_notes:\s*'([^']+)'/);
            if (speakerMatch) parts.push(speakerMatch[1].trim());
            if (parts.length > 0) return parts[0];
            // Fallback: strip known metadata prefixes and return what's left
            return rawDesc
                .replace(/slide_type:\s*\w+\s*/gi, '')
                .replace(/headline_text:\s*[^\n]+/gi, '')
                .replace(/visual_description:\s*[^\n]+/gi, '')
                .replace(/color_scheme:\s*[^\n]+/gi, '')
                .replace(/suggested_svg_elements:\s*[^\n]+/gi, '')
                .replace(/supporting_text:\s*/gi, '')
                .replace(/speaker_notes:\s*'[^']*'/gi, '')
                .trim() || rawDesc;
        }
        // Simple trailing slide_type strip
        return rawDesc.replace(/\.\s*slide_type:\s*\w+\s*$/i, '.').replace(/\s*slide_type:\s*\w+\s*$/i, '').trim() || rawDesc;
    }, [rawDesc]);

    // Text elements for direct editing (structured slides)
    const textElements = useMemo(() => {
        if (!slide?.elements) return [];
        return slide.elements
            .map((el, i) => ({ idx: i, type: el.type, content: getElementText(el) }))
            .filter(e => e.content.length > 0 && e.type !== 'image');
    }, [slide?.elements]);

    // Extract visible text parts from HTML for the Text tab (HTML slides)
    const htmlTextParts = useMemo(() => {
        const src = htmlDraft || slide?.html;
        if (!src) return [];
        const parts: { tag: string; text: string; index: number }[] = [];
        // Parse text content from common HTML text elements
        const tagRegex = /<(h[1-6]|p|span|li|td|th|a|strong|em|b|i|div|button|label)\b[^>]*>([\s\S]*?)<\/\1>/gi;
        let match;
        let idx = 0;
        while ((match = tagRegex.exec(src)) !== null) {
            // Strip inner tags to get plain text
            const inner = match[2].replace(/<[^>]+>/g, '').trim();
            if (inner.length > 0) {
                parts.push({ tag: match[1].toLowerCase(), text: inner, index: idx++ });
            }
        }
        return parts;
    }, [htmlDraft, slide?.html]);

    return (
        <div className="border-l-2 border-primary/30 pl-3 min-w-0">
            {/* Outline item header */}
            <div className="flex items-start gap-2">
                <span className="text-xs text-muted-foreground/60 font-mono mt-0.5 shrink-0">
                    {slideIndex >= 0 ? `${slideIndex + 1}.` : ''}
                </span>
                <div className="flex-1 min-w-0">
                    {editable ? (
                        <input
                            className="w-full text-sm font-medium text-foreground bg-transparent border-b border-dashed border-border/50 focus:border-primary/60 outline-none py-0.5 break-words"
                            value={displayTitle}
                            onChange={e => onEdit(item.id, 'title', e.target.value)}
                            placeholder="Slide title..."
                        />
                    ) : (
                        <p className="text-sm font-medium text-foreground break-words">{displayTitle}</p>
                    )}
                    {(editable || displayDesc) && (
                        editable ? (
                            <textarea
                                className="w-full text-xs text-muted-foreground bg-transparent border-b border-dashed border-border/30 focus:border-primary/40 outline-none mt-0.5 resize-none break-words"
                                value={displayDesc || ''}
                                onChange={e => onEdit(item.id, 'description', e.target.value)}
                                placeholder="Description..."
                                rows={1}
                            />
                        ) : (
                            displayDesc && <p className="text-xs text-muted-foreground mt-0.5 break-words line-clamp-4">{displayDesc}</p>
                        )
                    )}
                </div>
            </div>

            {/* Inline slide preview — split layout: slide left, editor right */}
            {(() => {
                const editorOpen = (htmlEditOpen || textEditOpen || aiEditOpen) && !!slide;
                const previewW = editorOpen && containerWidth > 0 ? Math.floor(containerWidth * 0.5) : containerWidth;
                const previewScale = containerWidth > 0 ? previewW / SLIDE_W : 1;
                const previewH = Math.round(SLIDE_H * previewScale);
                return (
                    <div ref={slideContainerRef} className={cn("mt-2 mb-1 w-full", editorOpen && "flex gap-2")}>
                        {/* Left: slide preview */}
                        {slide && containerWidth > 0 && (() => {
                            return (
                                <div
                                    className={editorOpen ? "w-1/2 shrink-0" : "w-full"}
                                >
                                    <div
                                        style={{
                                            width: '100%',
                                            height: previewH,
                                            overflow: 'hidden',
                                            position: 'relative',
                                            borderRadius: 8,
                                            border: '1px solid rgba(128,128,128,0.15)',
                                            boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
                                        }}
                                    >
                                        <div
                                            style={{
                                                width: SLIDE_W,
                                                height: SLIDE_H,
                                                transform: `scale(${previewScale})`,
                                                transformOrigin: 'top left',
                                                pointerEvents: 'none',
                                            }}
                                        >
                                            <SlideRenderer
                                                slide={slide}
                                                theme={theme}
                                                slideIndex={slideIndex}
                                                totalSlides={totalSlides}
                                                imageBaseUrl={`${API_BASE}/studio/${artifact.id}/images`}
                                            />
                                        </div>
                                        {/* Code2 button — bottom right of slide preview */}
                                        <button
                                            onClick={() => {
                                                const opening = !htmlEditOpen && !textEditOpen && !aiEditOpen;
                                                if (opening) {
                                                    const defaultTab = slide.html ? 'html' : 'text';
                                                    setHtmlEditOpen(true); setTextEditOpen(false); setAiEditOpen(false); setActiveTab(defaultTab);
                                                } else {
                                                    setHtmlEditOpen(false); setTextEditOpen(false); setAiEditOpen(false);
                                                }
                                            }}
                                            className={cn(
                                                "absolute bottom-2 right-2 flex items-center gap-1 px-2 py-1 rounded-md backdrop-blur-sm border font-mono text-[10px] font-semibold transition-all duration-150 shadow-lg",
                                                editorOpen
                                                    ? "bg-orange-500 border-orange-400 text-white"
                                                    : "bg-black/70 border-white/20 text-white/70 hover:text-orange-400 hover:border-orange-400/50 hover:bg-black/80"
                                            )}
                                            style={{ zIndex: 10, pointerEvents: 'auto' }}
                                            title={slide.html ? "Edit slide" : "Edit slide"}
                                        >
                                            {slide.html ? (
                                                <><Code2 className="w-3.5 h-3.5" /><span>&lt;/&gt;</span></>
                                            ) : (
                                                <><Pencil className="w-3 h-3" /><span>Edit</span></>
                                            )}
                                        </button>
                                    </div>
                                </div>
                            );
                        })()}

                        {/* Right: 3-tab editor panel — matches slide height */}
                        {editorOpen && slide && (
                            <div className="w-1/2 rounded-lg border border-border/30 bg-muted/10 overflow-hidden flex flex-col" style={{ height: previewH }}>
                                {/* Tab bar */}
                                <div className="flex border-b border-border/20 shrink-0">
                                    {slide.html && (
                                        <button
                                            onClick={() => setActiveTab('html')}
                                            className={cn(
                                                "flex items-center gap-1.5 px-3 py-2 text-[11px] font-medium transition-colors border-b-2 -mb-px",
                                                activeTab === 'html'
                                                    ? "border-orange-400 text-orange-400"
                                                    : "border-transparent text-muted-foreground hover:text-foreground"
                                            )}
                                        >
                                            <Code2 className="w-3 h-3" /> HTML
                                        </button>
                                    )}
                                    <button
                                        onClick={() => setActiveTab('text')}
                                        className={cn(
                                            "flex items-center gap-1.5 px-3 py-2 text-[11px] font-medium transition-colors border-b-2 -mb-px",
                                            activeTab === 'text'
                                                ? "border-emerald-400 text-emerald-400"
                                                : "border-transparent text-muted-foreground hover:text-foreground"
                                        )}
                                    >
                                        <FileText className="w-3 h-3" /> Text
                                    </button>
                                    <button
                                        onClick={() => setActiveTab('ai')}
                                        className={cn(
                                            "flex items-center gap-1.5 px-3 py-2 text-[11px] font-medium transition-colors border-b-2 -mb-px",
                                            activeTab === 'ai'
                                                ? "border-primary text-primary"
                                                : "border-transparent text-muted-foreground hover:text-foreground"
                                        )}
                                    >
                                        <Pencil className="w-3 h-3" /> AI Edit
                                    </button>
                                    {/* Save/Reset buttons inline with tabs */}
                                    {activeTab === 'html' && slide.html && (
                                        <div className="ml-auto flex items-center gap-2 px-2">
                                            {htmlDraft !== (slide.html || '') && (
                                                <button
                                                    onClick={() => { setHtmlDraft(slide.html || ''); setHtmlSaved(false); }}
                                                    className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
                                                >
                                                    Reset
                                                </button>
                                            )}
                                            <Button
                                                size="sm"
                                                onClick={handleHtmlSave}
                                                disabled={htmlSaving || htmlDraft === (slide.html || '')}
                                                className="h-6 text-[10px] px-2.5 bg-orange-600 hover:bg-orange-500 text-white disabled:opacity-40"
                                            >
                                                {htmlSaving ? (
                                                    <><Loader2 className="w-3 h-3 animate-spin mr-1" /> Saving...</>
                                                ) : htmlSaved ? (
                                                    <><Check className="w-3 h-3 mr-1" /> Saved</>
                                                ) : (
                                                    'Save'
                                                )}
                                            </Button>
                                        </div>
                                    )}
                                </div>

                                {/* Tab content — scrollable */}
                                <div className="flex-1 overflow-auto min-h-0">
                                    {/* HTML tab — syntax highlighted editor */}
                                    {activeTab === 'html' && slide.html && (() => {
                                        // Shared text styles — identical on pre and textarea to prevent layout drift
                                        const sharedStyle: React.CSSProperties = {
                                            margin: 0,
                                            border: 0,
                                            background: 'none',
                                            boxSizing: 'border-box',
                                            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                                            fontSize: '11px',
                                            fontWeight: 400,
                                            lineHeight: '1.6',
                                            letterSpacing: 'normal',
                                            whiteSpace: 'pre-wrap',
                                            overflowWrap: 'break-word',
                                            wordBreak: 'keep-all',
                                            padding: '12px',
                                            tabSize: 2,
                                        };
                                        const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                                        const highlighted = htmlDraft.replace(
                                            /<!--[\s\S]*?-->|<\/?[\w-]+(?:\s+[\w-]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*))?)*\s*\/?>|[^<]+/g,
                                            (match) => {
                                                if (match.startsWith('<!--')) {
                                                    return `<span style="color:#6a737d;font-style:italic">${esc(match)}</span>`;
                                                }
                                                if (match.startsWith('<')) {
                                                    return match.replace(
                                                        /(<\/?)([\w-]+)((?:\s+[\w-]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*))?)*\s*)(\/?>)/g,
                                                        (_m, open, tag, attrs, close) => {
                                                            const coloredAttrs = attrs.replace(
                                                                /([\w-]+)(\s*=\s*)("[^"]*"|'[^']*')/g,
                                                                (_a: string, name: string, eq: string, val: string) =>
                                                                    `<span style="color:#9cdcfe">${esc(name)}</span><span style="color:#cdd6f4">${esc(eq)}</span><span style="color:#ce9178">${esc(val)}</span>`
                                                            );
                                                            return `<span style="color:#808080">${esc(open)}</span><span style="color:#4ec9b0">${esc(tag)}</span>${coloredAttrs}<span style="color:#808080">${esc(close)}</span>`;
                                                        }
                                                    );
                                                }
                                                return `<span style="color:#f0f0f0">${esc(match)}</span>`;
                                            }
                                        );
                                        return (
                                            <div
                                                className="h-full overflow-auto"
                                                style={{ background: '#1e1e2e' }}
                                            >
                                                {/* Container: pre drives layout, textarea overlays */}
                                                <div style={{ position: 'relative', minHeight: '100%' }}>
                                                    {/* Highlighted layer — flows naturally, determines scroll height */}
                                                    <pre
                                                        style={{ ...sharedStyle, position: 'relative', pointerEvents: 'none', color: 'transparent' }}
                                                        aria-hidden="true"
                                                        dangerouslySetInnerHTML={{ __html: highlighted + '\n' }}
                                                    />
                                                    {/* Editable textarea — absolute overlay, no own scroll */}
                                                    <textarea
                                                        value={htmlDraft}
                                                        onChange={e => { setHtmlDraft(e.target.value); setHtmlSaved(false); }}
                                                        spellCheck={false}
                                                        className="focus:outline-none"
                                                        style={{
                                                            ...sharedStyle,
                                                            position: 'absolute',
                                                            top: 0,
                                                            left: 0,
                                                            width: '100%',
                                                            height: '100%',
                                                            resize: 'none',
                                                            overflow: 'hidden',
                                                            color: 'transparent',
                                                            caretColor: '#f0f0f0',
                                                            WebkitTextFillColor: 'transparent',
                                                        }}
                                                    />
                                                </div>
                                            </div>
                                        );
                                    })()}

                                    {/* Text tab */}
                                    {activeTab === 'text' && (
                                        <div className="p-3 space-y-2 overflow-auto">
                                            {slide.html ? (
                                                /* HTML slide: extract text parts and allow inline editing */
                                                <>
                                                    {htmlTextParts.length === 0 && (
                                                        <p className="text-xs text-muted-foreground italic">No editable text found in this slide.</p>
                                                    )}
                                                    {htmlTextParts.map((part) => (
                                                        <div key={part.index}>
                                                            <label className="text-[10px] text-muted-foreground uppercase tracking-wider">
                                                                &lt;{part.tag}&gt;
                                                            </label>
                                                            <input
                                                                className="w-full text-xs text-foreground bg-transparent border-b border-border/50 focus:border-primary/60 outline-none py-1"
                                                                defaultValue={part.text}
                                                                onBlur={e => {
                                                                    const newText = e.target.value;
                                                                    if (newText !== part.text) {
                                                                        // Replace the text in the HTML draft
                                                                        setHtmlDraft(prev => prev.replace(part.text, newText));
                                                                        setHtmlSaved(false);
                                                                    }
                                                                }}
                                                            />
                                                        </div>
                                                    ))}
                                                    {htmlTextParts.length > 0 && htmlDraft !== (slide.html || '') && (
                                                        <p className="text-[10px] text-orange-400/70 italic">Text changes applied to HTML. Use Save on HTML tab to persist.</p>
                                                    )}
                                                </>
                                            ) : (
                                                /* Structured slide: edit elements directly */
                                                <>
                                                    <div>
                                                        <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Title</label>
                                                        <input
                                                            className="w-full text-xs text-foreground bg-transparent border-b border-border/50 focus:border-primary/60 outline-none py-1"
                                                            value={directEdits.title ?? slide.title ?? ''}
                                                            onChange={e => setDirectEdits(prev => ({ ...prev, title: e.target.value }))}
                                                        />
                                                    </div>
                                                    {textElements.map(el => {
                                                        const key = `element_${el.idx}_content`;
                                                        return (
                                                            <div key={key}>
                                                                <label className="text-[10px] text-muted-foreground uppercase tracking-wider">
                                                                    {el.type}
                                                                </label>
                                                                <textarea
                                                                    className="w-full text-xs text-foreground bg-transparent border border-border/30 rounded p-1.5 focus:border-primary/60 outline-none resize-none"
                                                                    value={directEdits[key] ?? el.content}
                                                                    onChange={e => setDirectEdits(prev => ({ ...prev, [key]: e.target.value }))}
                                                                    rows={Math.min(4, el.content.split('\n').length + 1)}
                                                                />
                                                            </div>
                                                        );
                                                    })}
                                                    <Button
                                                        size="sm"
                                                        className="h-7 px-3 text-xs w-full"
                                                        onClick={handleDirectSave}
                                                        disabled={savingDirect || Object.keys(directEdits).length === 0}
                                                    >
                                                        {savingDirect ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <CheckCircle className="w-3 h-3 mr-1" />}
                                                        Save Text Changes
                                                    </Button>
                                                </>
                                            )}
                                        </div>
                                    )}

                                    {/* AI tab */}
                                    {activeTab === 'ai' && (
                                        <div className="p-3">
                                            <div className="flex gap-2 items-start">
                                                <Input
                                                    value={editInstruction}
                                                    onChange={e => setEditInstruction(e.target.value)}
                                                    placeholder="e.g. Make it more visual, add a chart..."
                                                    className="text-xs h-8 flex-1"
                                                    onKeyDown={e => e.key === 'Enter' && handleAiEdit()}
                                                />
                                                <Button
                                                    size="sm"
                                                    className="h-8 px-3 text-xs"
                                                    onClick={handleAiEdit}
                                                    disabled={editLoading || !editInstruction.trim()}
                                                >
                                                    {editLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                                                </Button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                );
            })()}

            {children}
        </div>
    );
}

// --- Create Artifact Dialog ---

function CreateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
    const createArtifact = useAppStore(s => s.createArtifact);
    const isGenerating = useAppStore(s => s.isGenerating);

    const [type, setType] = useState<'slides' | 'documents' | 'sheets'>('slides');
    const [slideMode, setSlideMode] = useState<'artistic' | 'business'>('artistic');
    const [title, setTitle] = useState('');
    const [prompt, setPrompt] = useState('');

    const handleCreate = async () => {
        if (!prompt.trim()) return;
        await createArtifact(type, prompt, title || undefined, type === 'slides' ? slideMode : undefined);
        setTitle('');
        setPrompt('');
        onOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="bg-card border-border sm:max-w-lg text-foreground">
                <DialogHeader>
                    <DialogTitle>Create Artifact</DialogTitle>
                </DialogHeader>

                <div className="space-y-5 py-2">
                    {/* Type selector */}
                    <div className="grid grid-cols-3 gap-2">
                        {(['slides', 'documents', 'sheets'] as const).map(t => {
                            const meta = TYPE_META[t === 'documents' ? 'document' : t === 'sheets' ? 'sheet' : t];
                            const Icon = meta.icon;
                            const selected = type === t;
                            return (
                                <button
                                    key={t}
                                    onClick={() => setType(t)}
                                    className={cn(
                                        "flex flex-col items-center gap-2 p-4 rounded-xl border transition-all duration-200",
                                        selected
                                            ? "border-primary bg-primary/10 text-primary shadow-md"
                                            : "border-border hover:border-primary/50 text-muted-foreground hover:text-foreground"
                                    )}
                                >
                                    <Icon className="w-6 h-6" />
                                    <span className="text-sm font-medium">{meta.label}</span>
                                </button>
                            );
                        })}
                    </div>

                    {/* Slide mode selector — only for slides */}
                    {type === 'slides' && (
                        <div className="space-y-2">
                            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Slide style</label>
                            <div className="grid grid-cols-2 gap-2">
                                <button
                                    onClick={() => setSlideMode('artistic')}
                                    className={cn(
                                        "flex items-center gap-3 p-3 rounded-lg border transition-all duration-200 text-left",
                                        slideMode === 'artistic'
                                            ? "border-primary bg-primary/10 text-primary"
                                            : "border-border hover:border-primary/50 text-muted-foreground hover:text-foreground"
                                    )}
                                >
                                    <Palette className="w-4 h-4 shrink-0" />
                                    <div>
                                        <div className="text-sm font-medium">Artistic</div>
                                        <div className="text-[10px] opacity-70">Rich HTML, creative layouts</div>
                                    </div>
                                </button>
                                <button
                                    onClick={() => setSlideMode('business')}
                                    className={cn(
                                        "flex items-center gap-3 p-3 rounded-lg border transition-all duration-200 text-left",
                                        slideMode === 'business'
                                            ? "border-primary bg-primary/10 text-primary"
                                            : "border-border hover:border-primary/50 text-muted-foreground hover:text-foreground"
                                    )}
                                >
                                    <Presentation className="w-4 h-4 shrink-0" />
                                    <div>
                                        <div className="text-sm font-medium">Business</div>
                                        <div className="text-[10px] opacity-70">Clean templates, PPTX-optimized</div>
                                    </div>
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Quick-start templates */}
                    <div className="space-y-2">
                        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Quick start</label>
                        <div className="flex flex-wrap gap-1.5">
                            {[
                                { label: 'Project Update', text: 'Create a project status update presentation with progress, milestones, and next steps' },
                                { label: 'Sales Pitch', text: 'Create a sales pitch deck with problem, solution, market opportunity, and call to action' },
                                { label: 'Team Intro', text: 'Create a team introduction presentation with member bios, roles, and org structure' },
                                { label: 'Technical Review', text: 'Create a technical architecture review with system diagrams, trade-offs, and recommendations' },
                            ].map(tpl => (
                                <button
                                    key={tpl.label}
                                    onClick={() => { setPrompt(tpl.text); setType('slides'); }}
                                    disabled={isGenerating}
                                    className="px-3 py-1.5 text-xs rounded-full border border-border/60 text-muted-foreground hover:text-foreground hover:border-primary/50 hover:bg-primary/5 transition-all duration-200"
                                >
                                    {tpl.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Title */}
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium text-muted-foreground">Title (optional)</label>
                        <Input
                            value={title}
                            onChange={e => setTitle(e.target.value)}
                            placeholder="e.g., Q4 Sales Report"
                            disabled={isGenerating}
                            className="bg-white/[0.06] border-white/[0.15]"
                        />
                    </div>

                    {/* Prompt */}
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium text-muted-foreground">
                            Describe your content <span className="text-destructive">*</span>
                        </label>
                        <Textarea
                            value={prompt}
                            onChange={e => setPrompt(e.target.value)}
                            placeholder="Describe the content you want to generate..."
                            rows={5}
                            className="text-sm bg-white/[0.06] border-white/[0.15]"
                            disabled={isGenerating}
                        />
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isGenerating}>
                        Cancel
                    </Button>
                    <Button onClick={handleCreate} disabled={isGenerating || !prompt.trim()}>
                        {isGenerating ? (
                            <>
                                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                Generating...
                            </>
                        ) : (
                            'Generate Outline'
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

// --- Detail Panel ---

function ArtifactDetail({ artifact }: { artifact: any }) {
    const approveOutline = useAppStore(s => s.approveOutline);
    const rejectOutline = useAppStore(s => s.rejectOutline);
    const isApproving = useAppStore(s => s.isApproving);
    const approveError = useAppStore(s => s.approveError);
    const applyEditInstruction = useAppStore(s => s.applyEditInstruction);
    const editLoading = useAppStore(s => s.editLoading);
    const editError = useAppStore(s => s.editError);
    const editConflict = useAppStore(s => s.editConflict);
    const clearEditState = useAppStore(s => s.clearEditState);
    const loadArtifact = useAppStore(s => s.loadArtifact);
    const [revisions, setRevisions] = useState<any[]>([]);
    const [revisionsLoading, setRevisionsLoading] = useState(false);
    const [showContentTree, setShowContentTree] = useState(false);
    const [editInstruction, setEditInstruction] = useState('');
    const [expandedRevisionId, setExpandedRevisionId] = useState<string | null>(null);
    const [expandedRevisionData, setExpandedRevisionData] = useState<any>(null);
    const [previewOpen, setPreviewOpen] = useState(false);
    const [restoreLoading, setRestoreLoading] = useState(false);
    const [restoreError, setRestoreError] = useState<string | null>(null);

    const handleRestore = async (revisionId: string, changeSummary: string) => {
        if (!window.confirm(`Restore to '${changeSummary}'? This will create a new revision.`)) return;
        setRestoreLoading(true);
        setRestoreError(null);
        try {
            await api.restoreRevision(artifact.id, revisionId, artifact.revision_head_id);
            await loadArtifact(artifact.id);
            const data = await api.listRevisions(artifact.id);
            setRevisions(data);
            setExpandedRevisionId(null);
            setExpandedRevisionData(null);
        } catch (err: any) {
            if (err?.response?.status === 409) {
                setRestoreError('Conflict: the artifact was modified. Please reload and try again.');
            } else {
                setRestoreError(err?.response?.data?.detail || 'Restore failed');
            }
        } finally {
            setRestoreLoading(false);
        }
    };

    const [outlineEdits, setOutlineEdits] = useState<Record<string, OutlineEdit>>({});
    const [themeInstruction, setThemeInstruction] = useState('');
    const [themeLoading, setThemeLoading] = useState(false);

    const meta = TYPE_META[artifact.type] || TYPE_META.document;
    const Icon = meta.icon;
    const outlineStatus = artifact.outline?.status;

    // Resolve theme
    const studioThemes = useAppStore(s => s.studioThemes);
    const resolvedTheme: SlideTheme = useMemo(() => {
        if (artifact.theme_id && studioThemes?.length) {
            const found = studioThemes.find((t: any) => t.id === artifact.theme_id);
            if (found) return found;
        }
        // Fall back to LLM-generated custom theme stored on artifact
        if (artifact.custom_theme && typeof artifact.custom_theme === 'object' && artifact.custom_theme.colors) {
            return artifact.custom_theme as SlideTheme;
        }
        return DEFAULT_THEME;
    }, [artifact.theme_id, artifact.custom_theme, studioThemes]);

    const slides: Slide[] = useMemo(() => {
        return artifact.content_tree?.slides ?? [];
    }, [artifact.content_tree?.slides]);

    const handleOutlineEdit = useCallback((id: string, field: 'title' | 'description', value: string) => {
        setOutlineEdits(prev => ({
            ...prev,
            [id]: { ...prev[id], [field]: value },
        }));
    }, []);

    const handleApproveWithEdits = useCallback(async () => {
        const modifications = Object.keys(outlineEdits).length > 0 ? { items: outlineEdits } : undefined;
        await approveOutline(artifact.id, modifications);
    }, [approveOutline, artifact.id, outlineEdits]);

    const handleApplyTheme = useCallback(async () => {
        if (!themeInstruction.trim()) return;
        setThemeLoading(true);
        try {
            await applyEditInstruction(
                artifact.id,
                `Global theme change: ${themeInstruction.trim()}. Do not change slide content, only adjust colors, fonts, and styling.`,
                artifact.revision_head_id
            );
            const { editError: err, editConflict: conflict } = useAppStore.getState();
            if (!err && !conflict) {
                setThemeInstruction('');
                await loadArtifact(artifact.id);
            }
        } finally {
            setThemeLoading(false);
        }
    }, [themeInstruction, artifact, applyEditInstruction, loadArtifact]);

    useEffect(() => {
        let cancelled = false;
        const loadRevisions = async () => {
            setRevisionsLoading(true);
            try {
                const data = await api.listRevisions(artifact.id);
                if (!cancelled) setRevisions(data);
            } catch {
                if (!cancelled) setRevisions([]);
            } finally {
                if (!cancelled) setRevisionsLoading(false);
            }
        };
        loadRevisions();
        return () => { cancelled = true; };
    }, [artifact.id, artifact.updated_at]);

    return (
        <ScrollArea className="h-full">
            <div className="p-6 space-y-8">
                {/* Header */}
                <div className="flex items-start gap-3">
                    <div className={cn("p-3 rounded-xl bg-muted/50 border border-border/50", meta.color)}>
                        <Icon className="w-6 h-6" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <h2 className="text-xl font-bold text-foreground truncate tracking-tight">
                            {artifact.title || 'Untitled'}
                        </h2>
                        <div className="flex items-center gap-2 mt-1">
                            <span className="text-sm text-muted-foreground capitalize">{artifact.type}</span>
                            {outlineStatus && (
                                <Badge variant="outline" className={cn("text-[10px] uppercase font-bold", STATUS_STYLE[outlineStatus])}>
                                    {outlineStatus}
                                </Badge>
                            )}
                        </div>
                        {artifact.updated_at && (
                            <span className="text-[10px] text-muted-foreground/60 mt-1 block">
                                Updated {formatDistanceToNow(new Date(artifact.updated_at), { addSuffix: true })}
                            </span>
                        )}
                    </div>
                    {/* Slideshow button in header */}
                    {artifact.type === 'slides' && artifact.content_tree && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setPreviewOpen(true)}
                            className="shrink-0 gap-1.5 h-8 text-xs"
                        >
                            <Maximize2 className="w-3.5 h-3.5" />
                            Slideshow
                        </Button>
                    )}
                </div>

                <ArtifactPromptBanner key={artifact.id} prompt={artifact.creation_prompt} />

                {/* Global Theme Bar (only when content exists) */}
                {artifact.content_tree && artifact.type === 'slides' && (
                    <div className="rounded-lg border border-border/50 bg-muted/20 p-3">
                        <div className="flex items-center gap-2 mb-2">
                            <Palette className="w-4 h-4 text-primary" />
                            <span className="text-xs font-semibold text-foreground uppercase tracking-wider">Theme</span>
                        </div>
                        <div className="flex gap-2">
                            <Input
                                value={themeInstruction}
                                onChange={e => setThemeInstruction(e.target.value)}
                                placeholder="Dark mode, tech style, investor deck, change fonts..."
                                className="text-xs h-8 flex-1"
                                onKeyDown={e => e.key === 'Enter' && handleApplyTheme()}
                            />
                            <Button
                                size="sm"
                                className="h-8 px-3 text-xs gap-1.5"
                                onClick={handleApplyTheme}
                                disabled={themeLoading || !themeInstruction.trim()}
                            >
                                {themeLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Palette className="w-3 h-3" />}
                                Apply
                            </Button>
                        </div>
                    </div>
                )}

                {/* Outline Section */}
                {artifact.outline && (
                    <div className="space-y-3">
                        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
                            Outline {outlineStatus === 'pending' && <span className="text-xs text-primary/60 font-normal ml-1">(editable)</span>}
                        </h3>
                        <div className="rounded-lg border border-border/50 bg-muted/20 p-4">
                            <EditableOutlineTree
                                items={artifact.outline.items || []}
                                edits={outlineEdits}
                                onEdit={handleOutlineEdit}
                                editable={outlineStatus === 'pending'}
                                slides={slides.length > 0 ? slides : undefined}
                                theme={resolvedTheme}
                                artifact={artifact}
                            />
                        </div>

                        {/* Approve / Reject */}
                        {outlineStatus === 'pending' && (
                            <div className="flex gap-2">
                                <Button
                                    onClick={handleApproveWithEdits}
                                    disabled={isApproving}
                                    className="flex-1 bg-green-600 hover:bg-green-700 text-white"
                                >
                                    {isApproving ? (
                                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                    ) : (
                                        <CheckCircle className="w-4 h-4 mr-2" />
                                    )}
                                    {Object.keys(outlineEdits).length > 0 ? 'Approve with Changes' : 'Approve & Generate'}
                                </Button>
                                <Button
                                    variant="outline"
                                    onClick={() => rejectOutline(artifact.id)}
                                    disabled={isApproving}
                                    className="flex-1 border-red-500/30 text-red-400 hover:bg-red-500/10"
                                >
                                    <XCircle className="w-4 h-4 mr-2" />
                                    Reject
                                </Button>
                            </div>
                        )}

                        {approveError && (
                            <div className="p-3 rounded-lg border border-destructive/50 bg-destructive/10 flex items-start gap-2">
                                <AlertCircle className="w-4 h-4 text-destructive shrink-0 mt-0.5" />
                                <p className="text-sm text-destructive">{approveError}</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Content Tree */}
                {artifact.content_tree && (
                    <div className="space-y-3">
                        <button
                            onClick={() => setShowContentTree(v => !v)}
                            className="flex items-center gap-2 text-sm font-semibold text-foreground uppercase tracking-wider hover:text-primary transition-colors"
                        >
                            {showContentTree ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                            Content Tree
                        </button>
                        {showContentTree && (
                            <div className="rounded-lg border border-border/50 bg-muted/20 p-4 overflow-x-auto">
                                <JsonTree data={artifact.content_tree} />
                            </div>
                        )}
                    </div>
                )}

                {/* Preview (slides only) */}
                {artifact.type === 'slides' && artifact.content_tree && (
                    <div>
                        <Button
                            onClick={() => setPreviewOpen(true)}
                            className="w-full gap-2 h-10 text-sm"
                        >
                            <Eye className="w-4 h-4" />
                            Preview Slides
                        </Button>
                        <SlidePreviewModal open={previewOpen} onClose={() => setPreviewOpen(false)} />
                    </div>
                )}

                {/* Export */}
                <ExportPanel artifact={artifact} />

                {/* Chat Edit Panel — only when content_tree exists */}
                {artifact.content_tree && (
                    <div className="space-y-3">
                        <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground uppercase tracking-wider">
                            <Send className="w-4 h-4" />
                            Edit
                        </h3>
                        <div className="space-y-2">
                            <Textarea
                                value={editInstruction}
                                onChange={(e) => { setEditInstruction(e.target.value); clearEditState(); }}
                                placeholder="Describe the change (e.g. 'Change slide 3 title to Q2 Results')"
                                className="min-h-[100px] text-sm"
                            />
                            <Button
                                size="sm"
                                onClick={async () => {
                                    if (!editInstruction.trim()) return;
                                    await applyEditInstruction(artifact.id, editInstruction.trim(), artifact.revision_head_id);
                                    const { editError: err, editConflict: conflict } = useAppStore.getState();
                                    if (!err && !conflict) setEditInstruction('');
                                    // Reload revisions after edit
                                    try {
                                        const data = await api.listRevisions(artifact.id);
                                        setRevisions(data);
                                    } catch { /* ignore */ }
                                }}
                                disabled={editLoading || !editInstruction.trim()}
                                className="w-full"
                            >
                                {editLoading ? (
                                    <><Loader2 className="w-3 h-3 animate-spin mr-1" /> Applying...</>
                                ) : (
                                    <><Send className="w-3 h-3 mr-1" /> Apply Edit</>
                                )}
                            </Button>
                            {editError && (
                                <div className="rounded-md bg-red-500/10 border border-red-500/20 p-2 text-xs text-red-400 flex items-start gap-2">
                                    <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
                                    <span>{editError}</span>
                                </div>
                            )}
                            {editConflict && (
                                <div className="rounded-md bg-amber-500/10 border border-amber-500/20 p-2 text-xs text-amber-400 flex items-center gap-2">
                                    <AlertTriangle className="w-3 h-3 shrink-0" />
                                    <span>Conflict: another edit was applied. </span>
                                    <button
                                        onClick={() => { loadArtifact(artifact.id); clearEditState(); }}
                                        className="underline hover:text-amber-300"
                                    >
                                        Reload Latest
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Revisions */}
                <div className="space-y-3">
                    <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground uppercase tracking-wider">
                        <History className="w-4 h-4" />
                        Revisions
                    </h3>
                    {revisionsLoading ? (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground py-4">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            Loading revisions...
                        </div>
                    ) : revisions.length === 0 ? (
                        <p className="text-xs text-muted-foreground italic py-2">No revisions yet</p>
                    ) : (
                        <div className="space-y-2">
                            {revisions.map((rev: any) => (
                                <div key={rev.id} className="rounded-lg border border-border/50 bg-muted/20">
                                    <button
                                        onClick={async () => {
                                            if (expandedRevisionId === rev.id) {
                                                setExpandedRevisionId(null);
                                                setExpandedRevisionData(null);
                                                return;
                                            }
                                            const clickedId = rev.id;
                                            setExpandedRevisionId(clickedId);
                                            setExpandedRevisionData(null);
                                            try {
                                                const data = await api.getRevision(artifact.id, clickedId);
                                                // Guard against stale responses from rapid clicks
                                                setExpandedRevisionId(prev => {
                                                    if (prev === clickedId) setExpandedRevisionData(data);
                                                    return prev;
                                                });
                                            } catch {
                                                setExpandedRevisionData(null);
                                            }
                                        }}
                                        className="w-full p-3 flex items-center gap-3 text-left hover:bg-muted/40 transition-colors rounded-lg"
                                    >
                                        <div className="w-2 h-2 rounded-full bg-primary/60 shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-medium text-foreground truncate">
                                                {rev.change_summary}
                                                {rev.id === artifact.revision_head_id && (
                                                    <span className="ml-1.5 text-[9px] text-green-400/70 font-normal">(current)</span>
                                                )}
                                            </p>
                                            {rev.created_at && (
                                                <span className="text-[10px] text-muted-foreground">
                                                    {formatDistanceToNow(new Date(rev.created_at), { addSuffix: true })}
                                                </span>
                                            )}
                                        </div>
                                        <Eye className="w-3 h-3 text-muted-foreground" />
                                    </button>
                                    {expandedRevisionId === rev.id && expandedRevisionData && (
                                        <div className="border-t border-border/50 p-3 space-y-2">
                                            {expandedRevisionData.edit_instruction && (
                                                <p className="text-xs text-muted-foreground italic">
                                                    &quot;{expandedRevisionData.edit_instruction}&quot;
                                                </p>
                                            )}
                                            {expandedRevisionData.diff?.highlights && expandedRevisionData.diff.highlights.length > 0 && (
                                                <div className="space-y-1">
                                                    {expandedRevisionData.diff.highlights.map((h: any, i: number) => (
                                                        <div key={i} className="text-[10px] text-muted-foreground flex items-center gap-1">
                                                            <span className="font-mono bg-muted/50 px-1 rounded">{h.kind}</span>
                                                            <span>{h.change}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                            {expandedRevisionData.diff?.paths && expandedRevisionData.diff.paths.length > 0 && (
                                                <div className="overflow-x-auto">
                                                    <table className="text-[10px] w-full">
                                                        <thead>
                                                            <tr className="text-muted-foreground">
                                                                <th className="text-left pr-2">Path</th>
                                                                <th className="text-left pr-2">Before</th>
                                                                <th className="text-left">After</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {expandedRevisionData.diff.paths.slice(0, 20).map((p: any, i: number) => (
                                                                <tr key={i} className="border-t border-border/30">
                                                                    <td className="font-mono pr-2 py-0.5">{p.path}</td>
                                                                    <td className="pr-2 py-0.5 text-red-400/70 truncate max-w-[100px]">{String(p.before ?? '')}</td>
                                                                    <td className="py-0.5 text-green-400/70 truncate max-w-[100px]">{String(p.after ?? '')}</td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            )}
                                            {rev.id !== artifact?.revision_head_id && (
                                                <button
                                                    onClick={() => handleRestore(rev.id, rev.change_summary)}
                                                    disabled={restoreLoading}
                                                    className="mt-2 flex items-center gap-1.5 text-xs text-primary/80 hover:text-primary disabled:opacity-50 transition-colors"
                                                >
                                                    <RotateCcw className="w-3 h-3" />
                                                    {restoreLoading ? 'Restoring...' : 'Restore to this version'}
                                                </button>
                                            )}
                                            {restoreError && (
                                                <div className="mt-2 rounded-md bg-red-500/10 border border-red-500/20 p-2 text-xs text-red-400 flex items-start gap-2">
                                                    <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
                                                    <span>{restoreError}</span>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </ScrollArea>
    );
}

// --- Main Dashboard ---

export function ForgeDashboard() {
    const artifacts = useAppStore(s => s.studioArtifacts);
    const activeArtifact = useAppStore(s => s.activeArtifact);
    const activeArtifactId = useAppStore(s => s.activeArtifactId);
    const setActiveArtifactId = useAppStore(s => s.setActiveArtifactId);
    const fetchArtifacts = useAppStore(s => s.fetchArtifacts);
    const deleteArtifact = useAppStore(s => s.deleteArtifact);
    const clearAllArtifacts = useAppStore(s => s.clearAllArtifacts);
    const isSidebarSubPanelOpen = useAppStore(s => s.isSidebarSubPanelOpen);
    const showArtifactList = isSidebarSubPanelOpen;

    const [createOpen, setCreateOpen] = useState(false);
    const [search, setSearch] = useState('');
    const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null);
    const [clearAllOpen, setClearAllOpen] = useState(false);

    useEffect(() => {
        fetchArtifacts();
    }, [fetchArtifacts]);

    const filtered = useMemo(() => {
        if (!search.trim()) return artifacts;
        const q = search.toLowerCase();
        return artifacts.filter((a: any) =>
            a.title?.toLowerCase().includes(q) || a.type?.toLowerCase().includes(q)
        );
    }, [artifacts, search]);

    return (
        <div className="flex h-full w-full overflow-hidden">
            {/* Left Pane — Artifact List (toggle via nav rail click) */}
            <div className={cn(
                "border-r border-border/50 flex flex-col shrink-0 transition-all duration-200 overflow-hidden",
                showArtifactList ? "w-80" : "w-0 border-r-0"
            )}>
                {/* Toolbar */}
                <div className="p-3 border-b border-border/50 flex items-center gap-2 shrink-0">
                    <div className="flex items-center gap-2 flex-1">
                        <Hammer className="w-4 h-4 text-primary" />
                        <span className="text-base font-bold text-foreground tracking-tight">Forge</span>
                    </div>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-foreground"
                        onClick={() => fetchArtifacts()}
                        title="Refresh"
                    >
                        <RefreshCw className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-foreground"
                        onClick={() => setCreateOpen(true)}
                        title="Create Artifact"
                    >
                        <Plus className="w-3.5 h-3.5" />
                    </Button>
                    {artifacts.length > 0 && (
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-muted-foreground hover:text-red-400"
                            onClick={() => setClearAllOpen(true)}
                            title="Clear All Artifacts"
                        >
                            <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                    )}
                </div>

                {/* Search */}
                <div className="px-3 py-2.5 border-b border-border/30">
                    <Input
                        className="h-8 text-sm"
                        placeholder="Search artifacts..."
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                    />
                </div>

                {/* List */}
                <ScrollArea className="flex-1">
                    <div className="p-2 space-y-1">
                        {filtered.length === 0 && (
                            <div className="text-center text-muted-foreground py-16 space-y-3">
                                <Hammer className="w-10 h-10 mx-auto opacity-25" />
                                <p className="text-sm">No artifacts yet</p>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setCreateOpen(true)}
                                >
                                    <Plus className="w-3.5 h-3.5 mr-1.5" />
                                    Create your first
                                </Button>
                            </div>
                        )}
                        {filtered.map((a: any) => {
                            const meta = TYPE_META[a.type] || TYPE_META.document;
                            const Icon = meta.icon;
                            const isActive = activeArtifactId === a.id;
                            const outlineStatus = a.outline?.status;
                            // Detect mode from slide_mode field (returned by list API)
                            const isBusinessMode = a.type === 'slides' && a.slide_mode === 'business';

                            return (
                                <div
                                    key={a.id}
                                    className={cn(
                                        "group w-full text-left px-3 py-2 rounded-lg transition-all duration-200 cursor-pointer",
                                        isActive
                                            ? "bg-primary/10 border border-primary/30"
                                            : "hover:bg-muted/50 border border-transparent"
                                    )}
                                    onClick={() => setActiveArtifactId(a.id)}
                                >
                                    <div className="flex items-center gap-2.5">
                                        <Icon className={cn("w-4 h-4 shrink-0", meta.color)} />
                                        <p className={cn(
                                            "text-sm font-medium truncate flex-1 min-w-0",
                                            isActive ? "text-primary" : "text-foreground"
                                        )}>
                                            {a.title || 'Untitled'}
                                        </p>
                                        <button
                                            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 text-muted-foreground hover:text-red-400 transition-all shrink-0"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setDeleteTarget({ id: a.id, title: a.title || 'Untitled' });
                                            }}
                                            title="Delete artifact"
                                        >
                                            <Trash2 className="w-3 h-3" />
                                        </button>
                                    </div>
                                    <div className="flex items-center gap-1.5 mt-1 ml-6.5 pl-0.5">
                                        <span className="text-[10px] text-muted-foreground capitalize">{a.type}</span>
                                        {a.type === 'slides' && (
                                            <span className={cn(
                                                "px-1.5 py-0 rounded-full text-[8px] font-semibold",
                                                isBusinessMode
                                                    ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                                                    : "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                                            )}>
                                                {isBusinessMode ? 'Business' : 'Artistic'}
                                            </span>
                                        )}
                                        <span className="flex-1" />
                                        {outlineStatus && (
                                            <span className={cn(
                                                "px-1.5 py-0 rounded-full text-[8px] uppercase font-bold tracking-tighter",
                                                STATUS_STYLE[outlineStatus]
                                            )}>
                                                {outlineStatus}
                                            </span>
                                        )}
                                    </div>
                                    {a.created_at && (
                                        <p className="text-[9px] text-muted-foreground/40 mt-0.5 ml-6.5 pl-0.5">
                                            {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                                        </p>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </ScrollArea>
            </div>

            {/* Right Pane — Detail */}
            <div className="flex-1 min-w-0 overflow-hidden">
                {activeArtifact ? (
                    <ArtifactDetail artifact={activeArtifact} />
                ) : (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground space-y-6 px-8">
                        <div className="p-8 bg-muted/20 rounded-2xl ring-1 ring-border/30">
                            <Hammer className="w-14 h-14 opacity-30" />
                        </div>
                        <div className="text-center space-y-2">
                            <h3 className="text-2xl font-bold text-foreground/90 tracking-tight">Forge Studio</h3>
                            <p className="text-sm text-muted-foreground max-w-[360px] leading-relaxed">
                                Transform your ideas into polished slides, documents, and spreadsheets with AI.
                            </p>
                        </div>
                        <Button
                            onClick={() => setCreateOpen(true)}
                            className="mt-2 h-10 px-6 text-sm gap-2"
                        >
                            <Plus className="w-4 h-4" />
                            Create Artifact
                        </Button>
                    </div>
                )}
            </div>

            {/* Create Dialog */}
            <CreateDialog open={createOpen} onOpenChange={setCreateOpen} />

            {/* Delete Single Artifact Confirmation */}
            <Dialog open={!!deleteTarget} onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}>
                <DialogContent className="bg-card border-border sm:max-w-md text-foreground">
                    <DialogHeader>
                        <DialogTitle>Delete Artifact</DialogTitle>
                    </DialogHeader>
                    <p className="text-sm text-muted-foreground">
                        Delete &ldquo;{deleteTarget?.title}&rdquo;? This will remove the artifact and all its exports.
                    </p>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
                        <Button
                            variant="destructive"
                            onClick={async () => {
                                if (deleteTarget) {
                                    await deleteArtifact(deleteTarget.id);
                                    setDeleteTarget(null);
                                }
                            }}
                        >
                            Delete
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Clear All Artifacts Confirmation */}
            <Dialog open={clearAllOpen} onOpenChange={setClearAllOpen}>
                <DialogContent className="bg-card border-border sm:max-w-md text-foreground">
                    <DialogHeader>
                        <DialogTitle>Clear All Artifacts</DialogTitle>
                    </DialogHeader>
                    <p className="text-sm text-muted-foreground">
                        Clear all artifacts? This will permanently delete all {artifacts.length} artifact{artifacts.length !== 1 ? 's' : ''} and their exports.
                    </p>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setClearAllOpen(false)}>Cancel</Button>
                        <Button
                            variant="destructive"
                            onClick={async () => {
                                await clearAllArtifacts();
                                setClearAllOpen(false);
                            }}
                        >
                            Clear All
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
