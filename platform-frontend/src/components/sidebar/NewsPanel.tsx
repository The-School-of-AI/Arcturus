import React, { useState } from 'react';
import { Newspaper, Plus, Trash2, Globe, RefreshCw, Rss, ChevronLeft, Loader2, Bookmark, BookmarkCheck, Search, X, ExternalLink } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import axios from 'axios';
import { API_BASE } from '@/lib/api';

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
        fetchNewsFeed,
        addNewsSource,
        deleteNewsSource,
        newsItems,
        isNewsLoading,
        openNewsTab,
        activeNewsTab,
        savedArticles,
        saveArticle,
        deleteSavedArticle,
        searchResults,
        setSearchResults,
        newsViewMode: viewMode,
        setNewsViewMode: setViewMode,
        newsSearchQuery: searchQuery,
        setNewsSearchQuery: setSearchQuery,
        isNewsAddOpen: isAddOpen,
        setIsNewsAddOpen: setIsAddOpen
    } = useAppStore();

    const [newName, setNewName] = React.useState("");
    const [newUrl, setNewUrl] = React.useState("");
    const [isSearching, setIsSearching] = React.useState(false);
    const [isAutoSearch, setIsAutoSearch] = React.useState(false);

    React.useEffect(() => {
        fetchNewsSources();
    }, []);

    // When a source is selected, switch to articles view
    const handleSelectSource = (sourceId: string | null) => {
        const source = newsSources.find(s => s.id === sourceId);

        // Check for Andrej Karpathy
        if (source && source.name.toLowerCase().includes("andrej karpathy")) {
            setIsAutoSearch(true);
            setSearchQuery("Andrej Karpathy news");
            performSearch("Andrej Karpathy news", 20);
            return;
        }

        setIsAutoSearch(false);
        setSelectedNewsSourceId(sourceId);
        if (sourceId !== null) {
            setViewMode('articles');
        }
    };

    const handleAddSource = async () => {
        if (!newName.trim() || !newUrl.trim()) return;
        await addNewsSource(newName, newUrl);
        setNewName("");
        setNewUrl("");
        setIsAddOpen(false);
    };

    const selectedSource = newsSources.find(s => s.id === selectedNewsSourceId);

    // Refresh news when source changes
    React.useEffect(() => {
        if (viewMode === 'articles') {
            fetchNewsFeed(selectedNewsSourceId || undefined);
        }
    }, [selectedNewsSourceId, fetchNewsFeed, viewMode]);

    // Check if an article is already saved
    const isArticleSaved = (url: string) => savedArticles.some(a => a.url === url);

    // --- Search Logic ---
    const performSearch = async (query: string, limit: number = 10) => {
        if (!query.trim()) return;

        setIsSearching(true);
        setViewMode('search');
        setSearchResults([]); // Clear previous

        try {
            const res = await axios.post(`${API_BASE}/mcp/call`, {
                server_name: "browser",
                tool_name: "web_search",
                arguments: { string: query, integer: limit }
            });

            let results: any[] = [];
            // Parse results - standardizing tool output
            let rawData = null;
            if (res.data.content && Array.isArray(res.data.content) && res.data.content.length > 0) {
                rawData = res.data.content[0].text;
            } else if (res.data.result) {
                rawData = res.data.result;
            }

            if (rawData) {
                try {
                    const data = JSON.parse(rawData);
                    if (Array.isArray(data)) {
                        results = data.map((item: any) => {
                            if (typeof item === 'string') return { title: item, url: item, description: "No preview available", source: "web" };
                            return {
                                title: item.title || item.url,
                                url: item.url,
                                description: item.snippet || item.body || "No description available",
                                source: "web"
                            };
                        });
                    }
                } catch (e) {
                    console.error("Parse error", e);
                }
            }
            setSearchResults(results);
        } catch (e) {
            console.error("Search failed", e);
        } finally {
            setIsSearching(false);
        }
    };

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsAutoSearch(false);
        performSearch(searchQuery);
    };

    const clearSearch = () => {
        setSearchQuery("");
        setViewMode('sources');
        setSearchResults([]);
        setIsAutoSearch(false);
    };

    return (
        <div className="flex flex-col h-full bg-card text-foreground">

            {/* Sources View - Now with Search Bar */}
            {
                (viewMode === 'sources' || viewMode === 'search') && (
                    <>
                        {/* Search Bar / Header */}
                        <div className="px-4 pt-4 pb-2 bg-card border-b border-border/50">
                            {isAutoSearch ? (
                                <div className="flex items-center gap-2">
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={clearSearch}
                                        className="h-8 w-8 p-0 rounded-full hover:bg-muted text-muted-foreground hover:text-foreground"
                                    >
                                        <ChevronLeft className="w-4 h-4" />
                                    </Button>
                                    <span className="text-sm font-medium truncate flex-1 leading-none uppercase tracking-widest text-muted-foreground">
                                        Andrej Karpathy News
                                    </span>
                                </div>
                            ) : (
                                <form onSubmit={handleSearch} className="relative flex items-center">
                                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                                    <Input
                                        placeholder="Search Web"
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        className="w-full bg-muted border border-border rounded-lg text-xs pl-8 pr-3 py-2 focus:outline-none focus:ring-1 focus:ring-neon-yellow/50 text-foreground placeholder:text-muted-foreground transition-all h-auto"
                                    />
                                    {searchQuery && (
                                        <button
                                            type="button"
                                            onClick={clearSearch}
                                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                        >
                                            <X className="w-3.5 h-3.5" />
                                        </button>
                                    )}
                                </form>
                            )}
                        </div>

                        {/* Search Results List */}
                        {viewMode === 'search' && (
                            <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-hide">
                                {isSearching ? (
                                    <div className="flex flex-col items-center justify-center py-10 space-y-2">
                                        <Loader2 className="w-6 h-6 text-cyan-500 animate-spin" />
                                        <span className="text-xs text-muted-foreground animate-pulse">Searching Web...</span>
                                    </div>
                                ) : searchResults.length === 0 ? (
                                    <div className="text-center py-10 text-muted-foreground text-xs">
                                        No results found.
                                    </div>
                                ) : (
                                    <div className="space-y-1">
                                        {searchResults.map((item, index) => (
                                            <div
                                                key={index}
                                                className={cn(
                                                    "group p-3 rounded-lg transition-all border cursor-pointer",
                                                    activeNewsTab === item.url
                                                        ? "bg-cyan-500/10 border-cyan-500/30"
                                                        : "border-transparent hover:bg-muted/50 hover:border-border/50"
                                                )}
                                                onClick={() => openNewsTab(item.url)}
                                            >
                                                <div className="flex flex-col gap-1 w-full">
                                                    <h4 className={cn(
                                                        "text-xs font-medium line-clamp-2",
                                                        activeNewsTab === item.url ? "text-cyan-400" : "text-foreground"
                                                    )}>
                                                        {item.title}
                                                    </h4>
                                                    <div className="flex items-center justify-between">
                                                        <span className="text-[10px] text-muted-foreground/60 font-mono truncate max-w-[150px]">
                                                            {new URL(item.url).hostname.replace('www.', '')}
                                                        </span>
                                                        <button
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                if (!isArticleSaved(item.url)) {
                                                                    saveArticle(item.title, item.url);
                                                                }
                                                            }}
                                                            className={cn(
                                                                "p-1 rounded-md transition-all shrink-0",
                                                                isArticleSaved(item.url)
                                                                    ? "text-amber-400"
                                                                    : "text-muted-foreground/40 opacity-0 group-hover:opacity-100 hover:text-amber-400 hover:bg-amber-500/10"
                                                            )}
                                                            title={isArticleSaved(item.url) ? "Saved" : "Save article"}
                                                        >
                                                            {isArticleSaved(item.url) ? (
                                                                <BookmarkCheck className="w-3 h-3" />
                                                            ) : (
                                                                <Bookmark className="w-3 h-3" />
                                                            )}
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Sources List */}
                        {viewMode === 'sources' && (
                            <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-hide">
                                <div className="h-4" />
                                <p className="text-[10px] font-bold text-muted-foreground px-1 uppercase tracking-widest">Available Sources</p>

                                {/* Global Feed */}
                                {/* Global Feed */}
                                <div
                                    onClick={() => handleSelectSource(null)}
                                    className={cn(
                                        "group relative p-4 rounded-xl border transition-all duration-300 cursor-pointer mb-2",
                                        "bg-gradient-to-br from-card to-muted/20 hover:shadow-md",
                                        selectedNewsSourceId === null
                                            ? "border-neon-yellow/40 hover:border-neon-yellow/60 bg-neon-yellow/5"
                                            : "border-border/50 hover:border-primary/50 hover:bg-accent/50"
                                    )}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className={cn(
                                            "p-2 rounded-lg transition-colors",
                                            selectedNewsSourceId === null ? "bg-neon-yellow/20 text-neon-yellow" : "bg-muted text-muted-foreground group-hover:text-foreground"
                                        )}>
                                            <Globe className="w-4 h-4" />
                                        </div>
                                        <span className={cn(
                                            "text-sm font-medium transition-colors",
                                            selectedNewsSourceId === null ? "text-neon-yellow" : "text-foreground group-hover:text-foreground/80"
                                        )}>AI Feed</span>
                                    </div>
                                </div>

                                {newsSources.map((source) => (
                                    <div
                                        key={source.id}
                                        onClick={() => handleSelectSource(source.id)}
                                        className={cn(
                                            "group relative p-4 rounded-xl border transition-all duration-300 cursor-pointer",
                                            "bg-gradient-to-br from-card to-muted/20 hover:shadow-md",
                                            selectedNewsSourceId === source.id
                                                ? "border-neon-yellow/40 hover:border-neon-yellow/60 bg-neon-yellow/5"
                                                : "border-border/50 hover:border-primary/50 hover:bg-accent/50"
                                        )}
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className={cn(
                                                    "p-2 rounded-lg transition-colors",
                                                    selectedNewsSourceId === source.id ? "bg-neon-yellow/20 text-neon-yellow" : "bg-muted text-muted-foreground group-hover:text-foreground"
                                                )}>
                                                    {source.type === 'rss' ? (
                                                        <Rss className="w-4 h-4" />
                                                    ) : (
                                                        <Globe className="w-4 h-4" />
                                                    )}
                                                </div>
                                                <div className="flex flex-col min-w-0">
                                                    <span className={cn(
                                                        "text-sm font-medium truncate transition-colors",
                                                        selectedNewsSourceId === source.id ? "text-neon-yellow" : "text-foreground group-hover:text-foreground/80"
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

                                {/* Saved Articles Section - REORDERED: Now after sources */}
                                {savedArticles.length > 0 && (
                                    <div
                                        onClick={() => setViewMode('saved')}
                                        className="group p-3 mt-4 mb-2 rounded-xl border border-amber-500/30 bg-amber-500/5 hover:bg-amber-500/10 transition-all cursor-pointer flex items-center justify-between"
                                    >
                                        <div className="flex items-center gap-3">
                                            <div className="p-1.5 rounded-lg bg-amber-500/20">
                                                <Bookmark className="w-4 h-4 text-amber-400" />
                                            </div>
                                            <div>
                                                <span className="text-sm font-medium text-amber-400">Saved Articles</span>
                                                <p className="text-[10px] text-muted-foreground">{savedArticles.length} items</p>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Add Source - MOVED TO BOTTOM of the list */}
                                <div className="pt-4 pb-2">
                                    <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
                                        <DialogTrigger asChild>
                                            <Button className="w-full gap-2 bg-muted/50 hover:bg-cyan-500/10 text-muted-foreground hover:text-cyan-400 border border-dashed border-border hover:border-cyan-500/50 shadow-none">
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
                            </div>
                        )}
                    </>
                )
            }

            {/* Articles View */}
            {
                viewMode === 'articles' && (
                    <div className="flex flex-col h-full bg-card">
                        {/* Header with Back Button - Matches Search Style */}
                        <div className="px-4 pt-4 pb-2 bg-card border-b border-border/50 flex items-center gap-2">
                            <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setViewMode('sources')}
                                className="h-8 w-8 p-0 rounded-full hover:bg-muted text-muted-foreground hover:text-foreground"
                            >
                                <ChevronLeft className="w-4 h-4" />
                            </Button>
                            <span className="text-sm font-medium truncate flex-1 leading-none">
                                {selectedSource ? selectedSource.name : (newsItems.length > 0 ? new URL(newsItems[0].url).hostname.replace('www.', '') : 'Articles')}
                            </span>
                        </div>

                        <div className="flex-1 overflow-y-auto scrollbar-hide p-4 space-y-3">
                            {isNewsLoading && newsItems.length === 0 ? (
                                <div className="flex items-center justify-center py-10">
                                    <Loader2 className="w-6 h-6 text-neon-yellow animate-spin" />
                                </div>
                            ) : newsItems.length === 0 ? (
                                <div className="py-10 text-center text-muted-foreground text-sm opacity-60">
                                    No articles available
                                </div>
                            ) : (
                                newsItems.map((item, index) => {
                                    const isActive = activeNewsTab === item.url;
                                    const isSaved = isArticleSaved(item.url);

                                    return (
                                        <div
                                            key={item.id}
                                            className={cn(
                                                "group relative p-4 rounded-xl border transition-all duration-300 cursor-pointer",
                                                "bg-gradient-to-br from-card to-muted/20",
                                                "hover:shadow-md",
                                                isActive
                                                    ? "border-neon-yellow/40 hover:border-neon-yellow/60 bg-neon-yellow/5"
                                                    : "border-border/50 hover:border-primary/50 hover:bg-accent/50"
                                            )}
                                            onClick={() => openNewsTab(item.url)}
                                        >
                                            <div className="flex justify-between items-start gap-3">
                                                <div className="flex-1 min-w-0">
                                                    <h4 className={cn(
                                                        "text-[13px] font-medium leading-relaxed transition-colors line-clamp-2",
                                                        isActive ? "text-neon-yellow" : "text-foreground group-hover:text-foreground/80"
                                                    )}>
                                                        {item.title}
                                                    </h4>
                                                    <div className="flex items-center gap-2 mt-1.5">
                                                        <span className="text-[10px] font-mono text-muted-foreground/50">
                                                            {(index + 1).toString().padStart(2, '0')}
                                                        </span>
                                                        {(item.published_at || item.snippet) && (
                                                            <span className="text-[10px] text-muted-foreground/40 font-mono truncate max-w-[150px]">
                                                                {item.published_at ? new Date(item.published_at).toLocaleDateString() : (item.snippet ? item.snippet.slice(0, 30) + '...' : '')}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>

                                                <div className="flex flex-col gap-1 -mr-1">
                                                    {/* Bookmark Button */}
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            saveArticle(item.title, item.url);
                                                        }}
                                                        className={cn(
                                                            "p-1.5 rounded-lg transition-all duration-200",
                                                            isSaved
                                                                ? "text-amber-400 bg-amber-400/10 opacity-100"
                                                                : "text-muted-foreground hover:text-amber-400 hover:bg-amber-400/10 opacity-0 group-hover:opacity-100"
                                                        )}
                                                        title={isSaved ? "Saved" : "Save for later"}
                                                    >
                                                        {isSaved ? <BookmarkCheck className="w-3.5 h-3.5" /> : <Bookmark className="w-3.5 h-3.5" />}
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </div>
                    </div>
                )
            }

            {/* Saved Articles View */}
            {
                viewMode === 'saved' && (
                    <div className="flex-1 overflow-y-auto scrollbar-hide">
                        {savedArticles.length === 0 ? (
                            <div className="py-10 text-center text-muted-foreground text-sm">
                                No saved articles
                            </div>
                        ) : (
                            <div className="p-2 space-y-1">
                                {savedArticles.map((item, index) => (
                                    <div
                                        key={item.id}
                                        className="group p-3 rounded-lg border border-transparent hover:bg-muted/50 hover:border-border/50 transition-all cursor-pointer"
                                    >
                                        <div className="flex items-start gap-2">
                                            <div
                                                className="flex-1 min-w-0"
                                                onClick={() => openNewsTab(item.url)}
                                            >
                                                <h4 className={cn(
                                                    "text-xs font-medium line-clamp-2 leading-relaxed",
                                                    activeNewsTab === item.url ? "text-cyan-400" : "text-foreground"
                                                )}>
                                                    {item.title}
                                                </h4>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <span className="text-[10px] text-muted-foreground/60 font-mono">
                                                        {new URL(item.url).hostname.replace('www.', '')}
                                                    </span>
                                                </div>
                                            </div>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    deleteSavedArticle(item.id);
                                                }}
                                                className="p-1.5 hover:bg-red-500/10 rounded-md text-muted-foreground/40 hover:text-red-400 transition-all opacity-0 group-hover:opacity-100"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )
            }
        </div >
    );
};
