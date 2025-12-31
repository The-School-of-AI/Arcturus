import React from 'react';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { X, ExternalLink, RefreshCw, ChevronLeft, ChevronRight, Globe, Lock, ShieldCheck } from 'lucide-react';

export const NewsTabViewer: React.FC = () => {
    const {
        newsTabs,
        activeNewsTab,
        setActiveNewsTab,
        closeNewsTab,
        closeAllNewsTabs
    } = useAppStore();

    if (newsTabs.length === 0) return null;

    const activeUrl = activeNewsTab || newsTabs[0];

    return (
        <div className="flex-1 flex flex-col bg-background overflow-hidden border-x border-border/50">
            {/* Tab Bar */}
            <div className="h-10 bg-muted/40 flex items-center px-2 gap-1 overflow-x-auto scrollbar-hide border-b border-border/50 shrink-0">
                {newsTabs.map((url) => (
                    <div
                        key={url}
                        className={cn(
                            "group flex items-center gap-2 px-3 py-1.5 rounded-t-lg text-[11px] font-medium transition-all max-w-[200px] shrink-0 cursor-pointer",
                            activeNewsTab === url
                                ? "bg-card text-foreground shadow-sm border-t border-x border-border/50"
                                : "text-muted-foreground hover:bg-muted/60"
                        )}
                        onClick={() => setActiveNewsTab(url)}
                    >
                        <Globe className="w-3 h-3 text-cyan-400 shrink-0" />
                        <span className="truncate flex-1">{new URL(url).hostname}</span>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                closeNewsTab(url);
                            }}
                            className="p-0.5 hover:bg-muted rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                            <X className="w-3 h-3" />
                        </button>
                    </div>
                ))}

                <div className="flex-1" />

                <button
                    onClick={closeAllNewsTabs}
                    className="text-[10px] text-muted-foreground hover:text-red-400 px-2 font-bold uppercase tracking-tighter transition-colors"
                >
                    Close All
                </button>
            </div>

            {/* Browser-like Toolbar */}
            <div className="h-10 bg-card border-b border-border/50 flex items-center px-4 gap-3 shrink-0">
                <div className="flex items-center gap-1">
                    <button className="p-1 hover:bg-muted rounded-md text-muted-foreground transition-colors disabled:opacity-30" disabled>
                        <ChevronLeft className="w-4 h-4" />
                    </button>
                    <button className="p-1 hover:bg-muted rounded-md text-muted-foreground transition-colors disabled:opacity-30" disabled>
                        <ChevronRight className="w-4 h-4" />
                    </button>
                    <button
                        onClick={() => {
                            const iframe = document.getElementById('news-content-iframe') as HTMLIFrameElement;
                            if (iframe) iframe.src = iframe.src;
                        }}
                        className="p-1 hover:bg-muted rounded-md text-muted-foreground transition-colors"
                    >
                        <RefreshCw className="w-3.5 h-3.5" />
                    </button>
                </div>

                <div className="flex-1 flex items-center gap-2 bg-muted/50 px-3 py-1 rounded-full border border-border/50">
                    <Lock className="w-3 h-3 text-green-500/60" />
                    <span className="text-[11px] text-muted-foreground truncate font-mono">{activeUrl}</span>
                </div>

                <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-mono">
                    <ShieldCheck className="w-3.5 h-3.5 text-cyan-500/60" />
                    <span className="uppercase tracking-widest hidden sm:block">Sandboxed</span>
                    <button
                        onClick={() => window.open(activeUrl, '_blank')}
                        className="p-1.5 hover:bg-muted rounded-md transition-colors"
                    >
                        <ExternalLink className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 bg-white relative">
                <iframe
                    id="news-content-iframe"
                    src={activeUrl}
                    className="w-full h-full border-none shadow-inner"
                    sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                    title="News Article"
                />
            </div>
        </div>
    );
};
