import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import {
    Clock,
    FileText,
    Loader2,
    Plus,
    RefreshCw,
    Search
} from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { usePagesStore } from '../usePagesStore';

export const PagesSidebar: React.FC = () => {
    const pages = usePagesStore(s => s.pages);
    const selectedPage = usePagesStore(s => s.selectedPage);
    const isLoading = usePagesStore(s => s.isLoading);
    const isGenerating = usePagesStore(s => s.isGenerating);
    const setPages = usePagesStore(s => s.setPages);
    const setSelectedPage = usePagesStore(s => s.setSelectedPage);
    const setIsLoading = usePagesStore(s => s.setIsLoading);
    const setIsGenerating = usePagesStore(s => s.setIsGenerating);

    const [searchQuery, setSearchQuery] = useState('');
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [newQuery, setNewQuery] = useState('');

    useEffect(() => {
        loadPages();
    }, []);

    const loadPages = async () => {
        setIsLoading(true);
        try {
            const results = await api.getPages();
            setPages(Array.isArray(results) ? results : []);
        } catch {
            setPages([]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleGenerate = async () => {
        if (!newQuery.trim()) return;
        setIsGenerating(true);
        setIsDialogOpen(false);
        const query = newQuery.trim();
        setNewQuery('');
        try {
            const data = await api.generatePage({ query, created_by: 'user' });
            pollJob(data.job_id);
        } catch {
            setIsGenerating(false);
        }
    };

    const pollJob = async (jobId: string) => {
        let attempts = 0;
        const check = async () => {
            try {
                const job = await api.getPageJob(jobId);
                if (job.status === 'done' || job.status === 'complete') {
                    await loadPages();
                    setIsGenerating(false);
                } else if (job.status === 'failed') {
                    setIsGenerating(false);
                } else if (attempts++ < 60) {
                    setTimeout(check, 2000);
                } else {
                    setIsGenerating(false);
                }
            } catch {
                setIsGenerating(false);
            }
        };
        check();
    };

    const filtered = pages.filter(p =>
        !searchQuery || (p.query || '').toLowerCase().includes(searchQuery.toLowerCase())
    );

    const statusColors: Record<string, string> = {
        pending: 'bg-yellow-500/15 text-yellow-400',
        generating: 'bg-blue-500/15 text-blue-400',
        complete: 'bg-green-500/15 text-green-400',
        failed: 'bg-red-500/15 text-red-400',
    };

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="px-3 pt-3 pb-2 flex items-center justify-between gap-2 border-b border-border/30">
                <div className="flex items-center gap-2 min-w-0">
                    <FileText className="w-4 h-4 text-primary shrink-0" />
                    <span className="font-semibold text-sm truncate">Spark Pages</span>
                    <Badge variant="outline" className="text-xs shrink-0">
                        {pages.length}
                    </Badge>
                </div>
                <div className="flex gap-1 shrink-0">
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={loadPages} disabled={isLoading}>
                        <RefreshCw className={cn('w-3.5 h-3.5', isLoading && 'animate-spin')} />
                    </Button>
                    <Button size="sm" className="h-7 px-2 gap-1 text-xs" onClick={() => setIsDialogOpen(true)} disabled={isGenerating}>
                        {isGenerating ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                            <Plus className="w-3.5 h-3.5" />
                        )}
                        New
                    </Button>
                </div>
            </div>

            {/* Search */}
            <div className="px-3 py-2 border-b border-border/30">
                <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                    <Input
                        placeholder="Search pages..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-8 h-8 text-xs"
                    />
                </div>
            </div>

            {/* List */}
            <ScrollArea className="flex-1">
                {isLoading && pages.length === 0 ? (
                    <div className="flex justify-center pt-12">
                        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                    </div>
                ) : filtered.length === 0 ? (
                    <div className="flex flex-col items-center gap-2 pt-12 px-4 text-center">
                        <FileText className="w-8 h-8 text-muted-foreground/30" />
                        <p className="text-xs text-muted-foreground">
                            {searchQuery ? 'No matches' : 'Generate your first page'}
                        </p>
                    </div>
                ) : (
                    <div className="p-2 space-y-1">
                        {filtered.map(page => (
                            <button
                                key={page.id}
                                onClick={() => setSelectedPage(page)}
                                className={cn(
                                    'w-full text-left rounded-lg px-3 py-2.5 transition-all group',
                                    selectedPage?.id === page.id
                                        ? 'bg-primary/15 border border-primary/30'
                                        : 'hover:bg-accent/60 border border-transparent'
                                )}
                            >
                                <div className="flex items-start justify-between gap-2 mb-1">
                                    <span className="text-xs font-medium line-clamp-2 leading-tight flex-1">
                                        {page.query}
                                    </span>
                                    <Badge className={cn('text-[10px] px-1.5 py-0 shrink-0 leading-4', statusColors[page.status] ?? statusColors.pending)}>
                                        {page.status}
                                    </Badge>
                                </div>
                                <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                                    <Clock className="w-2.5 h-2.5" />
                                    <span>
                                        {(() => {
                                            try {
                                                const d = new Date(page.created_at || Date.now());
                                                return isNaN(d.getTime()) ? 'recently' : formatDistanceToNow(d, { addSuffix: true });
                                            } catch { return 'recently'; }
                                        })()}
                                    </span>
                                    <span className="ml-auto">{page.sections?.length ?? 0} sections</span>
                                </div>
                            </button>
                        ))}
                    </div>
                )}
            </ScrollArea>

            {/* Generating indicator */}
            {isGenerating && (
                <div className="px-3 py-2 border-t border-border/30">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
                        Generating page...
                    </div>
                </div>
            )}

            {/* Generate Dialog */}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Generate New Page</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div>
                            <label className="text-sm font-medium mb-2 block">Query</label>
                            <Input
                                placeholder="e.g., iPhone vs Android, how to deploy React, AI market trends..."
                                value={newQuery}
                                onChange={(e) => setNewQuery(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                                autoFocus
                            />
                            <p className="text-xs text-muted-foreground mt-2">
                                💡 Smart template detection auto-selects the best format for your query.
                            </p>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
                        <Button onClick={handleGenerate} disabled={!newQuery.trim()}>
                            Generate
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};
