import React, { useRef, useState, useCallback, useEffect } from 'react';
import { useAppStore } from '@/store';
import { Loader2, GripVertical, ChevronDown, ChevronUp, CheckCircle2, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';

/** Extract domain from URL for display */
const getDomain = (url: string) => {
    try { return new URL(url).hostname.replace('www.', ''); } catch { return url; }
};

const ResearchProgress: React.FC = () => {
    const { researchProgress, currentRun } = useAppStore();
    const containerRef = useRef<HTMLDivElement>(null);
    const logRef = useRef<HTMLDivElement>(null);
    const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [expanded, setExpanded] = useState(true);
    const dragOffset = useRef({ x: 0, y: 0 });

    // Reset position and expand when switching runs
    useEffect(() => { setPos(null); setExpanded(true); }, [currentRun?.id]);

    // Set default position (bottom-left, above zoom controls)
    useEffect(() => {
        if (pos !== null || !containerRef.current) return;
        const parent = containerRef.current.closest('.react-flow') as HTMLElement | null;
        if (!parent) return;
        setPos({ x: 16, y: parent.clientHeight - 100 });
    }, [pos, researchProgress.isDeepResearch]);

    // Auto-scroll log to bottom when new entries appear
    useEffect(() => {
        if (expanded && logRef.current) {
            logRef.current.scrollTop = logRef.current.scrollHeight;
        }
    }, [expanded, researchProgress.urlExtractionProgress]);

    // Document-level listeners for smooth dragging
    useEffect(() => {
        if (!isDragging) return;
        const onMove = (e: PointerEvent) => {
            e.preventDefault();
            const parent = containerRef.current?.closest('.react-flow') as HTMLElement | null;
            if (!parent) return;
            const rect = parent.getBoundingClientRect();
            setPos({
                x: Math.max(0, Math.min(e.clientX - rect.left - dragOffset.current.x, rect.width - 320)),
                y: Math.max(0, Math.min(e.clientY - rect.top - dragOffset.current.y, rect.height - 40)),
            });
        };
        const onUp = () => setIsDragging(false);
        document.addEventListener('pointermove', onMove);
        document.addEventListener('pointerup', onUp);
        return () => {
            document.removeEventListener('pointermove', onMove);
            document.removeEventListener('pointerup', onUp);
        };
    }, [isDragging]);

    const onPointerDown = useCallback((e: React.PointerEvent) => {
        if (!containerRef.current) return;
        e.stopPropagation();
        const rect = containerRef.current.getBoundingClientRect();
        dragOffset.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
        setIsDragging(true);
    }, []);

    // Aggregate URL extraction progress across all retriever agents (cumulative)
    const urlEntries = Object.entries(researchProgress.urlExtractionProgress);
    const entries = urlEntries.map(([, p]) => p);
    const totalUrls = entries.reduce((sum, p) => sum + p.total, 0);
    const fetchedUrls = entries.reduce((sum, p) => sum + p.current, 0);
    const allDone = entries.length > 0 && entries.every(p => p.done);
    const urlPercent = totalUrls > 0 ? Math.round((fetchedUrls / totalUrls) * 100) : 0;

    // Build flat log entries: in-progress agents + completed URLs
    const logEntries: { type: 'extracting' | 'url'; stepId: string; label: string; current?: number; total?: number; url?: string; title?: string; domain?: string }[] = [];
    for (const [stepId, progress] of urlEntries) {
        const label = researchProgress.stepLabels[stepId]?.description || stepId;
        if (progress.done && progress.urls.length > 0) {
            // Completed: show each URL as a log line
            for (const u of progress.urls) {
                logEntries.push({ type: 'url', stepId, label, url: u.url, title: u.title, domain: getDomain(u.url) });
            }
        } else if (progress.done) {
            // Done but no URLs parsed — show completion line
            logEntries.push({ type: 'url', stepId, label, url: '', title: `${label} — ${progress.total} sources extracted`, domain: '' });
        } else {
            // In-progress: show extracting line
            logEntries.push({ type: 'extracting', stepId, label, current: progress.current, total: progress.total });
        }
    }

    // Only show during deep research when URLs are being extracted
    if (!researchProgress.isDeepResearch || totalUrls === 0) return null;

    return (
        <div
            ref={containerRef}
            onPointerDown={onPointerDown}
            onMouseDown={e => e.stopPropagation()}
            style={{ left: pos?.x ?? 16, top: pos?.y ?? 16, touchAction: 'none' }}
            className={cn(
                "absolute z-50 nopan nowheel nodrag cursor-grab select-none",
                isDragging && "opacity-90 !cursor-grabbing"
            )}
        >
            <div className={cn("glass-panel backdrop-blur-xl rounded-lg border border-border/50 shadow-lg", expanded && "w-[320px]")}>
                {/* Header pill — always visible */}
                <div className="px-3 py-2 flex items-center gap-2">
                    <GripVertical className="w-3 h-3 shrink-0 text-muted-foreground/40" />
                    {!allDone && <Loader2 className="w-3.5 h-3.5 text-emerald-500 animate-spin shrink-0" />}
                    {allDone && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />}
                    <span className="text-xs font-mono font-semibold text-emerald-400">
                        {fetchedUrls}/{totalUrls}
                    </span>
                    <span className="text-[10px] text-muted-foreground">URLs</span>
                    <div className="w-20 h-1.5 bg-background/80 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-emerald-500 rounded-full transition-all duration-300 ease-out"
                            style={{ width: `${Math.min(urlPercent, 100)}%` }}
                        />
                    </div>
                    <button
                        onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
                        onPointerDown={(e) => e.stopPropagation()}
                        className="ml-1 p-0.5 rounded hover:bg-background/60 transition-colors cursor-pointer"
                    >
                        {expanded
                            ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
                            : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
                        }
                    </button>
                </div>

                {/* Live URL log */}
                {expanded && (
                    <div
                        ref={logRef}
                        className="border-t border-border/30 max-h-[60vh] overflow-y-auto font-mono text-[10px] leading-relaxed"
                        onPointerDown={e => e.stopPropagation()}
                        onWheel={e => e.stopPropagation()}
                    >
                        {logEntries.map((entry, i) => {
                            if (entry.type === 'extracting') {
                                return (
                                    <div key={`ext-${entry.stepId}`} className="flex items-center gap-1.5 px-2.5 py-1 border-b border-border/10 bg-emerald-500/5">
                                        <Loader2 className="w-2.5 h-2.5 text-emerald-500/70 animate-spin shrink-0" />
                                        <span className="text-emerald-400/80 truncate">
                                            Extracting {entry.current}/{entry.total} —{' '}
                                            <span className="text-muted-foreground/60 italic">
                                                {entry.label.length > 40 ? entry.label.slice(0, 40) + '...' : entry.label}
                                            </span>
                                        </span>
                                    </div>
                                );
                            }
                            // URL entry
                            if (!entry.url) {
                                // Fallback: done but no URLs
                                return (
                                    <div key={`done-${entry.stepId}`} className="flex items-center gap-1.5 px-2.5 py-1 border-b border-border/10">
                                        <CheckCircle2 className="w-2.5 h-2.5 text-emerald-500/50 shrink-0" />
                                        <span className="text-muted-foreground/50 truncate">{entry.title}</span>
                                    </div>
                                );
                            }
                            return (
                                <a
                                    key={`url-${i}`}
                                    href={entry.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center gap-1.5 px-2.5 py-1 border-b border-border/10 hover:bg-background/40 group/url cursor-pointer transition-colors"
                                >
                                    <CheckCircle2 className="w-2.5 h-2.5 text-emerald-500/50 shrink-0" />
                                    <span className="text-muted-foreground/70 truncate group-hover/url:text-emerald-400 transition-colors">
                                        {entry.title || entry.url}
                                    </span>
                                    <span className="text-muted-foreground/30 shrink-0 ml-auto text-[9px]">
                                        {entry.domain}
                                    </span>
                                    <ExternalLink className="w-2.5 h-2.5 text-muted-foreground/20 shrink-0 opacity-0 group-hover/url:opacity-100 transition-opacity" />
                                </a>
                            );
                        })}
                        {logEntries.length === 0 && (
                            <div className="px-2.5 py-3 text-muted-foreground/40 text-center">
                                Waiting for URL extraction...
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ResearchProgress;
