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

    React.useEffect(() => {
        fetchNewsSources();
    }, []);

    // When a source is selected, switch to articles view
    const handleSelectSource = (sourceId: string | null) => {
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

    // Check if an article is already saved
    const isArticleSaved = (url: string) => savedArticles.some(a => a.url === url);

    // --- Search Logic ---
    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!searchQuery.trim()) return;

        setIsSearching(true);
        setViewMode('search');
        setSearchResults([]); // Clear previous

        try {
            const res = await axios.post(`${API_BASE}/mcp/call`, {
                server_name: "browser",
                tool_name: "web_search",
                arguments: { string: searchQuery, integer: 10 }
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

    const clearSearch = () => {
        setSearchQuery("");
        setViewMode('sources');
        setSearchResults([]);
    };

    return (
        <div className="flex flex-col h-full bg-card text-foreground">
            {/* Header */}
            <div className="p-4 border-b border-border flex items-center justify-between bg-card/50 backdrop-blur-md sticky top-0 z-10">
                <div className="flex items-center gap-2">
                    {(viewMode === 'articles' || viewMode === 'saved' || viewMode === 'search') && (
                        <button
                            onClick={() => viewMode === 'search' ? clearSearch() : setViewMode('sources')}
                            className="p-1 hover:bg-muted rounded-md mr-1"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                    )}
                    <div className="p-1.5 bg-cyan-500/10 rounded-lg">
                        {viewMode === 'saved' ? (
                            <Bookmark className="w-5 h-5 text-cyan-400" />
                        ) : viewMode === 'search' ? (
                            <Search className="w-5 h-5 text-cyan-400" />
                        ) : (
                            <Newspaper className="w-5 h-5 text-cyan-400" />
                        )}
                    </div>
                    <div>
                        <h2 className="font-semibold text-sm tracking-tight text-foreground uppercase">
                            {viewMode === 'saved' ? 'Saved Articles' : viewMode === 'search' ? 'Web Search' : viewMode === 'articles' && selectedSource ? selectedSource.name : 'News Sources'}
                        </h2>
                        <p className="text-[10px] text-cyan-400/80 font-mono tracking-widest">
                            {viewMode === 'saved' ? `${savedArticles.length} SAVED` : viewMode === 'search' ? `${searchResults.length} RESULTS` : viewMode === 'articles' ? `${newsItems.length} ARTICLES` : `${newsSources.length} SOURCES`}
                        </p>
                    </div>
                </div>
                <button
                    onClick={() => viewMode === 'sources' ? fetchNewsSources() : fetchNewsFeed(selectedNewsSourceId || undefined)}
                    className={cn("p-1.5 hover:bg-muted rounded-md transition-colors", isNewsLoading && "animate-spin")}
                >
                    <RefreshCw className="w-4 h-4 text-muted-foreground" />
                </button>
            </div>

            {/* Sources View - Now with Search Bar */}
            {(viewMode === 'sources' || viewMode === 'search') && (
                <>
                    {/* Search Bar */}
                    <div className="p-3 border-b border-border/50 bg-muted/20">
                        <form onSubmit={handleSearch} className="relative flex items-center">
                            <Search className="absolute left-3 w-3.5 h-3.5 text-muted-foreground" />
                            <Input
                                placeholder="Search Web"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-9 h-9 text-xs bg-card border-border/50 focus:border-cyan-500/50"
                            />
                            {searchQuery && (
                                <button
                                    type="button"
                                    onClick={clearSearch}
                                    className="absolute right-3 text-muted-foreground hover:text-foreground"
                                >
                                    <X className="w-3.5 h-3.5" />
                                </button>
                            )}
                        </form>
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
                            <div
                                onClick={() => handleSelectSource(null)}
                                className="group p-3 rounded-xl border border-border/50 hover:border-white/20 hover:bg-muted/30 transition-all cursor-pointer flex items-center justify-between text-muted-foreground hover:text-foreground"
                            >
                                <div className="flex items-center gap-3">
                                    <div className="p-1.5 rounded-lg bg-muted">
                                        <Globe className="w-4 h-4" />
                                    </div>
                                    <span className="text-sm font-medium text-black">AI Feed</span>
                                </div>
                            </div>

                            {newsSources.map((source) => (
                                <div
                                    key={source.id}
                                    onClick={() => handleSelectSource(source.id)}
                                    className="group p-3 rounded-xl border border-border/50 hover:border-white/20 hover:bg-muted/30 transition-all cursor-pointer"
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            <div className="p-1.5 rounded-lg bg-muted text-muted-foreground">
                                                {source.type === 'rss' ? (
                                                    <Rss className="w-4 h-4" />
                                                ) : (
                                                    <Globe className="w-4 h-4" />
                                                )}
                                            </div>
                                            <div className="flex flex-col min-w-0">
                                                <span className="text-sm font-medium text-foreground truncate">{source.name}</span>
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
            )}

            {/* Articles View */}
            {viewMode === 'articles' && (
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
                                    className={cn(
                                        "group p-3 rounded-lg transition-all border",
                                        activeNewsTab === item.url
                                            ? "bg-cyan-500/10 border-cyan-500/30"
                                            : "border-transparent hover:bg-muted/50 hover:border-border/50"
                                    )}
                                >
                                    <div className="flex items-start gap-2">
                                        <span className="text-[10px] font-mono text-muted-foreground/50 mt-0.5">
                                            {(index + 1).toString().padStart(2, '0')}
                                        </span>
                                        <div
                                            className="flex-1 min-w-0 cursor-pointer"
                                            onClick={() => openNewsTab(item.url)}
                                        >
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
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                if (!isArticleSaved(item.url)) {
                                                    saveArticle(item.title, item.url);
                                                }
                                            }}
                                            className={cn(
                                                "p-1.5 rounded-md transition-all shrink-0",
                                                isArticleSaved(item.url)
                                                    ? "text-amber-400"
                                                    : "text-muted-foreground/40 opacity-0 group-hover:opacity-100 hover:text-amber-400 hover:bg-amber-500/10"
                                            )}
                                            title={isArticleSaved(item.url) ? "Saved" : "Save article"}
                                        >
                                            {isArticleSaved(item.url) ? (
                                                <BookmarkCheck className="w-3.5 h-3.5" />
                                            ) : (
                                                <Bookmark className="w-3.5 h-3.5" />
                                            )}
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Saved Articles View */}
            {viewMode === 'saved' && (
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
            )}
        </div>
    );
};
