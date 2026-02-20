import React from 'react';
import { Plus, Presentation, FileText, Table2, Search } from 'lucide-react';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { StudioCreationModal } from './StudioCreationModal';

const TYPE_ICON: Record<string, React.ElementType> = {
    slides: Presentation,
    document: FileText,
    sheet: Table2,
};

const TYPE_COLOR: Record<string, string> = {
    slides: 'text-blue-400',
    document: 'text-emerald-400',
    sheet: 'text-amber-400',
};

export function StudioSidebar() {
    const artifacts = useAppStore(s => s.studioArtifacts);
    const activeId = useAppStore(s => s.activeArtifactId);
    const setActiveId = useAppStore(s => s.setActiveArtifactId);
    const fetchArtifacts = useAppStore(s => s.fetchArtifacts);
    const setOpen = useAppStore(s => s.setIsStudioModalOpen);

    const [search, setSearch] = React.useState('');

    React.useEffect(() => {
        fetchArtifacts();
    }, [fetchArtifacts]);

    const filtered = React.useMemo(() => {
        if (!search.trim()) return artifacts;
        const q = search.toLowerCase();
        return artifacts.filter((a: any) =>
            a.title?.toLowerCase().includes(q) || a.type?.toLowerCase().includes(q)
        );
    }, [artifacts, search]);

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground">
            {/* Header */}
            <div className="p-2 border-b border-border/50 bg-muted/20 flex items-center gap-1.5 shrink-0">
                <div className="relative flex-1 group">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    <input
                        className="w-full bg-background/50 border-transparent focus:bg-background focus:border-border rounded-md text-xs pl-8 pr-2 h-8 transition-all placeholder:text-muted-foreground outline-none"
                        placeholder="Search artifacts..."
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                    />
                </div>
                <button
                    onClick={() => setOpen(true)}
                    className="h-8 w-8 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-background/80 rounded-md"
                    title="Create Artifact"
                >
                    <Plus className="w-4 h-4" />
                </button>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-hide">
                {filtered.length === 0 && (
                    <div className="text-center text-muted-foreground text-xs py-8 opacity-60">
                        No artifacts yet. Click + to create one.
                    </div>
                )}
                {filtered.map((a: any) => {
                    const Icon = TYPE_ICON[a.type] || FileText;
                    const color = TYPE_COLOR[a.type] || 'text-muted-foreground';
                    const isActive = activeId === a.id;
                    const outlineStatus = a.outline?.status;

                    return (
                        <div
                            key={a.id}
                            onClick={() => setActiveId(a.id)}
                            className={cn(
                                "group relative p-3 rounded-xl border transition-all duration-300 cursor-pointer",
                                "hover:shadow-md",
                                isActive
                                    ? "border-primary/40 hover:border-primary/60 bg-primary/5"
                                    : "border-border/50 hover:border-primary/50 hover:bg-accent/50"
                            )}
                        >
                            <div className="flex items-start gap-2.5">
                                <Icon className={cn("w-4 h-4 mt-0.5 shrink-0", color)} />
                                <div className="flex-1 min-w-0">
                                    <p className={cn(
                                        "text-[13px] font-medium truncate",
                                        isActive ? "text-primary" : "text-foreground"
                                    )}>
                                        {a.title || 'Untitled'}
                                    </p>
                                    <div className="flex items-center gap-2 mt-1">
                                        <span className="text-[10px] text-muted-foreground capitalize">{a.type}</span>
                                        {outlineStatus && (
                                            <span className={cn(
                                                "px-1.5 py-0.5 rounded text-[9px] uppercase font-bold tracking-tighter",
                                                outlineStatus === 'pending' && "bg-orange-500/10 text-orange-400",
                                                outlineStatus === 'approved' && "bg-green-500/10 text-green-400",
                                                outlineStatus === 'rejected' && "bg-red-500/10 text-red-400",
                                            )}>
                                                {outlineStatus}
                                            </span>
                                        )}
                                    </div>
                                    {a.updated_at && (
                                        <span className="text-[9px] text-muted-foreground/60 mt-1 block">
                                            {formatDistanceToNow(new Date(a.updated_at), { addSuffix: true })}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            <StudioCreationModal />
        </div>
    );
}
