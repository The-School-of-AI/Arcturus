import React, { useState, useEffect, useMemo } from 'react';
import {
    Hammer, Plus, RefreshCw, CheckCircle, XCircle, ChevronRight, ChevronDown,
    History, FileText, Presentation, Table2, Loader2
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
                <div key={item.id} className="border-l-2 border-primary/30 pl-3">
                    <p className="text-sm font-medium text-foreground">{item.title}</p>
                    {item.description && (
                        <p className="text-xs text-muted-foreground mt-0.5">{item.description}</p>
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

                <div className="space-y-4 py-2">
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
                                        "flex flex-col items-center gap-1.5 p-3 rounded-lg border transition-colors",
                                        selected
                                            ? "border-primary bg-primary/10 text-primary"
                                            : "border-border hover:border-primary/50 text-muted-foreground hover:text-foreground"
                                    )}
                                >
                                    <Icon className="w-5 h-5" />
                                    <span className="text-xs font-medium">{meta.label}</span>
                                </button>
                            );
                        })}
                    </div>

                    {/* Title */}
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium text-muted-foreground">Title (optional)</label>
                        <Input
                            value={title}
                            onChange={e => setTitle(e.target.value)}
                            placeholder="e.g., Q4 Sales Report"
                            disabled={isGenerating}
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
                            rows={4}
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
    const [revisions, setRevisions] = useState<any[]>([]);
    const [revisionsLoading, setRevisionsLoading] = useState(false);
    const [showContentTree, setShowContentTree] = useState(false);

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
            <div className="p-6 space-y-6">
                {/* Header */}
                <div className="flex items-start gap-3">
                    <div className={cn("p-2.5 rounded-lg bg-muted/50 border border-border/50", meta.color)}>
                        <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <h2 className="text-lg font-semibold text-foreground truncate">
                            {artifact.title || 'Untitled'}
                        </h2>
                        <div className="flex items-center gap-2 mt-1">
                            <span className="text-xs text-muted-foreground capitalize">{artifact.type}</span>
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
                                <div
                                    key={rev.id}
                                    className="rounded-lg border border-border/50 bg-muted/20 p-3 flex items-center gap-3"
                                >
                                    <div className="w-2 h-2 rounded-full bg-primary/60 shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-xs font-medium text-foreground truncate">
                                            {rev.change_summary}
                                        </p>
                                        {rev.created_at && (
                                            <span className="text-[10px] text-muted-foreground">
                                                {formatDistanceToNow(new Date(rev.created_at), { addSuffix: true })}
                                            </span>
                                        )}
                                    </div>
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

    const [createOpen, setCreateOpen] = useState(false);
    const [search, setSearch] = useState('');

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
                        <span className="text-sm font-semibold text-foreground tracking-tight">Forge</span>
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
                </div>

                {/* Search */}
                <div className="px-3 py-2 border-b border-border/30">
                    <Input
                        className="h-7 text-xs"
                        placeholder="Search artifacts..."
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                    />
                </div>

                {/* List */}
                <ScrollArea className="flex-1">
                    <div className="p-2 space-y-1">
                        {filtered.length === 0 && (
                            <div className="text-center text-muted-foreground text-xs py-12 space-y-2">
                                <Hammer className="w-8 h-8 mx-auto opacity-30" />
                                <p>No artifacts yet</p>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="text-xs"
                                    onClick={() => setCreateOpen(true)}
                                >
                                    <Plus className="w-3 h-3 mr-1" />
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
                                <button
                                    key={a.id}
                                    onClick={() => setActiveArtifactId(a.id)}
                                    className={cn(
                                        "w-full text-left px-3 py-2.5 rounded-lg transition-all duration-200",
                                        isActive
                                            ? "bg-primary/10 border border-primary/30"
                                            : "hover:bg-muted/50 border border-transparent"
                                    )}
                                >
                                    <div className="flex items-start gap-2.5">
                                        <Icon className={cn("w-4 h-4 mt-0.5 shrink-0", meta.color)} />
                                        <div className="flex-1 min-w-0">
                                            <p className={cn(
                                                "text-[13px] font-medium truncate",
                                                isActive ? "text-primary" : "text-foreground"
                                            )}>
                                                {a.title || 'Untitled'}
                                            </p>
                                            <div className="flex items-center gap-1.5 mt-0.5">
                                                <span className="text-[10px] text-muted-foreground capitalize">{a.type}</span>
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
                                    </div>
                                </button>
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
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground space-y-4">
                        <div className="p-6 bg-muted/30 rounded-full ring-1 ring-border/50">
                            <Hammer className="w-10 h-10 opacity-40" />
                        </div>
                        <div className="text-center space-y-1">
                            <h3 className="text-sm font-semibold text-foreground/80">Forge Studio</h3>
                            <p className="text-xs max-w-[280px]">
                                Create slides, documents, and spreadsheets with AI. Select an artifact from the list or create a new one.
                            </p>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCreateOpen(true)}
                            className="mt-2"
                        >
                            <Plus className="w-3.5 h-3.5 mr-1.5" />
                            Create Artifact
                        </Button>
                    </div>
                )}
            </div>

            {/* Create Dialog */}
            <CreateDialog open={createOpen} onOpenChange={setCreateOpen} />
        </div>
    );
}
