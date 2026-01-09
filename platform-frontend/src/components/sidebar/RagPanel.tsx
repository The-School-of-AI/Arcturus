import React, { useEffect, useState, useMemo } from 'react';
import { FileText, File, Folder, CheckCircle, AlertCircle, RefreshCw, ChevronRight, ChevronDown, FolderPlus, UploadCloud, Zap, Search, Library, FileSearch } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useAppStore } from '@/store';
import { API_BASE } from '@/lib/api';

interface RagItem {
    name: string;
    path: string;
    type: string;
    size?: number;
    indexed?: boolean;
    hash?: string;
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
}> = ({ item, level, onSelect, selectedPath, onIndexFile, indexingPath, searchFilter, ragKeywordMatches }) => {
    const [isOpen, setIsOpen] = useState(false);
    const isFolder = item.type === 'folder';
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
            setIsOpen(!isOpen);
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
                    "group flex items-center gap-1.5 py-1.5 px-2 rounded cursor-pointer select-none transition-colors",
                    selectedPath === item.path ? "bg-primary/20 text-foreground" : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
                    level > 0 && "ml-3"
                )}
                style={{ paddingLeft: `${level * 12 + 8}px` }}
                onClick={handleClick}
            >
                {getIcon()}
                <span className="truncate text-sm flex-1">{item.name}</span>
                {!isFolder && (
                    <div className="flex items-center gap-2">
                        {isIndexingNow ? (
                            <RefreshCw className="w-3 h-3 text-yellow-500 animate-spin" />
                        ) : item.indexed ? (
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
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

export const RagPanel: React.FC = () => {
    const {
        openDocument,
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
        ragIndexStatus: indexStatus,
        setRagIndexStatus: setIndexStatus,
        isRagNewFolderOpen: isNewFolderOpen,
        setIsRagNewFolderOpen: setIsNewFolderOpen
    } = useAppStore();

    const [selectedFile, setSelectedFile] = useState<RagItem | null>(null);
    const [splitRatio, setSplitRatio] = useState(50);
    const [panelMode, setPanelMode] = useState<'browse' | 'seek'>('browse');
    const [innerSearch, setInnerSearch] = useState("");
    const [seeking, setSeeking] = useState(false);

    // New Folder State
    const [newFolderName, setNewFolderName] = useState("");

    // Upload State
    const fileInputRef = React.useRef<HTMLInputElement>(null);

    // Debounced Keyword Search for Browse mode
    useEffect(() => {
        if (panelMode !== 'browse' || !innerSearch.trim()) {
            setRagKeywordMatches([]);
            return;
        }

        const timer = setTimeout(async () => {
            try {
                const res = await axios.get(`${API_BASE}/rag/keyword_search`, { params: { query: innerSearch } });
                setRagKeywordMatches(res.data.matches || []);
            } catch (e) {
                console.error("Keyword search failed", e);
            }
        }, 300);

        return () => clearTimeout(timer);
    }, [innerSearch, panelMode, setRagKeywordMatches]);


    const handleSearchSubmit = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!innerSearch.trim()) return;

        if (panelMode === 'seek') {
            setSeeking(true);
            try {
                const res = await axios.get(`${API_BASE}/rag/search`, { params: { query: innerSearch } });
                console.log("SEEK Response:", res.data);  // DEBUG
                console.log("Results:", res.data?.results);  // DEBUG
                const results = res.data?.results || [];
                console.log("Setting ragSearchResults:", results.length);  // DEBUG
                setRagSearchResults(results);
            } catch (e) {
                console.error("RAG search failed", e);
            } finally {
                setSeeking(false);
            }
        }
    };

    const handleReindex = async (path: string | null = null) => {
        if (path) setIndexingPath(path);
        else setIndexing(true);

        setIndexStatus(path ? `Indexing...` : "Starting scan...");

        // Start polling for status
        const pollInterval = setInterval(async () => {
            try {
                const statusRes = await axios.get(`${API_BASE}/rag/indexing_status`);
                const status = statusRes.data;
                if (status.active && status.total > 0) {
                    const currentFile = status.currentFile || "...";
                    setIndexStatus(`Indexing ${status.completed}/${status.total}: ${currentFile}`);
                }
            } catch (e) {
                // Ignore polling errors
            }
        }, 2000);

        try {
            const res = await axios.post(`${API_BASE}/rag/reindex`, null, {
                params: path ? { path } : {}
            });

            clearInterval(pollInterval);

            if (res.data.status === 'success') {
                setIndexStatus("Done!");
                fetchFiles();
                setTimeout(() => setIndexStatus(null), 2000);
            }
        } catch (e) {
            clearInterval(pollInterval);
            setIndexStatus("Failed");
            setTimeout(() => setIndexStatus(null), 2000);
        } finally {
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
        openDocument({
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
    const allFilesIndexed = useMemo(() => {
        if (files.length === 0) return true;
        const unindexable = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg', 'mp4', 'mov', 'wav', 'mp3'];
        const check = (items: RagItem[]): boolean => {
            for (const item of items) {
                if (item.type !== 'folder') {
                    if (unindexable.includes(item.type.toLowerCase())) continue;
                    if (!item.indexed) return false;
                }
                if (item.children && !check(item.children)) return false;
            }
            return true;
        };
        return check(files);
    }, [files]);

    return (
        <div id="rag-panel-container" className="flex flex-col h-full bg-card text-foreground">
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

            {/* Search & Mode Toggle Merged */}
            <div className="px-4 pt-4 pb-2 bg-card border-b border-border/50 shrink-0">
                <div className="flex items-center gap-2">
                    <form onSubmit={handleSearchSubmit} className="relative flex-1">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                        <Input
                            className="w-full bg-muted border border-border rounded-lg text-xs pl-8 pr-3 py-2 focus:outline-none focus:ring-1 focus:ring-neon-yellow/50 text-foreground placeholder:text-muted-foreground transition-all h-auto"
                            placeholder={panelMode === 'browse' ? "Filter..." : "Ask..."}
                            value={innerSearch}
                            onChange={(e) => setInnerSearch(e.target.value)}
                        />
                    </form>
                    <div className="flex items-center bg-card/50 p-0.5 rounded-md border border-border/30 shrink-0">
                        <button
                            onClick={() => setPanelMode('browse')}
                            className={cn(
                                "px-2 py-1 rounded text-[9px] font-bold uppercase tracking-tight transition-all",
                                panelMode === 'browse' ? "bg-neon-yellow text-neutral-950" : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            Browse
                        </button>
                        <button
                            onClick={() => setPanelMode('seek')}
                            className={cn(
                                "px-2 py-1 rounded text-[9px] font-bold uppercase tracking-tight transition-all",
                                panelMode === 'seek' ? "bg-neon-yellow text-neutral-950" : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            Seek
                        </button>
                    </div>
                </div>
            </div>

            {/* Main Content Area */}
            <div style={{ height: selectedFile ? `${splitRatio}%` : '100%' }} className="flex-1 flex flex-col min-h-0 overflow-hidden">
                {panelMode === 'browse' ? (
                    <div className="flex-1 overflow-y-auto py-1 custom-scrollbar">
                        {files.map((file) => (
                            <FileTree
                                key={file.path}
                                item={file}
                                level={0}
                                onSelect={(f) => { setSelectedFile(f); handleOpenDoc(f); }}
                                selectedPath={selectedFile?.path}
                                onIndexFile={handleReindex}
                                indexingPath={indexingPath}
                                searchFilter={innerSearch}
                                ragKeywordMatches={ragKeywordMatches}
                            />
                        ))}
                        {files.length === 0 && !loading && (
                            <div className="flex flex-col items-center justify-center py-8 px-4 text-center space-y-2 opacity-30">
                                <Library className="w-8 h-8" />
                                <p className="text-[10px] font-medium">Empty Library</p>
                            </div>
                        )}
                    </div>
                ) : (
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
                                    className="p-2 rounded-lg bg-muted/30 border border-border/30 hover:border-primary/20 transition-all cursor-pointer group"
                                    onClick={() => source && openDocument({ id: source, title: name, type: ext, targetPage: page, searchText: content?.slice(0, 80) })}
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

            {/* Footer Area: Context or Compact Sync Info */}
            <div className={cn("bg-card/30 shrink-0", selectedFile ? "h-[30%] overflow-y-auto" : "p-2 border-t border-border/30")}>
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
                    // Minimal Status Line
                    <div className="flex items-center justify-between gap-4 px-1">
                        {!allFilesIndexed ? (
                            <div className="flex items-center gap-2 flex-1 min-w-0">
                                <div className="p-1 bg-neon-yellow/10 rounded">
                                    <Zap className={cn("w-3 h-3 text-neon-yellow", indexing && "animate-pulse")} />
                                </div>
                                <span className="text-[9px] font-bold text-neon-yellow uppercase truncate">Indexing Required</span>
                                <Button
                                    size="sm"
                                    onClick={() => handleReindex()}
                                    disabled={indexing}
                                    className="h-5 px-2 bg-neon-yellow text-neutral-950 hover:bg-neon-yellow/90 text-[8px] font-black uppercase ml-auto"
                                >
                                    {indexing ? "..." : "SCAN"}
                                </Button>
                            </div>
                        ) : (
                            <div className="flex items-center gap-2 flex-1">
                                <CheckCircle className="w-3 h-3 text-green-500/50" />
                                <span className="text-[9px] font-bold text-muted-foreground/50 uppercase tracking-widest">Documents Synced</span>
                                <button
                                    onClick={() => handleReindex()}
                                    className="ml-auto text-[8px] font-bold text-muted-foreground hover:text-primary transition-colors uppercase"
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
