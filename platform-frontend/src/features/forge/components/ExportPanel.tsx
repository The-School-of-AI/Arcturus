import React, { useState, useEffect } from 'react';
import {
    Download, Loader2, CheckCircle, AlertCircle, Palette, FileDown
} from 'lucide-react';
import { useAppStore } from '@/store';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';

// --- Theme Picker Dialog ---

function ThemePickerDialog({
    open,
    onOpenChange,
    onSelect,
}: {
    open: boolean;
    onOpenChange: (v: boolean) => void;
    onSelect: (themeId: string) => void;
}) {
    const themes = useAppStore(s => s.studioThemes);
    const fetchThemes = useAppStore(s => s.fetchThemes);
    const [selected, setSelected] = useState<string | null>(null);

    useEffect(() => {
        if (open) fetchThemes();
    }, [open, fetchThemes]);

    const handleConfirm = () => {
        if (selected) {
            onSelect(selected);
            onOpenChange(false);
            setSelected(null);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
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
                            <button
                                key={theme.id}
                                onClick={() => setSelected(theme.id)}
                                className={cn(
                                    "text-left p-3 rounded-lg border transition-all duration-150",
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
                                <p className="text-[10px] text-muted-foreground/60 mt-1">
                                    {theme.font_heading} / {theme.font_body}
                                </p>
                            </button>
                        ))}
                    </div>
                    {themes.length === 0 && (
                        <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                            Loading themes...
                        </div>
                    )}
                </ScrollArea>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button onClick={handleConfirm} disabled={!selected}>
                        <FileDown className="w-4 h-4 mr-2" />
                        Export with Theme
                    </Button>
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

// --- Export Panel (for ForgeDashboard ArtifactDetail) ---

export function ExportPanel({ artifact }: { artifact: any }) {
    const exportJobs = useAppStore(s => s.exportJobs);
    const isExporting = useAppStore(s => s.isExporting);
    const startExport = useAppStore(s => s.startExport);
    const [themePickerOpen, setThemePickerOpen] = useState(false);

    // Only show for slides with content_tree
    if (artifact.type !== 'slides' || !artifact.content_tree) return null;

    const handleThemeSelected = (themeId: string) => {
        startExport(artifact.id, themeId);
    };

    const handleDownload = async (job: any) => {
        const url = api.getExportDownloadUrl(artifact.id, job.id);
        const defaultName = `${artifact.title || 'slides'}.pptx`;
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
                <Button
                    size="sm"
                    onClick={() => setThemePickerOpen(true)}
                    disabled={isExporting}
                    className="h-7 text-xs"
                >
                    {isExporting ? (
                        <>
                            <Loader2 className="w-3 h-3 animate-spin mr-1.5" />
                            Exporting...
                        </>
                    ) : (
                        <>
                            <Palette className="w-3 h-3 mr-1.5" />
                            Export PPTX
                        </>
                    )}
                </Button>
            </div>

            {/* Export jobs list */}
            {exportJobs.length > 0 && (
                <div className="space-y-2">
                    {exportJobs.map((job: any) => (
                        <div
                            key={job.id}
                            className="rounded-lg border border-border/50 bg-muted/20 p-3 flex items-center gap-3"
                        >
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
                    ))}
                </div>
            )}

            <ThemePickerDialog
                open={themePickerOpen}
                onOpenChange={setThemePickerOpen}
                onSelect={handleThemeSelected}
            />
        </div>
    );
}

// --- Export Button (lightweight, for StudioWorkspace header) ---

export function ExportButton({ artifactId }: { artifactId: string }) {
    const isExporting = useAppStore(s => s.isExporting);
    const startExport = useAppStore(s => s.startExport);
    const [themePickerOpen, setThemePickerOpen] = useState(false);

    const handleThemeSelected = (themeId: string) => {
        startExport(artifactId, themeId);
    };

    return (
        <>
            <button
                onClick={() => setThemePickerOpen(true)}
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
            <ThemePickerDialog
                open={themePickerOpen}
                onOpenChange={setThemePickerOpen}
                onSelect={handleThemeSelected}
            />
        </>
    );
}
