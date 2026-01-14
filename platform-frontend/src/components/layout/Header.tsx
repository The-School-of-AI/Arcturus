import React, { useEffect, useState } from 'react';
import {
    Box, Square, Circle, PlayCircle, Database, Brain, Code2,
    LayoutGrid, Newspaper, GraduationCap, Settings, Plus,
    RefreshCw, Zap, Sparkles, X, FolderPlus, UploadCloud, Search,
    Loader2, ChevronLeft, Notebook
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { api, API_BASE } from '@/lib/api';
import { ThemeToggle, useTheme } from '@/components/theme';
import { ArcturusLogo } from '@/components/common/ArcturusLogo';

const TAB_CONFIG: Record<string, { label: string; icon: any; color: string; subtitleSuffix: string }> = {
    runs: { label: 'Agent Runs', icon: PlayCircle, color: 'text-neon-yellow', subtitleSuffix: 'SESSIONS' },
    rag: { label: 'RAG Documents', icon: Database, color: 'text-neon-yellow', subtitleSuffix: 'SOURCES' },
    mcp: { label: 'MCP Servers', icon: Box, color: 'text-neon-yellow', subtitleSuffix: 'CONNECTED' },
    remme: { label: 'Memory Vault', icon: Brain, color: 'text-neon-yellow', subtitleSuffix: 'PERSISTENT FACTS' },
    explorer: { label: 'Explorer', icon: Code2, color: 'text-neon-yellow', subtitleSuffix: 'PROJECTS' },
    apps: { label: 'App Builder', icon: LayoutGrid, color: 'text-neon-yellow', subtitleSuffix: 'DASHBOARDS' },
    news: { label: 'News Feed', icon: Newspaper, color: 'text-cyan-400', subtitleSuffix: 'SOURCES' },
    learn: { label: 'Learning', icon: GraduationCap, color: 'text-neon-yellow', subtitleSuffix: 'COURSES' },
    notes: { label: 'Notes', icon: Notebook, color: 'text-blue-400', subtitleSuffix: 'NOTES' },
    settings: { label: 'Settings', icon: Settings, color: 'text-neon-yellow', subtitleSuffix: 'CONFIG' },
    ide: { label: 'IDE', icon: Code2, color: 'text-neon-cyan', subtitleSuffix: '' }
};

export const Header: React.FC = () => {
    const {
        currentRun, sidebarTab, runs, savedApps, memories,
        analysisHistory, newsSources, ragFiles, mcpServers,
        isRagIndexing, setIsRagNewFolderOpen, fetchRagFiles,
        setIsNewRunOpen, setIsMcpAddOpen, setIsRemmeAddOpen,
        setIsNewsAddOpen, isRagLoading, isNewsLoading, fetchNewsSources,
        fetchApps, fetchMemories, fetchRuns, fetchMcpServers,
        newsViewMode, setNewsViewMode, setNewsSearchQuery, setSearchResults,
        notesFiles, fetchNotesFiles, isNotesLoading,
        gitSummary, fetchGitSummary
    } = useAppStore();
    const { theme } = useTheme();

    const [ollamaStatus, setOllamaStatus] = useState<'checking' | 'online' | 'offline'>('checking');

    // Check Ollama status on mount and periodically
    useEffect(() => {
        const checkOllama = async () => {
            try {
                const response = await fetch('http://127.0.0.1:11434/api/tags', {
                    method: 'GET',
                    signal: AbortSignal.timeout(2000)
                });
                setOllamaStatus(response.ok ? 'online' : 'offline');
            } catch {
                setOllamaStatus('offline');
            }
        };

        checkOllama();
        const interval = setInterval(checkOllama, 30000);
        return () => clearInterval(interval);
    }, []);

    // Check Git Status if in IDE
    useEffect(() => {
        if (sidebarTab === 'ide') {
            fetchGitSummary();
            const interval = setInterval(fetchGitSummary, 5000); // Check every 5s
            return () => clearInterval(interval);
        }
    }, [sidebarTab, fetchGitSummary]);

    const handleStop = async () => {
        if (!currentRun) return;
        try {
            await api.stopRun(currentRun.id);
        } catch (e) {
            console.error("Failed to stop run:", e);
        }
    };

    const config = TAB_CONFIG[sidebarTab];
    const Icon = config?.icon || Box;

    const countFilesRecursively = (items: any[]): number => {
        let count = 0;
        (items || []).forEach(item => {
            if (item.type === 'folder') {
                count += countFilesRecursively(item.children || []);
            } else {
                count += 1;
            }
        });
        return count;
    };

    const getCount = () => {
        switch (sidebarTab) {
            case 'runs': return runs.length;
            case 'apps': return savedApps.length;
            case 'remme': return memories.length;
            case 'explorer': return analysisHistory.length;
            case 'news': return newsSources.length;
            case 'rag': return ragFiles.length;
            case 'mcp': return mcpServers.length;
            case 'notes': return countFilesRecursively(notesFiles);
            default: return 0;
        }
    };

    return (
        <header className={cn(
            "h-11 border-b flex items-center justify-between px-4 shrink-0 shadow-none z-50 transition-colors pt-0 drag-region", // Added drag-region
            theme === 'dark' ? "bg-[#0b1220] border-border/50" : "bg-white border-border"
        )}>
            <div className="flex items-center gap-2 pl-16"> {/* Added pl-16 to clear traffic lights */}
                {/* Brand / Logo */}
                <div className="flex items-center gap-0 text-primary font-bold text-lg tracking-tight mr-4 cursor-pointer no-drag" onClick={() => window.location.reload()}>
                    <ArcturusLogo className="w-8 h-8" />
                    <span className="hidden sm:inline">Arcturus<span className="text-foreground">Platform</span></span>
                </div>

                <div className="h-8 w-px bg-border/50" />

                {/* Dynamic Panel Header Content */}
                <div className="flex items-center gap-3 animate-in fade-in slide-in-from-left-2 duration-300">
                    {sidebarTab === 'news' && (newsViewMode === 'articles' || newsViewMode === 'saved' || newsViewMode === 'search') && (
                        <button
                            onClick={() => {
                                if (newsViewMode === 'search') {
                                    setNewsSearchQuery("");
                                    setSearchResults([]);
                                }
                                setNewsViewMode('sources');
                            }}
                            className="p-1.5 hover:bg-muted rounded-full mr-1 transition-colors no-drag"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                    )}

                    <div>
                        <h2 className="font-bold text-sm tracking-tight text-foreground uppercase leading-none">
                            {sidebarTab === 'news'
                                ? (newsViewMode === 'saved' ? 'Saved Articles' : newsViewMode === 'search' ? 'Web Search' : Array.isArray(newsSources) && newsSources.find(s => s.id === useAppStore.getState().selectedNewsSourceId)?.name || 'News Feed')
                                : (config?.label || sidebarTab)}
                        </h2>
                        {sidebarTab === 'ide' ? (
                            <p className={cn("text-[9px] font-mono tracking-widest mt-1 opacity-80 uppercase", config?.color || 'text-neon-yellow')}>
                                {!gitSummary ? (
                                    "GIT NOT FOUND"
                                ) : gitSummary.staged > 0 ? (
                                    <span className="text-green-400">{gitSummary.staged} STAGED</span>
                                ) : (gitSummary.unstaged + gitSummary.untracked) > 0 ? (
                                    <span className="text-amber-400">{gitSummary.unstaged + gitSummary.untracked} CHANGES</span>
                                ) : (
                                    <span className="text-muted-foreground">ALL COMMITTED</span>
                                )}
                            </p>
                        ) : (
                            <p className={cn("text-[9px] font-mono tracking-widest mt-1 opacity-80 uppercase", config?.color || 'text-neon-yellow')}>
                                {getCount()} {config?.subtitleSuffix}
                            </p>
                        )}
                    </div>

                    {/* Action Buttons for Specific Tabs */}
                    <div className="flex items-center gap-1 ml-4 py-1 px-2 rounded-full bg-muted/30 border border-border/50">
                        {sidebarTab === 'runs' && (
                            <button onClick={() => setIsNewRunOpen(true)} className="p-1.5 hover:bg-neon-yellow/10 rounded-full text-muted-foreground hover:text-neon-yellow transition-all no-drag" title="New Run">
                                <Plus className="w-4 h-4" />
                            </button>
                        )}

                        {sidebarTab === 'rag' && (
                            <>
                                <button onClick={() => setIsRagNewFolderOpen(true)} className="p-1.5 hover:bg-muted/50 rounded-full hover:text-neon-yellow transition-all text-muted-foreground no-drag" title="New Folder">
                                    <FolderPlus className="w-4 h-4" />
                                </button>
                                <button onClick={() => (document.getElementById('rag-upload-input') as HTMLInputElement)?.click()} className="p-1.5 hover:bg-muted/50 rounded-full hover:text-neon-yellow transition-all text-muted-foreground no-drag" title="Upload File">
                                    <UploadCloud className="w-4 h-4" />
                                </button>
                                <button onClick={() => fetchRagFiles()} className="p-1.5 hover:bg-muted/50 rounded-full hover:text-neon-yellow transition-all text-muted-foreground no-drag" title="Refresh">
                                    <RefreshCw className={cn("w-4 h-4", isRagLoading && "animate-spin")} />
                                </button>
                            </>
                        )}

                        {sidebarTab === 'mcp' && (
                            <>
                                <button onClick={() => setIsMcpAddOpen(true)} className="p-1.5 hover:bg-muted/50 rounded-full text-muted-foreground hover:text-neon-yellow transition-all no-drag" title="Add Server">
                                    <Plus className="w-4 h-4" />
                                </button>
                                <button onClick={() => fetchMcpServers()} className="p-1.5 hover:bg-muted/50 rounded-full hover:text-neon-yellow transition-all text-muted-foreground no-drag" title="Refresh">
                                    <RefreshCw className="w-4 h-4" />
                                </button>
                            </>
                        )}

                        {sidebarTab === 'remme' && (
                            <>
                                <button onClick={() => setIsRemmeAddOpen(true)} className="p-1.5 hover:bg-neon-yellow/5 rounded-full text-muted-foreground hover:text-neon-yellow transition-all no-drag" title="Manual Add">
                                    <Plus className="w-4 h-4" />
                                </button>
                                <button
                                    onClick={async () => {
                                        if (confirm('Scan recent runs for new memories?')) {
                                            try { await api.post(`${API_BASE}/remme/scan`); fetchMemories(); }
                                            catch (e) { console.error("Scan failed", e); }
                                        }
                                    }}
                                    className="p-1.5 hover:bg-neon-yellow/5 rounded-full text-muted-foreground hover:text-neon-yellow transition-all no-drag" title="Scan for Memories"
                                >
                                    <Sparkles className="w-4 h-4 animate-pulse" />
                                </button>
                            </>
                        )}

                        {sidebarTab === 'news' && (
                            <>
                                <button onClick={() => {
                                    if (newsViewMode === 'saved') {
                                        useAppStore.getState().setIsAddSavedArticleOpen(true);
                                    } else {
                                        setIsNewsAddOpen(true);
                                    }
                                }} className="p-1.5 hover:bg-muted rounded-full hover:text-cyan-400 transition-all text-muted-foreground no-drag" title={newsViewMode === 'saved' ? "Add Article" : "Add Source"}>
                                    <Plus className="w-4 h-4" />
                                </button>
                                <button onClick={() => fetchNewsSources()} className="p-1.5 hover:bg-muted rounded-full hover:text-cyan-400 transition-all text-muted-foreground no-drag" title="Refresh">
                                    <RefreshCw className={cn("w-4 h-4", isNewsLoading && "animate-spin")} />
                                </button>
                            </>
                        )}

                        {(sidebarTab === 'runs' || sidebarTab === 'apps' || sidebarTab === 'explorer' || sidebarTab === 'notes') && (
                            <button
                                onClick={() => {
                                    if (sidebarTab === 'runs') fetchRuns();
                                    if (sidebarTab === 'apps') fetchApps();
                                    if (sidebarTab === 'notes') fetchNotesFiles();
                                }}
                                className="p-1.5 hover:bg-muted/50 rounded-full hover:text-neon-yellow transition-all text-muted-foreground no-drag"
                                title="Refresh"
                            >
                                <RefreshCw className={cn("w-4 h-4", sidebarTab === 'notes' && isNotesLoading && "animate-spin")} />
                            </button>
                        )}
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-2">
                {/* Active Run Status Indicator */}
                {currentRun?.status === 'running' && (
                    <div className="flex items-center gap-2 px-3 py-1 border border-yellow-500/30 bg-yellow-500/10 rounded-full animate-in fade-in zoom-in">
                        <span className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse" />
                        <span className="text-[10px] font-bold text-yellow-500 uppercase tracking-tight">Agent Running</span>
                        <button onClick={handleStop} className="ml-1 p-0.5 hover:bg-yellow-500/20 rounded-md text-yellow-600 no-drag">
                            <X className="w-3 h-3" />
                        </button>
                    </div>
                )}

                <div className="h-6 w-px bg-border/50 mx-2" />

                {/* Ollama Status Indicator */}
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted/40 border border-border/50">
                    <Circle
                        className={cn(
                            "w-2 h-2 fill-current",
                            ollamaStatus === 'online' && "text-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]",
                            ollamaStatus === 'offline' && "text-red-500 shadow-[0_0_8px_rgba(239,68,68,0.4)]",
                            ollamaStatus === 'checking' && "text-yellow-500 animate-pulse"
                        )}
                    />
                    <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Ollama</span>
                </div>

                <div className="no-drag">
                    <ThemeToggle />
                </div>
            </div>
        </header>
    );
};
