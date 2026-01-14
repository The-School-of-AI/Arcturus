import React, { useState, useEffect, useMemo } from 'react';
import { Search, Loader2, FileCode, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';
import { Input } from "@/components/ui/input";
import { cn } from '@/lib/utils';
import axios from 'axios';
import { useAppStore } from '@/store';
import { API_BASE } from '@/lib/api';

interface SearchResult {
    file: string;
    rel_path?: string;
    line: number;
    content: string;
}

interface FileGroup {
    file: string;
    rel_path: string;
    matches: SearchResult[];
}

export const SearchSidebar: React.FC = () => {
    const { explorerRootPath, openIdeDocument } = useAppStore();
    const [query, setQuery] = useState("");
    const [results, setResults] = useState<SearchResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [debouncedQuery, setDebouncedQuery] = useState("");
    const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());

    // Debounce
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedQuery(query);
        }, 500);
        return () => clearTimeout(timer);
    }, [query]);

    // Grouping
    const groupedResults = useMemo(() => {
        const groups: { [key: string]: FileGroup } = {};
        results.forEach(res => {
            if (!groups[res.file]) {
                groups[res.file] = {
                    file: res.file,
                    rel_path: res.rel_path || res.file,
                    matches: []
                };
            }
            groups[res.file].matches.push(res);
        });
        return Object.values(groups);
    }, [results]);

    // Auto-expand all on new search
    useEffect(() => {
        if (groupedResults.length > 0) {
            setExpandedFiles(new Set(groupedResults.map(g => g.file)));
        }
    }, [groupedResults]);

    const toggleFile = (file: string) => {
        const next = new Set(expandedFiles);
        if (next.has(file)) next.delete(file);
        else next.add(file);
        setExpandedFiles(next);
    };

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
        <div className="h-full flex flex-col bg-transparent">
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

            <div className="flex-1 overflow-y-auto scrollbar-thin">
                {isSearching ? (
                    <div className="flex flex-col items-center justify-center py-8 text-muted-foreground/50 gap-2">
                        <RefreshCw className="w-5 h-5 animate-spin" />
                        <span className="text-xs">Searching...</span>
                    </div>
                ) : groupedResults.length > 0 ? (
                    <div className="space-y-0">
                        <div className="px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground border-b border-border/10">
                            {results.length} results in {groupedResults.length} files
                        </div>
                        {groupedResults.map((group) => (
                            <div key={group.file} className="border-b border-border/5">
                                <div
                                    className="flex items-center gap-1.5 px-3 py-1.5 hover:bg-white/5 cursor-pointer group select-none"
                                    onClick={() => toggleFile(group.file)}
                                >
                                    {expandedFiles.has(group.file) ? (
                                        <ChevronDown className="w-3 h-3 text-muted-foreground/50" />
                                    ) : (
                                        <ChevronRight className="w-3 h-3 text-muted-foreground/50" />
                                    )}
                                    <FileCode className="w-3.5 h-3.5 text-primary/70 shrink-0" />
                                    <span className="text-[11px] font-semibold text-foreground/90 truncate" title={group.file}>
                                        {group.rel_path.split(/[/\\]/).pop()}
                                    </span>
                                    <span className="text-[9px] text-muted-foreground/40 font-mono ml-auto">
                                        {group.matches.length}
                                    </span>
                                </div>
                                {expandedFiles.has(group.file) && (
                                    <div className="bg-black/10 dark:bg-white/5">
                                        {group.matches.map((res, i) => (
                                            <div
                                                key={`${res.file}-${res.line}-${i}`}
                                                className="group pl-9 pr-3 py-1.5 hover:bg-primary/10 cursor-pointer transition-colors border-l-2 border-transparent hover:border-primary/50"
                                                onClick={() => openIdeDocument({
                                                    id: res.file,
                                                    title: res.file.split(/[/\\]/).pop() || 'file',
                                                    type: res.file.split('.').pop() || 'txt',
                                                    targetLine: res.line,
                                                    searchText: res.content
                                                })}
                                            >
                                                <div className="text-[10px] font-mono text-muted-foreground line-clamp-2 break-all group-hover:text-foreground/80">
                                                    <span className="text-primary/70 font-bold mr-2 w-4 inline-block text-right">{res.line}</span>
                                                    {res.content.trim()}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
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
