import React, { useState, useEffect } from 'react';
import {
    Download, Loader2, CheckCircle, AlertCircle, Palette, FileDown, ChevronDown, FileText, File, Globe, Table2, FileSpreadsheet
} from 'lucide-react';
import { useAppStore } from '@/store';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Switch } from '@/components/ui/switch';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';

// --- Quality Score Badge ---

function QualityScoreBadge({ score }: { score: number }) {
    const color = score >= 90
        ? 'bg-green-500/10 text-green-400 border-green-500/20'
        : score >= 70
            ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
            : 'bg-orange-500/10 text-orange-400 border-orange-500/20';
    return (
        <Badge variant="outline" className={cn("text-[10px] font-bold gap-0.5", color)}>
            Q{score}
        </Badge>
    );
}

// --- Validation Summary ---

function ValidationSummary({ results }: { results: any }) {
    const [expanded, setExpanded] = useState(false);
    if (!results) return null;

    const layoutWarnings = Array.isArray(results.layout_warnings) ? results.layout_warnings : [];
    const genericWarnings = Array.isArray(results.warnings) ? results.warnings : [];
    const warnings = [...layoutWarnings];
    for (const warning of genericWarnings) {
        if (!warnings.includes(warning)) warnings.push(warning);
    }
    const notesValid = results.notes_quality_valid;
    const chartValid = results.chart_quality_valid;
    const hasIssues = warnings.length > 0 || notesValid === false || chartValid === false;

    if (!hasIssues) return null;

    return (
        <div className="mt-1.5">
            <button
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
            >
                <ChevronDown className={cn("w-3 h-3 transition-transform", expanded && "rotate-180")} />
                {warnings.length + (notesValid === false ? 1 : 0) + (chartValid === false ? 1 : 0)} issue{(warnings.length + (notesValid === false ? 1 : 0) + (chartValid === false ? 1 : 0)) !== 1 ? 's' : ''}
            </button>
            {expanded && (
                <div className="mt-1 pl-4 space-y-0.5 text-[10px] text-muted-foreground">
                    {notesValid === false && (
                        <p className="text-amber-400">Speaker notes quality check failed</p>
                    )}
                    {chartValid === false && (
                        <p className="text-amber-400">Chart quality check failed</p>
                    )}
                    {warnings.map((w: string, i: number) => (
                        <p key={i} className="text-amber-400/80">{w}</p>
                    ))}
                </div>
            )}
        </div>
    );
}

// --- Theme Picker Dialog ---

function ThemePickerDialog({
    open,
    onOpenChange,
    onSelect,
}: {
    open: boolean;
    onOpenChange: (v: boolean) => void;
    onSelect: (themeId: string, strictLayout?: boolean, generateImages?: boolean) => void;
}) {
    const themes = useAppStore(s => s.studioThemes);
    const fetchThemes = useAppStore(s => s.fetchThemes);
    const [selected, setSelected] = useState<string | null>(null);
    const [strictLayout, setStrictLayout] = useState(false);
    const [generateImages, setGenerateImages] = useState(true);
    const [expandedBase, setExpandedBase] = useState<string | null>(null);
    const [variants, setVariants] = useState<Record<string, any[]>>({});
    const [loadingVariants, setLoadingVariants] = useState<string | null>(null);

    useEffect(() => {
        if (open) fetchThemes();
    }, [open, fetchThemes]);

    const handleExpandVariants = async (baseId: string) => {
        if (expandedBase === baseId) {
            setExpandedBase(null);
            return;
        }
        setExpandedBase(baseId);
        if (variants[baseId]) return;
        setLoadingVariants(baseId);
        try {
            const data = await api.listThemes({ base_id: baseId, include_variants: true });
            const variantOnly = data.filter((t: any) => t.id !== baseId);
            setVariants(prev => ({ ...prev, [baseId]: variantOnly }));
        } catch (e) {
            console.error("Failed to fetch variants", e);
        } finally {
            setLoadingVariants(null);
        }
    };

    const handleConfirm = () => {
        if (selected) {
            onSelect(selected, strictLayout || undefined, generateImages || undefined);
            onOpenChange(false);
            setSelected(null);
            setStrictLayout(false);
            setGenerateImages(true);
            setExpandedBase(null);
        }
    };

    const handleOpenChange = (v: boolean) => {
        if (!v) {
            setSelected(null);
            setStrictLayout(false);
            setGenerateImages(true);
            setExpandedBase(null);
        }
        onOpenChange(v);
    };

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="bg-card border-border sm:max-w-xl text-foreground">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Palette className="w-4 h-4 text-primary" />
                        Choose a Theme
                    </DialogTitle>
                </DialogHeader>

                <ScrollArea className="max-h-[400px]">
                    <div className="grid grid-cols-2 gap-3 p-1">
                        {themes.map((theme: any) => (
                            <React.Fragment key={theme.id}>
                                <div
                                    role="button"
                                    tabIndex={0}
                                    onClick={() => setSelected(theme.id)}
                                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(theme.id); } }}
                                    className={cn(
                                        "cursor-pointer text-left p-3 rounded-lg border transition-all duration-150",
                                        selected === theme.id
                                            ? "border-primary bg-primary/10 ring-1 ring-primary/40"
                                            : "border-border/50 hover:border-primary/40 hover:bg-muted/30"
                                    )}
                                >
                                    {/* Color swatches */}
                                    <div className="flex items-center gap-1.5 mb-2">
                                        {[
                                            theme.colors?.primary,
                                            theme.colors?.secondary,
                                            theme.colors?.accent,
                                            theme.colors?.background,
                                            theme.colors?.text,
                                        ].map((color: string, i: number) => (
                                            <div
                                                key={i}
                                                className="w-5 h-5 rounded-full border border-border/40 shrink-0"
                                                style={{ backgroundColor: color }}
                                                title={['Primary', 'Secondary', 'Accent', 'Background', 'Text'][i]}
                                            />
                                        ))}
                                    </div>
                                    <p className="text-sm font-medium text-foreground">{theme.name}</p>
                                    <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                                        {theme.description}
                                    </p>
                                    <div className="flex items-center justify-between mt-1">
                                        <p className="text-[10px] text-muted-foreground/60">
                                            {theme.font_heading} / {theme.font_body}
                                        </p>
                                        {!theme.base_theme_id && (
                                            <button
                                                type="button"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleExpandVariants(theme.id);
                                                }}
                                                className="text-[11px] bg-amber-100 text-amber-700 border border-amber-300 dark:bg-amber-500/20 dark:text-amber-400 dark:border-amber-500/30 rounded-full px-2 py-0.5 hover:bg-amber-200 dark:hover:bg-amber-500/30 transition-colors flex items-center gap-0.5"
                                            >
                                                6 Variants
                                                <ChevronDown className={cn(
                                                    "w-3 h-3 transition-transform",
                                                    expandedBase === theme.id && "rotate-180"
                                                )} />
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {/* Variant strip */}
                                {expandedBase === theme.id && (
                                    <div className="col-span-2 flex gap-2 overflow-x-auto py-1 px-1">
                                        {loadingVariants === theme.id && (
                                            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground py-2 px-3">
                                                <Loader2 className="w-3 h-3 animate-spin" />
                                                Loading variants...
                                            </div>
                                        )}
                                        {variants[theme.id]?.map((v: any) => (
                                            <button
                                                key={v.id}
                                                onClick={() => setSelected(v.id)}
                                                className={cn(
                                                    "shrink-0 text-left p-2 rounded-lg border transition-all duration-150 w-44",
                                                    selected === v.id
                                                        ? "border-primary bg-primary/10 ring-1 ring-primary/40"
                                                        : "border-border/50 hover:border-primary/40 hover:bg-muted/30"
                                                )}
                                            >
                                                <div className="flex items-center gap-1 mb-1">
                                                    {[v.colors?.primary, v.colors?.secondary, v.colors?.accent].map((c: string, ci: number) => (
                                                        <div key={ci} className="w-3.5 h-3.5 rounded-full border border-border/40" style={{ backgroundColor: c }} />
                                                    ))}
                                                </div>
                                                <p className="text-[11px] font-medium text-foreground truncate">{v.name}</p>
                                                <p className="text-[9px] text-muted-foreground/60 truncate">{v.font_heading} / {v.font_body}</p>
                                            </button>
                                        ))}
                                        {!loadingVariants && variants[theme.id]?.length === 0 && (
                                            <p className="text-[10px] text-muted-foreground py-2 px-3">No variants found</p>
                                        )}
                                    </div>
                                )}
                            </React.Fragment>
                        ))}
                    </div>
                    {themes.length === 0 && (
                        <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                            Loading themes...
                        </div>
                    )}
                </ScrollArea>

                <DialogFooter className="flex items-center sm:justify-between">
                    <div className="flex flex-col gap-2">
                        <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                            <Switch
                                checked={strictLayout}
                                onCheckedChange={setStrictLayout}
                            />
                            Strict layout validation
                        </label>
                        <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                            <Switch
                                checked={generateImages}
                                onCheckedChange={setGenerateImages}
                            />
                            Generate images (AI)
                        </label>
                    </div>
                    <div className="flex gap-2">
                        <Button variant="outline" onClick={() => handleOpenChange(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleConfirm} disabled={!selected}>
                            <FileDown className="w-4 h-4 mr-2" />
                            Export with Theme
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

// --- Status badge helper ---

function StatusBadge({ status }: { status: string }) {
    const styles: Record<string, { class: string; icon: React.ElementType }> = {
        completed: { class: 'bg-green-500/10 text-green-400 border-green-500/20', icon: CheckCircle },
        pending: { class: 'bg-orange-500/10 text-orange-400 border-orange-500/20', icon: Loader2 },
        failed: { class: 'bg-red-500/10 text-red-400 border-red-500/20', icon: AlertCircle },
    };
    const s = styles[status] || styles.pending;
    const Icon = s.icon;
    return (
        <Badge variant="outline" className={cn("text-[10px] uppercase font-bold gap-1", s.class)}>
            <Icon className={cn("w-3 h-3", status === 'pending' && "animate-spin")} />
            {status}
        </Badge>
    );
}

// --- Document Format Picker Dialog ---

function DocFormatPickerDialog({
    open,
    onOpenChange,
    onSelect,
}: {
    open: boolean;
    onOpenChange: (v: boolean) => void;
    onSelect: (format: string, generateImages?: boolean) => void;
}) {
    const [selected, setSelected] = useState<string | null>(null);
    const [generateImages, setGenerateImages] = useState(false);

    const handleOpenChange = (v: boolean) => {
        if (!v) { setSelected(null); setGenerateImages(false); }
        onOpenChange(v);
    };

    const handleSelect = (format: string) => {
        if (format === 'html') {
            setSelected(format);
        } else {
            onSelect(format);
            handleOpenChange(false);
        }
    };

    const handleConfirmHtml = () => {
        onSelect('html', generateImages || undefined);
        handleOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="bg-card border-border sm:max-w-md text-foreground">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <FileDown className="w-4 h-4 text-primary" />
                        Choose Export Format
                    </DialogTitle>
                </DialogHeader>
                <div className="grid grid-cols-3 gap-3 p-1">
                    <button
                        onClick={() => handleSelect('docx')}
                        className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border/50 hover:border-primary/40 hover:bg-muted/30 transition-all"
                    >
                        <FileText className="w-8 h-8 text-blue-400" />
                        <span className="text-sm font-medium">DOCX</span>
                        <span className="text-[10px] text-muted-foreground">Word Document</span>
                    </button>
                    <button
                        onClick={() => handleSelect('pdf')}
                        className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border/50 hover:border-primary/40 hover:bg-muted/30 transition-all"
                    >
                        <File className="w-8 h-8 text-red-400" />
                        <span className="text-sm font-medium">PDF</span>
                        <span className="text-[10px] text-muted-foreground">PDF Document</span>
                    </button>
                    <button
                        onClick={() => handleSelect('html')}
                        className={cn(
                            "flex flex-col items-center gap-2 p-4 rounded-lg border transition-all",
                            selected === 'html'
                                ? "border-primary bg-primary/10 ring-1 ring-primary/40"
                                : "border-border/50 hover:border-primary/40 hover:bg-muted/30"
                        )}
                    >
                        <Globe className="w-8 h-8 text-emerald-400" />
                        <span className="text-sm font-medium">HTML</span>
                        <span className="text-[10px] text-muted-foreground">Web Page</span>
                    </button>
                </div>
                {selected === 'html' && (
                    <div className="flex items-center justify-between px-1 pt-2 border-t border-border/50">
                        <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                            <Switch
                                checked={generateImages}
                                onCheckedChange={setGenerateImages}
                            />
                            Generate hero image (AI)
                        </label>
                        <Button size="sm" onClick={handleConfirmHtml}>
                            <FileDown className="w-3.5 h-3.5 mr-1.5" />
                            Export HTML
                        </Button>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

// --- Sheet Format Picker Dialog ---

function SheetFormatPickerDialog({
    open,
    onOpenChange,
    onSelect,
}: {
    open: boolean;
    onOpenChange: (v: boolean) => void;
    onSelect: (format: string) => void;
}) {
    const handleSelect = (format: string) => {
        onSelect(format);
        onOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="bg-card border-border sm:max-w-sm text-foreground">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <FileDown className="w-4 h-4 text-primary" />
                        Choose Export Format
                    </DialogTitle>
                </DialogHeader>
                <div className="grid grid-cols-2 gap-3 p-1">
                    <button
                        onClick={() => handleSelect('xlsx')}
                        className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border/50 hover:border-primary/40 hover:bg-muted/30 transition-all"
                    >
                        <FileSpreadsheet className="w-8 h-8 text-green-400" />
                        <span className="text-sm font-medium">XLSX</span>
                        <span className="text-[10px] text-muted-foreground">Excel Workbook</span>
                    </button>
                    <button
                        onClick={() => handleSelect('csv')}
                        className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border/50 hover:border-primary/40 hover:bg-muted/30 transition-all"
                    >
                        <Table2 className="w-8 h-8 text-blue-400" />
                        <span className="text-sm font-medium">CSV</span>
                        <span className="text-[10px] text-muted-foreground">All Tabs (ZIP)</span>
                    </button>
                </div>
            </DialogContent>
        </Dialog>
    );
}

// --- Export Panel (for ForgeDashboard ArtifactDetail) ---

export function ExportPanel({ artifact }: { artifact: any }) {
    const exportJobs = useAppStore(s => s.exportJobs);
    const isExporting = useAppStore(s => s.isExporting);
    const startExport = useAppStore(s => s.startExport);
    const autoDownloadJobId = useAppStore(s => s.autoDownloadJobId);
    const clearAutoDownload = useAppStore(s => s.clearAutoDownload);
    const [themePickerOpen, setThemePickerOpen] = useState(false);
    const [docFormatPickerOpen, setDocFormatPickerOpen] = useState(false);
    const [sheetFormatPickerOpen, setSheetFormatPickerOpen] = useState(false);

    const isDocument = artifact.type === 'document';
    const isSlides = artifact.type === 'slides';
    const isSheet = artifact.type === 'sheet';

    const handleDownload = async (job: any) => {
        const url = api.getExportDownloadUrl(artifact.id, job.id);
        const jobFormat = job.format || (isDocument ? 'docx' : 'pptx');
        const fileExt = jobFormat === 'csv' ? 'zip' : jobFormat;
        const defaultName = `${artifact.title || artifact.type}.${fileExt}`;
        try {
            // Electron: native Save dialog + auto-open
            if ((window as any).electronAPI) {
                const result = await (window as any).electronAPI.invoke('dialog:saveAndOpen', { url, defaultName });
                if (!result?.success && !result?.canceled) {
                    console.error('Save failed:', result?.error);
                }
                return;
            }
            // Browser fallback: blob download
            const resp = await fetch(url);
            if (!resp.ok) {
                const detail = await resp.text().catch(() => '');
                throw new Error(detail || `Download failed with HTTP ${resp.status}`);
            }
            const blob = await resp.blob();
            const blobUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = defaultName;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(blobUrl);
        } catch (err) {
            console.error('Download failed:', err);
        }
    };

    // Auto-trigger save dialog when export completes.
    // Uses getState() to avoid double-fire when SlideBottomBar also handles this.
    useEffect(() => {
        if (!autoDownloadJobId) return;
        // Only auto-download if this panel is showing the artifact that started the export
        if (autoDownloadJobId.artifactId !== artifact.id) return;
        const job = exportJobs.find((j: any) => j.id === autoDownloadJobId.jobId && j.status === 'completed');
        if (job) {
            if (!useAppStore.getState().autoDownloadJobId) return;
            clearAutoDownload();
            handleDownload(job);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [autoDownloadJobId, exportJobs, artifact.id]);

    // Show for slides, documents, or sheets with content_tree
    if (!['slides', 'document', 'sheet'].includes(artifact.type) || !artifact.content_tree) return null;

    const handleThemeSelected = (themeId: string, strictLayout?: boolean, generateImages?: boolean) => {
        startExport(artifact.id, 'pptx', themeId, strictLayout, generateImages);
    };

    const handleDocFormatSelected = (format: string, generateImages?: boolean) => {
        startExport(artifact.id, format, undefined, undefined, generateImages);
    };

    const handleSheetFormatSelected = (format: string) => {
        startExport(artifact.id, format);
    };

    const formatSize = (bytes: number | null | undefined) => {
        if (!bytes) return '';
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground uppercase tracking-wider">
                    <FileDown className="w-4 h-4" />
                    Export
                </h3>
                <button
                    onClick={() => isSheet ? setSheetFormatPickerOpen(true) : isDocument ? setDocFormatPickerOpen(true) : setThemePickerOpen(true)}
                    disabled={isExporting}
                    className="h-7 px-3 rounded-full text-xs font-bold bg-amber-100 text-amber-700 border border-amber-300 hover:bg-amber-200 dark:bg-amber-500/20 dark:text-amber-400 dark:border-amber-500/30 dark:hover:bg-amber-500/30 transition-colors disabled:opacity-50 flex items-center gap-1.5"
                >
                    {isExporting ? (
                        <>
                            <Loader2 className="w-3 h-3 animate-spin" />
                            Exporting...
                        </>
                    ) : isSheet ? (
                        <>
                            <FileDown className="w-3 h-3" />
                            Export Sheet
                        </>
                    ) : isDocument ? (
                        <>
                            <FileDown className="w-3 h-3" />
                            Export Doc
                        </>
                    ) : (
                        <>
                            <Palette className="w-3 h-3" />
                            Export PPTX
                        </>
                    )}
                </button>
            </div>

            {/* Export jobs list */}
            {exportJobs.length > 0 && (
                <div className="space-y-2">
                    {exportJobs.map((job: any) => (
                        <div
                            key={job.id}
                            className="rounded-lg border border-border/50 bg-muted/20 p-3"
                        >
                            <div className="flex items-center gap-3">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <StatusBadge status={job.status} />
                                        <span className="text-[10px] text-muted-foreground uppercase">
                                            {job.format || 'pptx'}
                                        </span>
                                        {job.file_size_bytes && (
                                            <span className="text-[10px] text-muted-foreground">
                                                {formatSize(job.file_size_bytes)}
                                            </span>
                                        )}
                                        {job.status === 'completed' && job.validator_results?.quality_score != null && (
                                            <QualityScoreBadge score={job.validator_results.quality_score} />
                                        )}
                                    </div>
                                    {job.created_at && (
                                        <span className="text-[10px] text-muted-foreground/60 mt-0.5 block">
                                            {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
                                        </span>
                                    )}
                                </div>
                                {job.status === 'completed' && (
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-7 w-7 text-primary hover:text-primary/80"
                                        onClick={() => handleDownload(job)}
                                        title="Download PPTX"
                                    >
                                        <Download className="w-4 h-4" />
                                    </Button>
                                )}
                            </div>
                            {/* Failed export error */}
                            {job.status === 'failed' && job.error && (
                                <div className="mt-2 p-2 rounded bg-red-500/10 border border-red-500/20 text-[11px] text-red-400">
                                    {job.error}
                                </div>
                            )}
                            {/* Validation details */}
                            {job.status === 'completed' && job.validator_results && (
                                <ValidationSummary results={job.validator_results} />
                            )}
                        </div>
                    ))}
                </div>
            )}

            {isSlides && (
                <ThemePickerDialog
                    open={themePickerOpen}
                    onOpenChange={setThemePickerOpen}
                    onSelect={handleThemeSelected}
                />
            )}
            {isDocument && (
                <DocFormatPickerDialog
                    open={docFormatPickerOpen}
                    onOpenChange={setDocFormatPickerOpen}
                    onSelect={handleDocFormatSelected}
                />
            )}
            {isSheet && (
                <SheetFormatPickerDialog
                    open={sheetFormatPickerOpen}
                    onOpenChange={setSheetFormatPickerOpen}
                    onSelect={handleSheetFormatSelected}
                />
            )}
        </div>
    );
}

// --- Export Button (lightweight, for StudioWorkspace header) ---

export function ExportButton({ artifactId, artifactType }: { artifactId: string; artifactType?: string }) {
    const isExporting = useAppStore(s => s.isExporting);
    const startExport = useAppStore(s => s.startExport);
    const [themePickerOpen, setThemePickerOpen] = useState(false);
    const [docFormatPickerOpen, setDocFormatPickerOpen] = useState(false);
    const [sheetFormatPickerOpen, setSheetFormatPickerOpen] = useState(false);

    const isDocument = artifactType === 'document';
    const isSheet = artifactType === 'sheet';

    const handleThemeSelected = (themeId: string, strictLayout?: boolean, generateImages?: boolean) => {
        startExport(artifactId, 'pptx', themeId, strictLayout, generateImages);
    };

    const handleDocFormatSelected = (format: string, generateImages?: boolean) => {
        startExport(artifactId, format, undefined, undefined, generateImages);
    };

    const handleSheetFormatSelected = (format: string) => {
        startExport(artifactId, format);
    };

    return (
        <>
            <button
                onClick={() => isSheet ? setSheetFormatPickerOpen(true) : isDocument ? setDocFormatPickerOpen(true) : setThemePickerOpen(true)}
                disabled={isExporting}
                className="px-2 py-0.5 rounded text-[9px] uppercase font-bold tracking-tighter bg-primary/10 text-primary hover:bg-primary/20 transition-colors disabled:opacity-50 flex items-center gap-1"
            >
                {isExporting ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                    <FileDown className="w-3 h-3" />
                )}
                Export
            </button>
            {!isDocument && !isSheet && (
                <ThemePickerDialog
                    open={themePickerOpen}
                    onOpenChange={setThemePickerOpen}
                    onSelect={handleThemeSelected}
                />
            )}
            {isDocument && (
                <DocFormatPickerDialog
                    open={docFormatPickerOpen}
                    onOpenChange={setDocFormatPickerOpen}
                    onSelect={handleDocFormatSelected}
                />
            )}
            {isSheet && (
                <SheetFormatPickerDialog
                    open={sheetFormatPickerOpen}
                    onOpenChange={setSheetFormatPickerOpen}
                    onSelect={handleSheetFormatSelected}
                />
            )}
        </>
    );
}
