import React from 'react';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils'
import { ExternalLink, Clock, ChevronUp, Globe, Newspaper, ArrowLeft, Loader2 } from 'lucide-react';

// Helper to strip HTML tags from RSS summaries
const stripHtml = (html: string): string => {
    if (!html) return '';
    return html.replace(/<[^>]*>/g, '').trim();
};

export const NewsList: React.FC = () => {
    const {
        newsItems,
        isNewsLoading,
        fetchNewsFeed,
        selectedNewsSourceId,
        openNewsTab,
        newsTabs,
        closeAllNewsTabs
    } = useAppStore();

    React.useEffect(() => {
        fetchNewsFeed(selectedNewsSourceId || undefined);
    }, [selectedNewsSourceId]);

    // If there are open tabs, show a "Back to Feed" option
    const hasOpenTabs = newsTabs.length > 0;

    if (isNewsLoading && newsItems.length === 0) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center space-y-4 bg-card">
                <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
                <p className="text-sm text-muted-foreground animate-pulse font-mono tracking-widest">FETCHING INTELLIGENCE...</p>
            </div>
        );
    }

    return (
        <div className="flex-1 flex flex-col bg-card overflow-hidden">
            {/* Toolbar */}
            <div className="h-12 border-b border-border bg-card flex items-center justify-between px-4 shrink-0">
                <div className="flex items-center gap-2">
                    {hasOpenTabs && (
                        <button
                            onClick={closeAllNewsTabs}
                            className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-cyan-400 hover:bg-cyan-500/10 rounded-md transition-colors"
                        >
                            <ArrowLeft className="w-3.5 h-3.5" />
                            Back to Feed
                        </button>
                    )}
                    {!hasOpenTabs && (
                        <>
                            <Globe className="w-4 h-4 text-cyan-400" />
                            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
                                {selectedNewsSourceId ? `Feed: ${selectedNewsSourceId.toUpperCase()}` : 'Global Intelligence Feed'}
                            </h3>
                        </>
                    )}
                </div>
                <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-mono">
                    <span>{newsItems.length} ITEMS</span>
                    <div className="w-1 h-1 bg-cyan-500 rounded-full" />
                    <button
                        onClick={() => fetchNewsFeed(selectedNewsSourceId || undefined)}
                        className="hover:text-cyan-400 transition-colors"
                    >
                        REFRESH
                    </button>
                </div>
            </div>

            {/* Feed Items */}
            <div className="flex-1 overflow-y-auto scrollbar-hide bg-muted/30">
                <div className="max-w-4xl mx-auto py-6 px-4 space-y-3">
                    {newsItems.map((item, index) => (
                        <div
                            key={item.id}
                            className="group relative flex gap-4 p-4 rounded-xl border border-border bg-card shadow-sm hover:shadow-md transition-all hover:border-cyan-500/30"
                        >
                            {/* Ranking */}
                            <div className="flex flex-col items-center gap-1 shrink-0 pt-1">
                                <span className="text-[10px] font-bold text-muted-foreground/50 font-mono">{(index + 1).toString().padStart(2, '0')}</span>
                                <button className="p-1 hover:text-cyan-400 transition-colors text-muted-foreground/30">
                                    <ChevronUp className="w-4 h-4" />
                                </button>
                            </div>

                            {/* Content */}
                            <div className="flex-1 min-w-0 space-y-2">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex-1">
                                        {/* CLICKABLE TITLE - Opens in Reader Mode */}
                                        <h4
                                            onClick={() => openNewsTab(item.url)}
                                            className="text-sm font-semibold leading-relaxed text-foreground line-clamp-2 cursor-pointer hover:text-cyan-500 transition-colors"
                                        >
                                            {item.title}
                                        </h4>
                                        {item.url && (
                                            <span className="text-[10px] font-normal text-muted-foreground/60 font-mono">
                                                {new URL(item.url).hostname.replace('www.', '')}
                                            </span>
                                        )}
                                    </div>
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            window.open(item.url, '_blank');
                                        }}
                                        className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors shrink-0"
                                        title="Open in Browser"
                                    >
                                        <ExternalLink className="w-3.5 h-3.5" />
                                    </button>
                                </div>

                                {/* Summary - Strip HTML tags */}
                                {item.summary && (
                                    <p className="text-xs text-muted-foreground line-clamp-2 leading-normal">
                                        {stripHtml(item.summary)}
                                    </p>
                                )}

                                <div className="flex items-center gap-4 text-[10px] font-mono text-muted-foreground/60 pt-1">
                                    <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-muted">
                                        <Clock className="w-3 h-3" />
                                        <span>{new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                    </div>
                                    <span className="uppercase tracking-widest font-bold text-cyan-400/60">{item.source_name}</span>

                                    {item.points && (
                                        <span className="text-muted-foreground">
                                            {item.points} pts
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}

                    {newsItems.length === 0 && !isNewsLoading && (
                        <div className="py-20 text-center space-y-4">
                            <div className="p-4 bg-muted rounded-full w-fit mx-auto">
                                <Newspaper className="w-8 h-8 text-muted-foreground/40" />
                            </div>
                            <div>
                                <h4 className="text-sm font-bold text-muted-foreground uppercase tracking-widest">No Intelligence Gathered</h4>
                                <p className="text-xs text-muted-foreground/60 mt-1">Select a source or try refreshing the feed.</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
