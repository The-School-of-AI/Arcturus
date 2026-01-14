import React, { useEffect, useState, useMemo } from 'react';
import { FileText, File, Folder, CheckCircle, AlertCircle, RefreshCw, ChevronRight, ChevronDown, FolderPlus, UploadCloud, Zap, Search, Library, FileSearch, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useAppStore } from '@/store';
import { API_BASE } from '@/lib/api';
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface RagItem {
    name: string;
    path: string;
    type: string;
    size?: number;
    indexed?: boolean;
    status?: 'complete' | 'pending' | 'indexing' | 'error' | 'unindexed';
    hash?: string;
    chunk_count?: number;
    error?: string;
    children?: RagItem[];
}

const FileTree: React.FC<{
    item: RagItem;
    level: number;
    onSelect: (item: RagItem) => void;
    selectedPath: string | undefined;
    onIndexFile: (path: string) => void;
    indexingPath: string | null;
    searchFilter: string;
    ragKeywordMatches: string[];
    expandedFolders: string[];
    toggleFolder: (path: string) => void;
}> = ({ item, level, onSelect, selectedPath, onIndexFile, indexingPath, searchFilter, ragKeywordMatches, expandedFolders, toggleFolder }) => {
    const isFolder = item.type === 'folder';
    const isOpen = expandedFolders.includes(item.path);
    const isIndexingNow = indexingPath === item.path;

    // Simple recursive visibility check for search
    const isVisible = useMemo(() => {
        if (!searchFilter.trim()) return true;

        // 1. Check if name matches
        const matchesName = item.name.toLowerCase().includes(searchFilter.toLowerCase());
        if (matchesName) return true;

        // 2. Check if content matches (keyword search results)
        if (ragKeywordMatches.includes(item.path)) return true;

        // 3. Check if any children are visible
        if (item.children) {
            return item.children.some(child => {
                // If it's a child file, check name or content
                const childMatchesName = child.name.toLowerCase().includes(searchFilter.toLowerCase());
                if (childMatchesName) return true;
                if (ragKeywordMatches.includes(child.path)) return true;

                // If it's a child folder, we need deeper check? 
                // For simplicity, let's keep it one level for now or adjust logic.
                // Actually, the recursion in parent handles this if we return true here.
                return false;
            });
        }
        return false;
    }, [item, searchFilter, ragKeywordMatches]);

    if (!isVisible) return null;

    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (isFolder) {
            toggleFolder(item.path);
        }
        onSelect(item);
    };

    const handleIndexClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        onIndexFile(item.path);
    };

    const getIcon = () => {
        if (isFolder) return isOpen ? <ChevronDown className="w-4 h-4 text-yellow-500" /> : <ChevronRight className="w-4 h-4 text-yellow-500" />;
        switch (item.type) {
            case 'pdf': return <FileText className="w-4 h-4 text-red-400" />;
            case 'doc':
            case 'docx': return <FileText className="w-4 h-4 text-blue-400" />;
            case 'txt':
            case 'md': return <FileText className="w-4 h-4 text-muted-foreground" />;
            default: return <File className="w-4 h-4 text-muted-foreground" />;
        }
    };

    return (
        <div>
            <div
                className={cn(
                    "group relative flex items-center gap-1.5 py-1.5 px-3 transition-all duration-200 cursor-pointer select-none",
                    selectedPath === item.path
                        ? "bg-blue-500/10 text-blue-500 shadow-[inset_2px_0_0_0_#2b7fff]"
                        : "hover:bg-accent/30 text-muted-foreground hover:text-foreground",
                    level > 0 && "ml-3"
                )}
                style={{ paddingLeft: `${level * 12 + 8}px` }}
                onClick={handleClick}
            >
                {getIcon()}
                <span className="truncate text-sm flex-1">{item.name}</span>
                {!isFolder && (
                    <div className="flex items-center gap-2">
                        {isIndexingNow || item.status === 'indexing' ? (
                            <RefreshCw className="w-3 h-3 text-yellow-500 animate-spin" />
                        ) : item.status === 'pending' ? (
                            <div className="w-3 h-3 rounded-full bg-yellow-500/50 animate-pulse" title="Queued for indexing" />
                        ) : item.status === 'error' ? (
                            <span title={item.error || 'Indexing failed'}><AlertCircle className="w-3 h-3 text-red-500" /></span>
                        ) : item.indexed || item.status === 'complete' ? (
                            <CheckCircle className="w-3 h-3 text-green-500" />
                        ) : (
                            <button
                                onClick={handleIndexClick}
                                className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-yellow-500/20 rounded transition-all text-yellow-500"
                                title="Index Now"
                            >
                                <Zap className="w-3 h-3" />
                            </button>
                        )}
                    </div>
                )}
            </div>
            {isOpen && item.children && (
                <div>
                    {item.children.map((child) => (
                        <FileTree
                            key={child.path}
                            item={child}
                            level={level + 1}
                            onSelect={onSelect}
                            selectedPath={selectedPath}
                            onIndexFile={onIndexFile}
                            indexingPath={indexingPath}
                            searchFilter={searchFilter}
                            ragKeywordMatches={ragKeywordMatches}
                            expandedFolders={expandedFolders}
                            toggleFolder={toggleFolder}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

export const RagPanel: React.FC = () => {
    const {
        openRagDocument,
        setRagSearchResults,
        ragSearchResults,
        ragKeywordMatches,
        setRagKeywordMatches,
        ragFiles: files,
        setRagFiles: setFiles,
        isRagLoading: loading,
        fetchRagFiles: fetchFiles,
        isRagIndexing: indexing,
        setIsRagIndexing: setIndexing,
        ragIndexingPath: indexingPath,
        setRagIndexingPath: setIndexingPath,
        isRagNewFolderOpen: isNewFolderOpen,
        setIsRagNewFolderOpen: setIsNewFolderOpen,
        ragIndexingProgress,
        startRagPolling,
        stopRagPolling,
        ragIndexStatus: indexStatus,
        setRagIndexStatus: setIndexStatus,
        selectedRagFile: selectedFile,
        setSelectedRagFile: setSelectedFile,
        expandedRagFolders,
        toggleRagFolder
    } = useAppStore();

    const [splitRatio, setSplitRatio] = useState(50);
    const [panelMode, setPanelMode] = useState<'browse' | 'seek' | 'grep'>('browse');
    const [innerSearch, setInnerSearch] = useState("");
    const [seeking, setSeeking] = useState(false);
    const [grepResults, setGrepResults] = useState<any[]>([]);
    const [isRegex, setIsRegex] = useState(false);
    const [isCaseSensitive, setIsCaseSensitive] = useState(false);

    // New Folder State
    const [newFolderName, setNewFolderName] = useState("");

    // Upload State
    const fileInputRef = React.useRef<HTMLInputElement>(null);

    // Global ESC listener for deselection
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                setSelectedFile(null);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, []);

    // Debounced Keyword Search for Browse mode
    useEffect(() => {
        if (!innerSearch.trim()) {
            setRagKeywordMatches([]);
            setGrepResults([]);
            return;
        }

        const timer = setTimeout(async () => {
            if (panelMode === 'browse') {
                try {
                    const res = await axios.get(`${API_BASE}/rag/keyword_search`, { params: { query: innerSearch } });
                    setRagKeywordMatches(res.data.matches || []);
                } catch (e) {
                    console.error("Keyword search failed", e);
                }
            } else if (panelMode === 'grep') {
                setSeeking(true);
                try {
                    const res = await axios.get(`${API_BASE}/rag/ripgrep_search`, {
                        params: {
                            query: innerSearch,
                            regex: isRegex,
                            case_sensitive: isCaseSensitive
                        }
                    });
                    setGrepResults(res.data?.results || []);
                } catch (e) {
                    console.error("Grep search failed", e);
                } finally {
                    setSeeking(false);
                }
            }
        }, 400);

        return () => clearTimeout(timer);
    }, [innerSearch, panelMode, isRegex, isCaseSensitive, setRagKeywordMatches]);


    const handleSearchSubmit = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!innerSearch.trim()) return;

        if (panelMode === 'seek') {
            setSeeking(true);
            try {
                const res = await axios.get(`${API_BASE}/rag/search`, { params: { query: innerSearch } });
                const results = res.data?.results || [];
                setRagSearchResults(results);
            } catch (e) {
                console.error("RAG search failed", e);
            } finally {
                setSeeking(false);
            }
        } else if (panelMode === 'grep') {
            setSeeking(true);
            try {
                const res = await axios.get(`${API_BASE}/rag/ripgrep_search`, {
                    params: {
                        query: innerSearch,
                        regex: isRegex,
                        case_sensitive: isCaseSensitive
                    }
                });
                setGrepResults(res.data?.results || []);
            } catch (e) {
                console.error("Grep search failed", e);
            } finally {
                setSeeking(false);
            }
        }
    };

    const handleReindex = async (path: string | null = null) => {
        if (path) setIndexingPath(path);
        else setIndexing(true);

        setIndexStatus(path ? `Indexing...` : "Starting scan...");

        // Start global polling
        startRagPolling();

        try {
            const res = await axios.post(`${API_BASE}/rag/reindex`, null, {
                params: path ? { path } : {}
            });

            if (res.data.status === 'success') {
                setIndexStatus("Done!");
                fetchFiles();
                setTimeout(() => setIndexStatus(null), 2000);
            }
        } catch (e) {
            setIndexStatus("Failed");
            setTimeout(() => setIndexStatus(null), 2000);
            setIndexing(false);
            setIndexingPath(null);
        }
    };

    useEffect(() => {
        fetchFiles();
    }, []);

    const handleCreateFolder = async () => {
        if (!newFolderName.trim()) return;
        const path = selectedFile?.type === 'folder' ? `${selectedFile.path}/${newFolderName}` : newFolderName;
        try {
            await axios.post(`${API_BASE}/rag/create_folder`, null, { params: { folder_path: path } });
            setIsNewFolderOpen(false);
            setNewFolderName("");
            fetchFiles();
        } catch (e) { alert("Failed to create folder"); }
    };

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const formData = new FormData();
            formData.append("file", e.target.files[0]);
            if (selectedFile?.type === 'folder') formData.append("path", selectedFile.path);
            try {
                await axios.post(`${API_BASE}/rag/upload`, formData, { headers: { "Content-Type": "multipart/form-data" } });
                fetchFiles();
            } catch (error) { alert("Failed to upload file"); }
        }
    };

    const handleOpenDoc = (item: RagItem) => {
        if (item.type === 'folder') return;
        openRagDocument({
            id: item.path,
            title: item.name,
            type: item.type
        });
    };

    // Semantic result parser: "[Source: pdfs/file.pdf]"
    const parseResult = (text: string) => {
        const match = text.match(/\[Source:\s*(.+?)\]$/);
        if (match) {
            const path = match[1];
            const content = text.replace(match[0], "").trim();
            const name = path.split('/').pop() || path;
            return { path, content, name };
        }
        return { path: null, content: text, name: 'Unknown' };
    };

    // Recursive check for unindexed files (ignore images/media)
    const indexingStats = useMemo(() => {
        let unindexed = 0;
        let pending = 0;
        let errors = 0;
        let total = 0;

        const unindexable = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg', 'mp4', 'mov', 'wav', 'mp3'];

        const scan = (items: RagItem[]) => {
            for (const item of items) {
                if (item.path.includes('mcp_repos') || item.path.includes('faiss_index')) continue;

                if (item.type !== 'folder') {
                    if (unindexable.includes(item.type.toLowerCase())) continue;
                    total++;

                    // Use new status field
                    const status = item.status || (item.indexed ? 'complete' : 'unindexed');
                    if (status === 'pending' || status === 'indexing') {
                        pending++;
                    } else if (status === 'error') {
                        errors++;
                        unindexed++; // Errors count as needing reindex
                    } else if (status !== 'complete') {
                        unindexed++;
                    }
                }
                if (item.children) scan(item.children);
            }
        };

        scan(files);
        return {
            unindexed,
            pending,
            errors,
            total,
            allDone: total > 0 && unindexed === 0 && pending === 0,
            empty: total === 0
        };
    }, [files]);

    return (
        <div id="rag-panel-container" className="flex flex-col h-full bg-transparent text-foreground">
            {/* Header Content moved to Top Bar */}
            <input type="file" ref={fileInputRef} id="rag-upload-input" className="hidden" onChange={handleFileChange} />

            {/* Hidden Actions for programmatic trigger from Top Bar */}
            <div className="hidden">
                <Dialog open={isNewFolderOpen} onOpenChange={setIsNewFolderOpen}>
                    <DialogContent className="bg-card border-border sm:max-w-xs text-foreground">
                        <DialogHeader><DialogTitle className="text-foreground text-sm">New Folder</DialogTitle></DialogHeader>
                        <Input placeholder="Folder Name" value={newFolderName} onChange={(e) => setNewFolderName(e.target.value)} className="bg-muted border-input text-foreground h-8 text-xs my-2" />
                        <DialogFooter><Button size="sm" onClick={handleCreateFolder}>Create</Button></DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>

            {/* Header */}
            <div className="flex flex-col border-b border-border/50 bg-muted/20">
                <div className="p-2 flex items-center gap-1.5 shrink-0">
                    {/* Search */}
                    <div className="relative flex-1 group">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                        <Input
                            className="w-full bg-background/50 border-transparent focus:bg-background focus:border-border rounded-md text-xs pl-8 pr-2 h-8 transition-all placeholder:text-muted-foreground"
                            placeholder={panelMode === 'browse' ? "Search workspace..." : "Ask your context..."}
                            value={innerSearch}
                            onChange={(e) => setInnerSearch(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSearchSubmit()}
                        />
                    </div>

                    <div className="flex items-center gap-1">
                        {/* Add Actions */}
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-background/80" title="Add to Knowledge Base">
                                    <Plus className="w-4 h-4" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-40">
                                <DropdownMenuItem onClick={() => fileInputRef.current?.click()}>
                                    <UploadCloud className="w-4 h-4 mr-2" />
                                    Upload File
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => setIsNewFolderOpen(true)}>
                                    <FolderPlus className="w-4 h-4 mr-2" />
                                    New Folder
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>

                        <div className="w-px h-4 bg-border/50 mx-1" />

                        {/* Mode Toggles */}
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => setPanelMode('browse')}
                                    className={cn(
                                        "h-8 w-8 transition-all",
                                        panelMode === 'browse' ? "text-primary bg-primary/10" : "text-muted-foreground hover:text-foreground hover:bg-background/80"
                                    )}
                                >
                                    <Library className="w-4 h-4" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="bottom" className="max-w-[320px] p-4 space-y-3 z-[100] glass-panel border-primary/20">
                                <p className="font-bold text-sm text-primary flex items-center gap-2">
                                    <Library className="w-4 h-4" /> Mode 1: Browse (File-System)
                                </p>
                                <div className="space-y-2 text-xs leading-relaxed">
                                    <p>Uses <strong>Ripgrep</strong> to search raw files on disk. Best for code and markdown.</p>
                                    <div className="p-2.5 bg-primary/5 rounded border border-primary/20 text-[10px]">
                                        <p className="font-bold mb-1 underline decoration-primary/30">The indexing nuance:</p>
                                        <p>Normally Ripgrep misses binary PDFs. However, we've added a <strong>Fallback</strong>: if Ripgrep finds 0 hits, it automatically checks the indexed text-metadata.</p>
                                        <p className="mt-1.5 pt-1.5 border-t border-primary/10"><strong>Try:</strong> Searching 'anmol' might only show .md files, but 'anmol singh' triggers the fallback and reveals the PDF!</p>
                                    </div>
                                </div>
                            </TooltipContent>
                        </Tooltip>

                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => setPanelMode('seek')}
                                    className={cn(
                                        "h-8 w-8 transition-all",
                                        panelMode === 'seek' ? "text-primary bg-primary/10" : "text-muted-foreground hover:text-foreground hover:bg-background/80"
                                    )}
                                >
                                    <FileSearch className="w-4 h-4" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="bottom" className="max-w-[320px] p-4 space-y-3 z-[100] glass-panel border-blue-400/20">
                                <p className="font-bold text-sm text-blue-400 flex items-center gap-2">
                                    <FileSearch className="w-4 h-4" /> Mode 2: Seek (Hybrid RAG)
                                </p>
                                <div className="space-y-2 text-xs leading-relaxed">
                                    <p>Our smartest search. Combines <strong>BM25 Keyword</strong> matching with <strong>Semantic Vector</strong> understanding.</p>
                                    <ul className="list-disc pl-4 space-y-1 text-[11px] opacity-90">
                                        <li>Finds concepts, not just exact strings.</li>
                                        <li>Bypasses disk files to use the optimized index.</li>
                                        <li>Perfect for PDFs and deep context questions.</li>
                                    </ul>
                                </div>
                            </TooltipContent>
                        </Tooltip>

                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => setPanelMode('grep')}
                                    className={cn(
                                        "h-8 w-8 transition-all",
                                        panelMode === 'grep' ? "text-primary bg-primary/10" : "text-muted-foreground hover:text-foreground hover:bg-background/80"
                                    )}
                                >
                                    <Zap className="w-4 h-4" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="bottom" className="max-w-[320px] p-4 space-y-3 z-[100] glass-panel border-yellow-400/20">
                                <p className="font-bold text-sm text-yellow-500 flex items-center gap-2">
                                    <Zap className="w-4 h-4" /> Mode 3: Grep (Pure Match)
                                </p>
                                <p className="text-xs leading-relaxed">
                                    Raw, literal <strong>Ripgrep</strong> across the entire workspace. Returns exact line correlations and code snippets.
                                </p>
                                <p className="text-[11px] bg-yellow-500/5 p-2 rounded italic opacity-80 border border-yellow-500/10">
                                    Fastest way to find specific variables, tags, or boilerplate codes.
                                </p>
                            </TooltipContent>
                        </Tooltip>
                    </div>
                </div>

                {panelMode === 'grep' && (
                    <div className="flex items-center justify-between px-2 pb-2">
                        <div className="flex items-center gap-3">
                            <label className="flex items-center gap-1.5 cursor-pointer group">
                                <input
                                    type="checkbox"
                                    checked={isRegex}
                                    onChange={(e) => setIsRegex(e.target.checked)}
                                    className="w-3 h-3 rounded border-border bg-muted text-primary focus:ring-0 focus:ring-offset-0"
                                />
                                <span className="text-[10px] uppercase font-bold text-muted-foreground group-hover:text-foreground transition-colors">Regex</span>
                            </label>
                            <label className="flex items-center gap-1.5 cursor-pointer group">
                                <input
                                    type="checkbox"
                                    checked={isCaseSensitive}
                                    onChange={(e) => setIsCaseSensitive(e.target.checked)}
                                    className="w-3 h-3 rounded border-border bg-muted text-primary focus:ring-0 focus:ring-offset-0"
                                />
                                <span className="text-[10px] uppercase font-bold text-muted-foreground group-hover:text-foreground transition-colors">Match Case</span>
                            </label>
                        </div>
                        {grepResults.length > 0 && (
                            <span className="text-[9px] font-mono text-primary/60 bg-primary/5 px-1.5 py-0.5 rounded border border-primary/20">
                                {grepResults.length} Matches
                            </span>
                        )}
                    </div>
                )}
            </div>

            {/* Main Content Area */}
            <div style={{ height: selectedFile ? `${splitRatio}%` : '100%' }} className="flex-1 flex flex-col min-h-0 overflow-hidden">
                {panelMode === 'browse' ? (
                    <div
                        className="flex-1 overflow-y-auto py-1 custom-scrollbar"
                        onClick={() => setSelectedFile(null)}
                    >
                        {files.map((file) => (
                            <FileTree
                                key={file.path}
                                item={file}
                                level={0}
                                onSelect={(f: RagItem) => { setSelectedFile(f); handleOpenDoc(f); }}
                                selectedPath={selectedFile?.path}
                                onIndexFile={handleReindex}
                                indexingPath={indexingPath}
                                searchFilter={innerSearch}
                                ragKeywordMatches={ragKeywordMatches}
                                expandedFolders={expandedRagFolders}
                                toggleFolder={toggleRagFolder}
                            />
                        ))}
                        {files.length === 0 && !loading && (
                            <div className="flex flex-col items-center justify-center py-8 px-4 text-center space-y-2 opacity-30">
                                <Library className="w-8 h-8" />
                                <p className="text-[10px] font-medium">Empty Library</p>
                            </div>
                        )}
                    </div>
                ) : panelMode === 'seek' ? (
                    <div className="flex-1 overflow-y-auto p-2 space-y-2 custom-scrollbar">
                        {seeking && (
                            <div className="flex items-center justify-center py-6 opacity-50">
                                <RefreshCw className="w-5 h-5 animate-spin text-primary" />
                            </div>
                        )}
                        {!seeking && Array.isArray(ragSearchResults) && ragSearchResults.map((res: any, i) => {
                            const isStructured = typeof res === 'object' && res !== null;
                            const content = isStructured ? res.content : (parseResult(res)).content;
                            const source = isStructured ? res.source : (parseResult(res)).path;
                            const page = isStructured ? res.page : 1;
                            const name = source?.split('/').pop() || 'Unknown';
                            const ext = source?.split('.').pop() || 'txt';

                            return (
                                <div
                                    key={i}
                                    className={cn(
                                        "group relative p-4 rounded-xl border transition-all duration-300 cursor-pointer overflow-hidden",
                                        "hover:shadow-lg hover:border-primary/50",
                                        "border-border/50"
                                    )}
                                    onClick={() => source && openRagDocument({ id: source, title: name, type: ext, targetPage: page, searchText: content?.slice(0, 80) })}
                                >
                                    <div className="flex items-center gap-1.5 mb-1">
                                        <FileText className="w-2.5 h-2.5 text-red-400" />
                                        <span className="text-[9px] font-bold text-muted-foreground truncate flex-1">{name}</span>
                                        {page > 1 && <span className="text-[8px] font-mono opacity-50">p{page}</span>}
                                    </div>
                                    <p className="text-[11px] text-foreground/70 leading-snug line-clamp-3">"{content}"</p>
                                </div>
                            );
                        })}
                        {!seeking && innerSearch && ragSearchResults.length === 0 && (
                            <div className="text-center py-6 text-[10px] text-muted-foreground opacity-50 uppercase tracking-widest font-bold">No Matches</div>
                        )}
                    </div>
                ) : (
                    <div className="flex-1 overflow-y-auto p-2 space-y-2 custom-scrollbar">
                        {seeking && (
                            <div className="flex items-center justify-center py-6 opacity-50">
                                <RefreshCw className="w-5 h-5 animate-spin text-primary" />
                            </div>
                        )}
                        {!seeking && (Object.entries(grepResults.reduce((acc: any, res: any) => {
                            const file = res.file || 'unknown';
                            if (!acc[file]) acc[file] = [];
                            acc[file].push(res);
                            return acc;
                        }, {})) as [string, any[]][]).map(([file, matches], i) => (
                            <div
                                key={i}
                                className={cn(
                                    "group relative p-3 rounded-lg border border-border/40 hover:border-primary/40 hover:bg-primary/5 transition-all duration-200 cursor-pointer overflow-hidden bg-card/10 select-none"
                                )}
                                onClick={() => {
                                    // Open the file at the first match
                                    const first = matches[0];
                                    openRagDocument({
                                        id: first.file,
                                        title: first.file.split('/').pop() || 'file',
                                        type: first.file.split('.').pop() || 'txt',
                                        targetLine: first.line,
                                        searchText: first.content
                                    });
                                }}
                            >
                                <div className="flex items-center gap-1.5 mb-2 border-b border-border/30 pb-1.5">
                                    <File className="w-3 h-3 text-blue-400/70" />
                                    <span className="text-[10px] font-black text-muted-foreground truncate uppercase flex-1" title={file}>{file}</span>
                                    <span className="text-[9px] font-mono bg-muted px-1.5 rounded-full text-muted-foreground shrink-0 opacity-70">
                                        {matches.length} Matches
                                    </span>
                                </div>
                                <div className="space-y-1">
                                    {matches.slice(0, 5).map((m: any, idx: number) => (
                                        <div key={idx} className="flex gap-2 items-start opacity-80 hover:opacity-100">
                                            <span className="text-[9px] font-mono text-primary/60 min-w-[24px] text-right shrink-0">L{m.line}</span>
                                            <span className="text-[10px] font-mono text-foreground/80 line-clamp-1 break-all flex-1">{m.content.trim()}</span>
                                        </div>
                                    ))}
                                    {matches.length > 5 && (
                                        <div className="pl-8 text-[9px] italic opacity-50 text-muted-foreground">
                                            + {matches.length - 5} more...
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                        {!seeking && innerSearch && grepResults.length === 0 && (
                            <div className="text-center py-8 opacity-30 flex flex-col items-center gap-2">
                                <Search className="w-6 h-6" />
                                <p className="text-[9px] font-bold uppercase tracking-widest">No Pattern Matches</p>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Draggable Handle - Only show if file selected */}
            {selectedFile && (
                <div
                    className="h-1 bg-muted/30 hover:bg-primary/30 cursor-row-resize flex items-center justify-center shrink-0 transition-colors"
                    onMouseDown={(e) => {
                        const startY = e.clientY;
                        const startHeight = splitRatio;
                        const onMove = (me: MouseEvent) => {
                            const delta = ((me.clientY - startY) / (document.getElementById('rag-panel-container')?.offsetHeight || 1)) * 100;
                            setSplitRatio(Math.min(Math.max(startHeight + delta, 20), 80));
                        };
                        const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
                        document.addEventListener('mousemove', onMove);
                        document.addEventListener('mouseup', onUp);
                    }}
                >
                    <div className="w-4 h-0.5 bg-muted rounded-full" />
                </div>
            )}

            {/* Footer Area: Detailed Sync Status */}
            <div className={cn("bg-card/30 shrink-0", selectedFile ? "h-[20%] overflow-y-auto" : "p-3 border-t border-border/30")}>
                {selectedFile ? (
                    <div className="p-3 space-y-3">
                        <div className="flex items-center justify-between border-b border-border/30 pb-1.5">
                            <h4 className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">Properties</h4>
                            <button onClick={() => setSelectedFile(null)} className="text-[9px] text-muted-foreground hover:text-foreground">ESC</button>
                        </div>
                        <div className="space-y-2">
                            <div className="space-y-0.5">
                                <label className="text-[8px] uppercase text-muted-foreground/60 font-bold">Path</label>
                                <div className="text-[10px] font-mono text-primary truncate" title={selectedFile.path}>{selectedFile.path}</div>
                            </div>
                            {selectedFile.type !== 'folder' && (
                                <div className="flex items-center justify-between bg-muted/10 p-1.5 rounded border border-border/20">
                                    <span className="text-[8px] font-bold uppercase text-muted-foreground">Indexing</span>
                                    {selectedFile.indexed ? (
                                        <div className="flex items-center gap-1 text-green-500 font-bold text-[9px] uppercase"><CheckCircle className="w-2.5 h-2.5" /> Ready</div>
                                    ) : (
                                        <button onClick={() => handleReindex(selectedFile.path)} className="text-[8px] font-bold text-yellow-500 flex items-center gap-1 hover:underline"><Zap className="w-2.5 h-2.5" /> Start</button>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="px-1">
                        {indexing || ragIndexingProgress ? (
                            <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <RefreshCw className="w-3 h-3 text-neon-yellow animate-spin" />
                                        <span className="text-[9px] font-black text-neon-yellow uppercase tracking-tight">
                                            Indexing {ragIndexingProgress ? `${ragIndexingProgress.completed}/${ragIndexingProgress.total}` : ''}
                                        </span>
                                    </div>
                                    {ragIndexingProgress && (
                                        <span className="text-[9px] font-mono text-neon-yellow/60">
                                            {Math.round((ragIndexingProgress.completed / ragIndexingProgress.total) * 100)}%
                                        </span>
                                    )}
                                </div>

                                {/* Progress Bar */}
                                <div className="h-1 w-full bg-neon-yellow/10 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-neon-yellow transition-all duration-500 ease-out shadow-[0_0_8px_rgba(255,255,0,0.5)]"
                                        style={{ width: `${ragIndexingProgress ? (ragIndexingProgress.completed / ragIndexingProgress.total) * 100 : 0}%` }}
                                    />
                                </div>

                                {ragIndexingProgress?.currentFile && (
                                    <div className="flex items-center gap-1.5">
                                        <File className="w-2.5 h-2.5 text-muted-foreground" />
                                        <span className="text-[8px] text-muted-foreground truncate italic">
                                            {ragIndexingProgress.currentFile}
                                        </span>
                                    </div>
                                )}
                            </div>
                        ) : indexingStats.pending > 0 ? (
                            <div className="flex items-center justify-between gap-4">
                                <div className="flex items-center gap-2 flex-1 min-w-0">
                                    <div className="p-1 bg-yellow-500/20 rounded">
                                        <RefreshCw className="w-3 h-3 text-yellow-500 animate-spin" />
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="text-[9px] font-bold text-yellow-500 uppercase leading-tight tracking-tighter">
                                            {indexingStats.pending} FILES QUEUED FOR INDEXING
                                        </span>
                                    </div>
                                </div>
                            </div>
                        ) : !indexingStats.allDone ? (
                            <div className="flex items-center justify-between gap-4">
                                <div className="flex items-center gap-2 flex-1 min-w-0">
                                    <div className="p-1 bg-neon-yellow/10 rounded">
                                        <Zap className="w-3 h-3 text-neon-yellow" />
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="text-[9px] font-bold text-neon-yellow uppercase leading-tight tracking-tighter">
                                            {indexingStats.empty ? "FULL INDEXING REQUIRED" :
                                                indexingStats.errors > 0 ? `${indexingStats.errors} ERRORS, ${indexingStats.unindexed - indexingStats.errors} UNINDEXED` :
                                                    `${indexingStats.unindexed}/${indexingStats.total} FILES NEED INDEXING`}
                                        </span>
                                    </div>
                                    <Button
                                        size="sm"
                                        onClick={() => handleReindex()}
                                        disabled={indexing}
                                        className="h-6 px-3 bg-neon-yellow text-neutral-950 hover:bg-neon-yellow/90 text-[9px] font-black uppercase ml-auto transition-transform active:scale-95 shadow-lg shadow-neon-yellow/20"
                                    >
                                        SCAN
                                    </Button>
                                </div>
                            </div>
                        ) : (
                            <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse shadow-[0_0_5px_rgba(34,197,94,0.5)]" />
                                    <span className="text-[9px] font-bold text-muted-foreground/60 uppercase tracking-widest">Documents Synced</span>
                                </div>
                                <button
                                    onClick={() => handleReindex()}
                                    className="ml-auto text-[8px] font-bold text-muted-foreground hover:text-primary transition-colors uppercase hover:underline"
                                    disabled={indexing}
                                >
                                    Rescan
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
