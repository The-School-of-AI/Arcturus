import React, { useState, useEffect } from 'react';
import { Search, Loader2, FileCode, RefreshCw } from 'lucide-react';
import { Input } from "@/components/ui/input";
import { cn } from '@/lib/utils';
import axios from 'axios';
import { useAppStore } from '@/store';
import { API_BASE } from '@/lib/api';

interface SearchResult {
    file: string;
    rel_path?: string; // Optional relative path for display
    line: number;
    content: string;
}

export const SearchSidebar: React.FC = () => {
    const { explorerRootPath, openDocument } = useAppStore();
    const [query, setQuery] = useState("");
    const [results, setResults] = useState<SearchResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [debouncedQuery, setDebouncedQuery] = useState("");

    // Debounce
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedQuery(query);
        }, 500);
        return () => clearTimeout(timer);
    }, [query]);

    // Search Effect
    useEffect(() => {
        if (!debouncedQuery.trim() || !explorerRootPath) {
            setResults([]);
            setIsSearching(false);
            return;
        }

        const performSearch = async () => {
            setIsSearching(true);
            try {
                // Use the backend's ripgrep endpoint
                const res = await axios.get(`${API_BASE}/rag/ripgrep_search`, {
                    params: {
                        query: debouncedQuery,
                        target_dir: explorerRootPath
                    }
                });

                if (res.data && res.data.results) {
                    setResults(res.data.results);
                } else {
                    setResults([]);
                }
            } catch (e) {
                console.error("Search failed", e);
                setResults([]);
            } finally {
                setIsSearching(false);
            }
        };

        performSearch();
    }, [debouncedQuery, explorerRootPath]);

    if (!explorerRootPath) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground/50 p-4 text-center">
                <Search className="w-8 h-8 mb-2 opacity-50" />
                <span className="text-xs">Open a workspace to search</span>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-background">
            <div className="p-3 border-b border-border/50 bg-muted/20">
                <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                    <Input
                        className="w-full bg-muted border border-border rounded-lg text-xs pl-8 pr-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary/50 text-foreground placeholder:text-muted-foreground transition-all h-auto"
                        placeholder="Search files..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        autoFocus
                    />
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
                {isSearching ? (
                    <div className="flex flex-col items-center justify-center py-8 text-muted-foreground/50 gap-2">
                        <RefreshCw className="w-5 h-5 animate-spin" />
                        <span className="text-xs">Searching...</span>
                    </div>
                ) : results.length > 0 ? (
                    <div className="space-y-1">
                        <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                            {results.length} results
                        </div>
                        {results.map((res, i) => (
                            <div
                                key={`${res.file}-${res.line}-${i}`}
                                className="group p-2 rounded-md hover:bg-accent/50 cursor-pointer border border-transparent hover:border-border/50 transition-all"
                                onClick={() => openDocument({
                                    id: res.file,
                                    title: res.file.split(/[/\\]/).pop() || 'file',
                                    type: res.file.split('.').pop() || 'txt',
                                    targetLine: res.line,
                                    searchText: res.content
                                })}
                            >
                                <div className="flex items-center gap-1.5 mb-0.5 max-w-full">
                                    <FileCode className="w-3 h-3 text-blue-400 shrink-0" />
                                    <span className="text-xs font-medium text-foreground truncate" title={res.file}>
                                        {res.rel_path || res.file}
                                    </span>
                                </div>
                                <div className="pl-4 text-[10px] font-mono text-muted-foreground line-clamp-1 break-all">
                                    <span className="text-primary/70 mr-1">{res.line}:</span>
                                    {res.content.trim()}
                                </div>
                            </div>
                        ))}
                    </div>
                ) : query && (
                    <div className="flex flex-col items-center justify-center py-8 text-muted-foreground/50">
                        <span className="text-xs">No results found</span>
                    </div>
                )}
            </div>
        </div>
    );
};
