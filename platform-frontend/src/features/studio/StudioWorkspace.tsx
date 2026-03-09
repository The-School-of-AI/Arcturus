import React, { useRef, useState } from 'react';
import { Wand2, Loader2, CheckCircle, XCircle, Presentation, FileText, Table2, AlertCircle, Upload, Eye } from 'lucide-react';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ExportButton } from '@/features/forge/components/ExportPanel';
import { SlidePreviewModal } from '@/features/forge/components/preview/SlidePreviewModal';

// === Sub-viewers ===

function OutlineViewer({ artifact }: { artifact: any }) {
    const approveOutline = useAppStore(s => s.approveOutline);
    const rejectOutline = useAppStore(s => s.rejectOutline);
    const isApproving = useAppStore(s => s.isApproving);
    const approveError = useAppStore(s => s.approveError);
    const outline = artifact.outline;

    if (!outline) return null;

    return (
        <div className="flex flex-col h-full">
            <div className="p-4 border-b border-border/50 flex items-center justify-between shrink-0">
                <div>
                    <h2 className="text-lg font-semibold">{artifact.title}</h2>
                    <span className="text-xs text-muted-foreground capitalize">{artifact.type} outline</span>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => rejectOutline(artifact.id)}
                        className="px-3 py-1.5 rounded-lg border border-border text-sm hover:border-destructive hover:bg-destructive/10 hover:text-destructive transition-colors flex items-center gap-1.5"
                    >
                        <XCircle className="w-3.5 h-3.5" />
                        Reject
                    </button>
                    <button
                        onClick={() => approveOutline(artifact.id)}
                        disabled={isApproving}
                        className="px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center gap-1.5"
                    >
                        {isApproving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5" />}
                        {isApproving ? 'Generating...' : 'Approve & Generate'}
                    </button>
                </div>
            </div>

            {approveError && (
                <div className="mx-4 mt-2 p-3 rounded-lg border border-destructive/50 bg-destructive/10 flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-destructive shrink-0 mt-0.5" />
                    <p className="text-sm text-destructive">{approveError}</p>
                </div>
            )}

            <ScrollArea className="flex-1 p-4">
                <div className="space-y-2 max-w-3xl mx-auto">
                    {outline.items?.map((item: any, i: number) => (
                        <OutlineItemRow key={item.id || i} item={item} depth={0} index={i} />
                    ))}
                </div>
            </ScrollArea>
        </div>
    );
}

function OutlineItemRow({ item, depth, index }: { item: any; depth: number; index: number }) {
    return (
        <div style={{ paddingLeft: depth * 20 }}>
            <div className="p-3 rounded-lg border border-border/50 bg-muted/20 hover:bg-muted/40 transition-colors">
                <div className="flex items-start gap-2">
                    <span className="text-xs text-muted-foreground font-mono mt-0.5 shrink-0">{index + 1}.</span>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium">{item.title}</p>
                        {item.description && (
                            <p className="text-xs text-muted-foreground mt-1">{item.description}</p>
                        )}
                    </div>
                </div>
            </div>
            {item.children?.map((child: any, ci: number) => (
                <OutlineItemRow key={child.id || ci} item={child} depth={depth + 1} index={ci} />
            ))}
        </div>
    );
}

// === Chart Summary Helper ===

function ChartSummary({ content }: { content: any }) {
    if (!content || typeof content !== 'object') return null;
    const chartType = content.chart_type || content.type || 'chart';
    const title = content.title || '';
    const categories = content.categories?.length || content.data?.categories?.length || 0;
    const series = content.series?.length || content.data?.series?.length || 0;
    const points = content.points?.length || 0;
    const xAxis = content.x_label || '';
    const yAxis = content.y_label || '';

    const typeColors: Record<string, string> = {
        bar: 'text-blue-400', column: 'text-blue-400',
        line: 'text-emerald-400', area: 'text-emerald-400',
        pie: 'text-amber-400', doughnut: 'text-amber-400',
        scatter: 'text-purple-400',
    };
    const color = typeColors[chartType.toLowerCase()] || 'text-primary';

    return (
        <span>
            <span className={cn("font-semibold", color)}>{chartType}</span>
            {title && <> &mdash; {title}</>}
            {(categories > 0 || series > 0 || points > 0) && (
                <span className="text-muted-foreground ml-1">
                    ({[
                        categories > 0 && `${categories} categories`,
                        series > 0 && `${series} series`,
                        points > 0 && `${points} points`,
                    ].filter(Boolean).join(', ')})
                </span>
            )}
            {(xAxis || yAxis) && (
                <span className="text-muted-foreground/60 ml-1">
                    {[xAxis && `x: ${xAxis}`, yAxis && `y: ${yAxis}`].filter(Boolean).join(', ')}
                </span>
            )}
        </span>
    );
}

// === Content Tree Viewers ===

function SlidesViewer({ tree }: { tree: any }) {
    return (
        <div className="space-y-4 max-w-4xl mx-auto p-4">
            <div className="text-center mb-6">
                <h2 className="text-xl font-bold">{tree.deck_title}</h2>
                {tree.subtitle && <p className="text-sm text-muted-foreground mt-1">{tree.subtitle}</p>}
            </div>
            {tree.slides?.map((slide: any, i: number) => (
                <div key={slide.id || i} className="border border-border/50 rounded-xl p-4 bg-muted/10 hover:bg-muted/20 transition-colors">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                            Slide {i + 1}
                        </span>
                        <span className="text-[10px] text-muted-foreground capitalize">{slide.slide_type}</span>
                    </div>
                    {slide.title && <h3 className="text-sm font-semibold mb-2">{slide.title}</h3>}
                    <div className="space-y-1.5">
                        {slide.elements?.map((el: any, ei: number) => (
                            <div key={el.id || ei} className="text-xs text-foreground/80 pl-3 border-l-2 border-border/40">
                                <span className="text-muted-foreground font-mono text-[10px]">[{el.type}]</span>{' '}
                                {el.type === 'chart' && el.content && typeof el.content === 'object' && !Array.isArray(el.content)
                                    ? <ChartSummary content={el.content} />
                                    : typeof el.content === 'string' ? el.content : Array.isArray(el.content) ? el.content.join(', ') : JSON.stringify(el.content)}
                            </div>
                        ))}
                    </div>
                    {slide.speaker_notes && (
                        <div className="mt-3 pt-2 border-t border-border/30 text-[11px] text-muted-foreground italic">
                            {slide.speaker_notes}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}

function DocumentViewer({ tree }: { tree: any }) {
    return (
        <div className="max-w-3xl mx-auto p-4 space-y-4">
            <div className="mb-6">
                <h2 className="text-xl font-bold">{tree.doc_title}</h2>
                {tree.doc_type && <span className="text-xs text-muted-foreground capitalize">{tree.doc_type.replace(/_/g, ' ')}</span>}
                {tree.abstract && <p className="text-sm text-muted-foreground mt-2 italic">{tree.abstract}</p>}
            </div>
            {tree.sections?.map((section: any, i: number) => (
                <SectionNode key={section.id || i} section={section} />
            ))}
        </div>
    );
}

function SectionNode({ section }: { section: any }) {
    const Tag = `h${Math.min(section.level || 1, 4)}` as keyof React.JSX.IntrinsicElements;
    const sizes: Record<number, string> = { 1: 'text-lg font-bold', 2: 'text-base font-semibold', 3: 'text-sm font-semibold', 4: 'text-sm font-medium' };
    return (
        <div className="mb-3" style={{ paddingLeft: ((section.level || 1) - 1) * 16 }}>
            <Tag className={cn(sizes[section.level || 1] || 'text-sm', 'mb-1')}>{section.heading}</Tag>
            {section.content && <p className="text-sm text-foreground/80 whitespace-pre-wrap">{section.content}</p>}
            {section.subsections?.map((sub: any, si: number) => (
                <SectionNode key={sub.id || si} section={sub} />
            ))}
        </div>
    );
}

function SheetViewer({ tree }: { tree: any }) {
    return (
        <div className="space-y-6 p-4 max-w-5xl mx-auto">
            <h2 className="text-xl font-bold">{tree.workbook_title}</h2>
            {tree.assumptions && <p className="text-xs text-muted-foreground italic mb-2">{tree.assumptions}</p>}
            {tree.tabs?.map((tab: any, i: number) => (
                <div key={tab.id || i} className="border border-border/50 rounded-xl overflow-hidden">
                    <div className="px-3 py-2 bg-muted/30 border-b border-border/50 text-xs font-semibold flex items-center gap-2">
                        <Table2 className="w-3.5 h-3.5 text-amber-400" />
                        {tab.name}
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                            {tab.headers?.length > 0 && (
                                <thead>
                                    <tr className="border-b border-border/40 bg-muted/10">
                                        {tab.headers.map((h: string, hi: number) => (
                                            <th key={hi} className="px-3 py-2 text-left font-semibold text-muted-foreground">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                            )}
                            <tbody>
                                {tab.rows?.map((row: any[], ri: number) => (
                                    <tr key={ri} className="border-b border-border/20 hover:bg-muted/10">
                                        {row.map((cell, ci) => (
                                            <td key={ci} className="px-3 py-1.5 text-foreground/80">
                                                {cell != null ? String(cell) : ''}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            ))}
        </div>
    );
}

// === Upload Data Button (for sheet artifacts) ===

function UploadDataButton({ artifactId }: { artifactId: string }) {
    const analyzeSheetUpload = useAppStore(s => s.analyzeSheetUpload);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setIsUploading(true);
        setError(null);
        try {
            await analyzeSheetUpload(artifactId, file);
        } catch (err: any) {
            setError(err?.response?.data?.detail || err?.message || 'Upload failed');
        } finally {
            setIsUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    return (
        <>
            <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx,.json"
                className="hidden"
                onChange={handleUpload}
            />
            <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="px-2 py-0.5 rounded text-[9px] uppercase font-bold tracking-tighter bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20 transition-colors disabled:opacity-50 flex items-center gap-1"
            >
                {isUploading ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                    <Upload className="w-3 h-3" />
                )}
                Upload Data
            </button>
            {error && (
                <span className="text-[9px] text-red-400">{error}</span>
            )}
        </>
    );
}

// === Main Workspace ===

export function StudioWorkspace() {
    const artifact = useAppStore(s => s.activeArtifact);
    const isGenerating = useAppStore(s => s.isGenerating);
    const isApproving = useAppStore(s => s.isApproving);
    const setOpen = useAppStore(s => s.setIsStudioModalOpen);
    const [previewOpen, setPreviewOpen] = useState(false);

    // Empty state
    if (!artifact && !isGenerating) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4">
                <div className="p-6 bg-muted/50 rounded-full ring-1 ring-white/10">
                    <Wand2 className="w-12 h-12 text-primary" />
                </div>
                <div className="space-y-1">
                    <h2 className="text-xl font-bold text-foreground uppercase tracking-tighter">Forge Studio</h2>
                    <p className="text-xs text-muted-foreground">Create slides, documents, and spreadsheets with AI</p>
                </div>
                <button
                    onClick={() => setOpen(true)}
                    className="mt-4 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors"
                >
                    Create Artifact
                </button>
            </div>
        );
    }

    // Generating spinner
    if (isGenerating && !artifact) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-3">
                <Loader2 className="w-10 h-10 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">Generating outline...</p>
            </div>
        );
    }

    if (!artifact) return null;

    // Outline pending → show outline viewer
    const outlineStatus = artifact.outline?.status;
    if (outlineStatus === 'pending') {
        return <OutlineViewer artifact={artifact} />;
    }

    // Approving spinner
    if (isApproving) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-3">
                <Loader2 className="w-10 h-10 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">Generating full content...</p>
            </div>
        );
    }

    // Has content_tree → dispatch to typed viewer
    if (artifact.content_tree) {
        const typeIcon: Record<string, React.ElementType> = { slides: Presentation, document: FileText, sheet: Table2 };
        const Icon = typeIcon[artifact.type] || FileText;

        return (
            <div className="flex flex-col h-full">
                <div className="p-3 border-b border-border/50 flex items-center gap-2 shrink-0">
                    <Icon className="w-4 h-4 text-primary" />
                    <h2 className="text-sm font-semibold">{artifact.title}</h2>
                    <span className="text-[10px] text-muted-foreground capitalize ml-1">{artifact.type}</span>
                    <div className="flex items-center gap-2 ml-auto">
                        {outlineStatus === 'approved' && (
                            <span className="px-1.5 py-0.5 rounded text-[9px] uppercase font-bold tracking-tighter bg-green-500/10 text-green-400">
                                Generated
                            </span>
                        )}
                        {artifact.type === 'sheet' && (
                            <UploadDataButton artifactId={artifact.id} />
                        )}
                        {artifact.type === 'slides' && (
                            <>
                                <button
                                    onClick={() => setPreviewOpen(true)}
                                    className="px-2 py-0.5 rounded text-[9px] uppercase font-bold tracking-tighter bg-muted/30 text-foreground hover:bg-muted/50 transition-colors flex items-center gap-1"
                                >
                                    <Eye className="w-3 h-3" />
                                    Preview
                                </button>
                                <SlidePreviewModal open={previewOpen} onClose={() => setPreviewOpen(false)} />
                            </>
                        )}
                        {['slides', 'document', 'sheet'].includes(artifact.type) && (
                            <ExportButton artifactId={artifact.id} artifactType={artifact.type} />
                        )}
                    </div>
                </div>
                <ScrollArea className="flex-1">
                    {artifact.type === 'slides' && <SlidesViewer tree={artifact.content_tree} />}
                    {artifact.type === 'document' && <DocumentViewer tree={artifact.content_tree} />}
                    {artifact.type === 'sheet' && <SheetViewer tree={artifact.content_tree} />}
                </ScrollArea>
            </div>
        );
    }

    // Rejected or other state
    return (
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-3">
            <div className="p-4 bg-muted/50 rounded-full ring-1 ring-white/10">
                <Wand2 className="w-8 h-8 text-muted-foreground" />
            </div>
            <p className="text-sm text-muted-foreground">
                {outlineStatus === 'rejected' ? 'Outline was rejected. Create a new artifact to try again.' : 'Select an artifact from the sidebar.'}
            </p>
        </div>
    );
}
