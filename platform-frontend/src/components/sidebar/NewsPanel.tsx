import React from 'react';
import { Newspaper, Plus, Trash2, Globe, RefreshCw, Rss, ChevronLeft, FileText, Loader2 } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";

// Helper to strip HTML tags
const stripHtml = (html: string): string => {
    if (!html) return '';
    return html.replace(/<[^>]*>/g, '').trim();
};

export const NewsPanel: React.FC = () => {
    const {
        newsSources,
        selectedNewsSourceId,
        setSelectedNewsSourceId,
        fetchNewsSources,
        addNewsSource,
        deleteNewsSource,
        newsItems,
        isNewsLoading,
        openNewsTab,
        activeNewsTab
    } = useAppStore();

    const [isAddOpen, setIsAddOpen] = React.useState(false);
    const [newName, setNewName] = React.useState("");
    const [newUrl, setNewUrl] = React.useState("");

    React.useEffect(() => {
        fetchNewsSources();
    }, []);

    const handleAddSource = async () => {
        if (!newName.trim() || !newUrl.trim()) return;
        await addNewsSource(newName, newUrl);
        setNewName("");
        setNewUrl("");
        setIsAddOpen(false);
    };

    // When a source is selected, show its articles in the sidebar
    const showArticleList = selectedNewsSourceId !== null;

    return (
        <div className="flex flex-col h-full bg-card text-foreground">
            {/* Header */}
            <div className="p-4 border-b border-border flex items-center justify-between bg-card/50 backdrop-blur-md sticky top-0 z-10">
                <div className="flex items-center gap-2">
                    {showArticleList && (
                        <button
                            onClick={() => setSelectedNewsSourceId(null)}
                            className="p-1 hover:bg-muted rounded-md mr-1"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                    )}
                    <div className="p-1.5 bg-cyan-500/10 rounded-lg">
                        <Newspaper className="w-5 h-5 text-cyan-400" />
                    </div>
                    <div>
                        <h2 className="font-semibold text-sm tracking-tight text-foreground uppercase">
                            {showArticleList ? newsSources.find(s => s.id === selectedNewsSourceId)?.name || 'Feed' : 'News Sources'}
                        </h2>
                        <p className="text-[10px] text-cyan-400/80 font-mono tracking-widest">
                            {showArticleList ? `${newsItems.length} ARTICLES` : `${newsSources.length} SOURCES`}
                        </p>
                    </div>
                </div>
                <button
                    onClick={() => fetchNewsSources()}
                    className={cn("p-1.5 hover:bg-muted rounded-md transition-colors", isNewsLoading && "animate-spin")}
                >
                    <RefreshCw className="w-4 h-4 text-muted-foreground" />
                </button>
            </div>

            {/* Content - Show either sources or articles */}
            {!showArticleList ? (
                <>
                    {/* Add Source */}
                    <div className="p-3 border-b border-border/50 bg-muted/20">
                        <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
                            <DialogTrigger asChild>
                                <Button className="w-full gap-2 bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-900/20 font-semibold border-none">
                                    <Plus className="w-4 h-4" />
                                    Add News Source
                                </Button>
                            </DialogTrigger>
                            <DialogContent className="bg-card border-border sm:max-w-md text-foreground">
                                <DialogHeader>
                                    <DialogTitle className="text-foreground text-lg">Add Custom News Source</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium text-muted-foreground">Source Name</label>
                                        <Input
                                            placeholder="e.g., TechCrunch"
                                            value={newName}
                                            onChange={(e) => setNewName(e.target.value)}
                                            className="bg-muted border-input text-foreground"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium text-muted-foreground">URL (Site or RSS)</label>
                                        <Input
                                            placeholder="https://techcrunch.com"
                                            value={newUrl}
                                            onChange={(e) => setNewUrl(e.target.value)}
                                            className="bg-muted border-input text-foreground"
                                        />
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsAddOpen(false)}>Cancel</Button>
                                    <Button onClick={handleAddSource} className="bg-cyan-600 hover:bg-cyan-500 text-white font-semibold">Discover & Add</Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    </div>

                    {/* Source List */}
                    <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-hide">
                        {/* Global / All Feed */}
                        <div
                            onClick={() => setSelectedNewsSourceId(null)}
                            className={cn(
                                "group p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between",
                                selectedNewsSourceId === null
                                    ? "border-cyan-500/40 bg-cyan-500/5 text-cyan-400"
                                    : "border-border/50 hover:border-white/20 hover:bg-muted/30 text-muted-foreground hover:text-foreground"
                            )}
                        >
                            <div className="flex items-center gap-3">
                                <div className={cn("p-1.5 rounded-lg", selectedNewsSourceId === null ? "bg-cyan-500/20" : "bg-muted")}>
                                    <Globe className="w-4 h-4" />
                                </div>
                                <span className="text-sm font-medium">Global Feed</span>
                            </div>
                        </div>

                        <div className="h-4" />
                        <p className="text-[10px] font-bold text-muted-foreground px-1 uppercase tracking-widest">Available Sources</p>

                        {newsSources.map((source) => (
                            <div
                                key={source.id}
                                onClick={() => setSelectedNewsSourceId(source.id)}
                                className={cn(
                                    "group p-3 rounded-xl border transition-all cursor-pointer",
                                    selectedNewsSourceId === source.id
                                        ? "border-cyan-500/40 bg-cyan-500/5"
                                        : "border-border/50 hover:border-white/20 hover:bg-muted/30"
                                )}
                            >
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <div className={cn(
                                            "p-1.5 rounded-lg flex items-center justify-center",
                                            selectedNewsSourceId === source.id ? "bg-cyan-500/20 text-cyan-400" : "bg-muted text-muted-foreground"
                                        )}>
                                            {source.type === 'rss' ? (
                                                <Rss className="w-4 h-4" />
                                            ) : (
                                                <Globe className="w-4 h-4" />
                                            )}
                                        </div>
                                        <div className="flex flex-col min-w-0">
                                            <span className={cn(
                                                "text-sm font-medium truncate",
                                                selectedNewsSourceId === source.id ? "text-cyan-400" : "text-foreground"
                                            )}>{source.name}</span>
                                            <span className="text-[10px] text-muted-foreground truncate opacity-60 font-mono">{new URL(source.url).hostname}</span>
                                        </div>
                                    </div>
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            if (confirm(`Remove ${source.name}?`)) deleteNewsSource(source.id);
                                        }}
                                        className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/10 rounded-lg text-muted-foreground hover:text-red-400 transition-all"
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </>
            ) : (
                /* Article List for Selected Source */
                <div className="flex-1 overflow-y-auto scrollbar-hide">
                    {isNewsLoading && newsItems.length === 0 ? (
                        <div className="flex items-center justify-center py-10">
                            <Loader2 className="w-6 h-6 text-cyan-500 animate-spin" />
                        </div>
                    ) : newsItems.length === 0 ? (
                        <div className="py-10 text-center text-muted-foreground text-sm">
                            No articles available
                        </div>
                    ) : (
                        <div className="p-2 space-y-1">
                            {newsItems.map((item, index) => (
                                <div
                                    key={item.id}
                                    onClick={() => openNewsTab(item.url)}
                                    className={cn(
                                        "p-3 rounded-lg cursor-pointer transition-all border",
                                        activeNewsTab === item.url
                                            ? "bg-cyan-500/10 border-cyan-500/30"
                                            : "border-transparent hover:bg-muted/50 hover:border-border/50"
                                    )}
                                >
                                    <div className="flex items-start gap-2">
                                        <span className="text-[10px] font-mono text-muted-foreground/50 mt-0.5">
                                            {(index + 1).toString().padStart(2, '0')}
                                        </span>
                                        <div className="flex-1 min-w-0">
                                            <h4 className={cn(
                                                "text-xs font-medium line-clamp-2 leading-relaxed",
                                                activeNewsTab === item.url ? "text-cyan-400" : "text-foreground"
                                            )}>
                                                {item.title}
                                            </h4>
                                            {item.summary && (
                                                <p className="text-[10px] text-muted-foreground/60 line-clamp-1 mt-1">
                                                    {stripHtml(item.summary)}
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
