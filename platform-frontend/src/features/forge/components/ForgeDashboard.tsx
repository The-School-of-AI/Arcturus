import React, { useState, useEffect, useMemo } from 'react';
import {
    Hammer, Plus, RefreshCw, CheckCircle, XCircle, ChevronRight, ChevronDown,
    History, FileText, Presentation, Table2, Loader2, AlertCircle,
    Send, AlertTriangle, Eye, Trash2, RotateCcw
} from 'lucide-react';
import { useAppStore } from '@/store';
import { api } from '@/lib/api';
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
import { ArtifactPromptBanner } from './ArtifactPromptBanner';

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

// --- Outline tree viewer ---

function OutlineTree({ items }: { items: any[] }) {
    if (!items?.length) return <span className="text-muted-foreground text-xs italic">No outline items</span>;

    return (
        <div className="space-y-2">
            {items.map((item: any) => (
                <div key={item.id} className="border-l-2 border-primary/30 pl-3 min-w-0">
                    <p className="text-sm font-medium text-foreground break-words">{item.title}</p>
                    {item.description && (
                        <p className="text-xs text-muted-foreground mt-0.5 break-words">{item.description}</p>
                    )}
                    {item.children?.length > 0 && (
                        <div className="ml-2 mt-1">
                            <OutlineTree items={item.children} />
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}

// --- Create Artifact Dialog ---

function CreateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
    const createArtifact = useAppStore(s => s.createArtifact);
    const isGenerating = useAppStore(s => s.isGenerating);

    const [type, setType] = useState<'slides' | 'documents' | 'sheets'>('slides');
    const [title, setTitle] = useState('');
    const [prompt, setPrompt] = useState('');

    const handleCreate = async () => {
        if (!prompt.trim()) return;
        await createArtifact(type, prompt, title || undefined);
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

    const meta = TYPE_META[artifact.type] || TYPE_META.document;
    const Icon = meta.icon;
    const outlineStatus = artifact.outline?.status;

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
                </div>

                <ArtifactPromptBanner key={artifact.id} prompt={artifact.creation_prompt} />

                {/* Outline Section */}
                {artifact.outline && (
                    <div className="space-y-3">
                        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">Outline</h3>
                        <div className="rounded-lg border border-border/50 bg-muted/20 p-4">
                            <OutlineTree items={artifact.outline.items || []} />
                        </div>

                        {/* Approve / Reject */}
                        {outlineStatus === 'pending' && (
                            <div className="flex gap-2">
                                <Button
                                    onClick={() => approveOutline(artifact.id)}
                                    disabled={isApproving}
                                    className="flex-1 bg-green-600 hover:bg-green-700 text-white"
                                >
                                    {isApproving ? (
                                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                    ) : (
                                        <CheckCircle className="w-4 h-4 mr-2" />
                                    )}
                                    Approve
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
            {/* Left Pane — Artifact List */}
            <div className="w-80 border-r border-border/50 flex flex-col shrink-0">
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

                            return (
                                <div
                                    key={a.id}
                                    className={cn(
                                        "group w-full text-left px-3 py-2.5 rounded-lg transition-all duration-200 flex items-start gap-2.5 cursor-pointer",
                                        isActive
                                            ? "bg-primary/10 border border-primary/30"
                                            : "hover:bg-muted/50 border border-transparent"
                                    )}
                                    onClick={() => setActiveArtifactId(a.id)}
                                >
                                    <Icon className={cn("w-4 h-4 mt-0.5 shrink-0", meta.color)} />
                                    <div className="flex-1 min-w-0">
                                        <p className={cn(
                                            "text-sm font-medium truncate",
                                            isActive ? "text-primary" : "text-foreground"
                                        )}>
                                            {a.title || 'Untitled'}
                                        </p>
                                        <div className="flex items-center gap-1.5 mt-0.5">
                                            <span className="text-xs text-muted-foreground capitalize">{a.type}</span>
                                            {outlineStatus && (
                                                <span className={cn(
                                                    "px-1 py-0 rounded text-[8px] uppercase font-bold tracking-tighter",
                                                    STATUS_STYLE[outlineStatus]
                                                )}>
                                                    {outlineStatus}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <button
                                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 text-muted-foreground hover:text-red-400 transition-all shrink-0 mt-0.5"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setDeleteTarget({ id: a.id, title: a.title || 'Untitled' });
                                        }}
                                        title="Delete artifact"
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>
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
