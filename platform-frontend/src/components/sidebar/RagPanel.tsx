import React, { useEffect, useState, useMemo } from 'react';
import { FileText, File, Folder, CheckCircle, AlertCircle, RefreshCw, ChevronRight, ChevronDown, FolderPlus, UploadCloud, Zap, Search, Library, FileSearch } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useAppStore } from '@/store';

interface RagItem {
    name: string;
    path: string;
    type: string;
    size?: number;
    indexed?: boolean;
    hash?: string;
    children?: RagItem[];
}

const API_BASE = 'http://localhost:8000';

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
        setRagKeywordMatches
    } = useAppStore();
    const [files, setFiles] = useState<RagItem[]>([]);
    const [selectedFile, setSelectedFile] = useState<RagItem | null>(null);
    const [loading, setLoading] = useState(false);
    const [splitRatio, setSplitRatio] = useState(60);
    const [panelMode, setPanelMode] = useState<'browse' | 'seek'>('browse');
    const [innerSearch, setInnerSearch] = useState("");
    const [seeking, setSeeking] = useState(false);

    // New Folder State
    const [isNewFolderOpen, setIsNewFolderOpen] = useState(false);
    const [newFolderName, setNewFolderName] = useState("");

    // Indexing State
    const [indexing, setIndexing] = useState(false);
    const [indexingPath, setIndexingPath] = useState<string | null>(null);
    const [indexStatus, setIndexStatus] = useState<string | null>(null);

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

    const fetchFiles = async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${API_BASE}/rag/documents`);
            setFiles(res.data.files);
        } catch (e) {
            console.error("Failed to fetch RAG docs", e);
        } finally {
            setLoading(false);
        }
    };

    const handleSearchSubmit = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!innerSearch.trim()) return;

        if (panelMode === 'seek') {
            setSeeking(true);
            try {
                const res = await axios.get(`${API_BASE}/rag/search`, { params: { query: innerSearch } });
                setRagSearchResults(res.data.results || []);
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

        setIndexStatus(path ? `Indexing...` : "Re-scanning all...");

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
        <div id="rag-panel-container" className="flex flex-col h-full bg-card border-r border-border">
            {/* Header: Search & Toggle */}
            <div className="p-3 border-b border-border space-y-3 bg-card/80 backdrop-blur-md shrink-0">
                <div className="flex items-center gap-2 bg-muted/50 p-1 rounded-lg border border-border/50">
                    <button
                        onClick={() => setPanelMode('browse')}
                        className={cn(
                            "flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all",
                            panelMode === 'browse' ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                        )}
                    >
                        <Library className="w-3 h-3" />
                        Browse
                    </button>
                    <button
                        onClick={() => setPanelMode('seek')}
                        className={cn(
                            "flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all",
                            panelMode === 'seek' ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                        )}
                    >
                        <FileSearch className="w-3 h-3" />
                        Seek
                    </button>
                </div>

                <div className="flex items-center justify-between">
                    <form onSubmit={handleSearchSubmit} className="relative flex-1">
                        <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-muted-foreground" />
                        <Input
                            className="bg-background/50 border-input pl-9 h-9 text-xs text-foreground"
                            placeholder={panelMode === 'browse' ? "Filter library..." : "Ask your documents..."}
                            value={innerSearch}
                            onChange={(e) => setInnerSearch(e.target.value)}
                        />
                    </form>

                    <div className="flex items-center gap-1 pl-2">
                        <Dialog open={isNewFolderOpen} onOpenChange={setIsNewFolderOpen}>
                            <DialogTrigger asChild>
                                <button className="p-1.5 hover:bg-muted/50 rounded-md hover:text-primary transition-all text-muted-foreground" title="New Folder">
                                    <FolderPlus className="w-3.5 h-3.5" />
                                </button>
                            </DialogTrigger>
                            <DialogContent className="bg-card border-border sm:max-w-xs text-foreground">
                                <DialogHeader><DialogTitle className="text-foreground text-sm">New Folder</DialogTitle></DialogHeader>
                                <Input placeholder="Folder Name" value={newFolderName} onChange={(e) => setNewFolderName(e.target.value)} className="bg-muted border-input text-foreground h-8 text-xs my-2" />
                                <DialogFooter><Button size="sm" onClick={handleCreateFolder}>Create</Button></DialogFooter>
                            </DialogContent>
                        </Dialog>

                        <button onClick={() => fileInputRef.current?.click()} className="p-1.5 hover:bg-muted/50 rounded-md hover:text-primary transition-all text-muted-foreground" title="Upload File">
                            <UploadCloud className="w-3.5 h-3.5" />
                        </button>
                        <input type="file" ref={fileInputRef} className="hidden" onChange={handleFileChange} />

                        <button onClick={() => handleReindex()} className={cn("p-1.5 hover:bg-muted/50 rounded-md transition-all text-muted-foreground hover:text-yellow-400", indexing && "animate-pulse")} title="Index All">
                            <Zap className="w-3.5 h-3.5" />
                        </button>

                        <button onClick={fetchFiles} className="p-1.5 hover:bg-muted/50 rounded-md hover:text-primary transition-all text-muted-foreground" title="Refresh Library">
                            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
                        </button>
                    </div>
                </div>
            </div>

            {/* Main Content Area */}
            <div style={{ height: `${splitRatio}%` }} className="flex flex-col min-h-0 overflow-hidden">
                {panelMode === 'browse' ? (
                    <div className="flex-1 overflow-y-auto py-2 custom-scrollbar">
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
                            <div className="flex flex-col items-center justify-center py-12 px-4 text-center space-y-3 opacity-30">
                                <Library className="w-10 h-10" />
                                <p className="text-xs font-medium">Library is empty.<br />Upload files to get started.</p>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="flex-1 overflow-y-auto p-3 space-y-4 custom-scrollbar">
                        {seeking && (
                            <div className="flex items-center justify-center py-8 opacity-50">
                                <RefreshCw className="w-6 h-6 animate-spin text-primary" />
                            </div>
                        )}
                        {!seeking && Array.isArray(ragSearchResults) && ragSearchResults.map((res, i) => {
                            const { path, content, name } = parseResult(res);
                            return (
                                <div
                                    key={i}
                                    className="p-3 rounded-lg bg-muted/50 border border-border/50 hover:border-primary/30 transition-all cursor-pointer group"
                                    onClick={() => path && openDocument({ id: path, title: name, type: path.split('.').pop() || 'txt' })}
                                >
                                    <div className="flex items-center gap-2 mb-2">
                                        <FileText className="w-3 h-3 text-red-400" />
                                        <span className="text-[10px] font-bold text-muted-foreground truncate max-w-[150px]">{name}</span>
                                    </div>
                                    <p className="text-xs text-foreground/80 leading-relaxed line-clamp-4 italic">"{content}"</p>
                                    <div className="mt-2 flex justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                                        <span className="text-[10px] text-primary flex items-center gap-1 font-semibold">View Source <ChevronRight className="w-2.5 h-2.5" /></span>
                                    </div>
                                </div>
                            );
                        })}
                        {!seeking && innerSearch && ragSearchResults.length === 0 && (
                            <div className="text-center py-8 text-xs text-muted-foreground opacity-50">No semantic matches found</div>
                        )}
                    </div>
                )}
            </div>

            {/* Draggable Handle */}
            <div
                className="h-1 bg-muted hover:bg-primary/50 cursor-row-resize flex items-center justify-center shrink-0 transition-colors"
                onMouseDown={(e) => {
                    const startY = e.clientY;
                    const startHeight = splitRatio;
                    const onMove = (me: MouseEvent) => {
                        const delta = ((me.clientY - startY) / (document.getElementById('rag-panel-container')?.offsetHeight || 1)) * 100;
                        setSplitRatio(Math.min(Math.max(startHeight + delta, 20), 85));
                    };
                    const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
                    document.addEventListener('mousemove', onMove);
                    document.addEventListener('mouseup', onUp);
                }}
            >
                <div className="w-6 h-0.5 bg-muted rounded-full" />
            </div>

            {/* Footer Area: Info & Actions */}
            <div className="flex-1 bg-card/50 p-3 overflow-y-auto space-y-4 min-h-0 custom-scrollbar">
                <div className="flex items-center justify-between border-b border-border/50 pb-2">
                    <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Context Details</h4>
                </div>

                {selectedFile ? (
                    <div className="space-y-3">
                        <div className="space-y-1">
                            <label className="text-[9px] uppercase text-muted-foreground font-bold">Location</label>
                            <div className="text-xs font-mono text-primary truncate" title={selectedFile.path}>{selectedFile.path}</div>
                        </div>
                        {selectedFile.type !== 'folder' && (
                            <div className="flex items-center justify-between bg-muted/20 p-2 rounded border border-border/50">
                                <span className="text-[10px] font-bold uppercase text-muted-foreground">Status</span>
                                {selectedFile.indexed ? (
                                    <div className="flex items-center gap-1.5 text-green-500 font-bold text-[10px]"><CheckCircle className="w-3 h-3" /> INDEXED</div>
                                ) : (
                                    <button onClick={() => handleReindex(selectedFile.path)} className="text-[9px] font-bold text-yellow-500 flex items-center gap-1 hover:underline"><AlertCircle className="w-3 h-3" /> INDEX NOW</button>
                                )}
                            </div>
                        )}
                        {indexStatus && <div className="text-[9px] p-1.5 bg-yellow-500/10 text-yellow-400 rounded border border-yellow-500/20 animate-pulse">{indexStatus}</div>}

                        <Button
                            variant="outline"
                            size="sm"
                            className="w-full border-primary/30 text-primary hover:bg-primary/10 h-7 text-[10px] mt-2 gap-2"
                            onClick={() => handleReindex()}
                            disabled={indexing}
                        >
                            <RefreshCw className={cn("w-3 h-3", indexing && "animate-spin")} />
                            {indexing ? "SCANNING..." : "REFRESH INDEX"}
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-4">
                        <div className="h-20 flex flex-col items-center justify-center text-muted-foreground/30 italic text-[10px] border border-dashed border-border/50 rounded-lg text-center px-4">
                            Select a document to manage its indexing state
                        </div>

                        {!allFilesIndexed ? (
                            <div className="p-4 rounded-xl bg-neon-yellow/5 border border-neon-yellow/10 flex flex-col items-center gap-3 text-center">
                                <div className="p-3 bg-neon-yellow/10 rounded-full text-neon-yellow">
                                    <Zap className={cn("w-6 h-6", indexing && "animate-pulse")} />
                                </div>
                                <div className="space-y-1">
                                    <h5 className="text-xs font-bold text-neon-yellow uppercase">Unindexed Content Found</h5>
                                    <p className="text-[10px] text-muted-foreground leading-tight">
                                        New documents were detected that haven't been processed yet.
                                    </p>
                                </div>
                                <Button
                                    onClick={() => handleReindex()}
                                    disabled={indexing}
                                    className="w-full bg-neon-yellow text-neutral-950 hover:bg-neon-yellow/90 font-bold h-9 gap-2 shadow-lg shadow-neon-yellow/20"
                                >
                                    {indexing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
                                    {indexing ? "SCANNING DOCUMENTS..." : "START BACKGROUND SCAN"}
                                </Button>
                            </div>
                        ) : (
                            <div className="p-4 rounded-xl bg-green-500/5 border border-green-500/10 flex flex-col items-center gap-3 text-center opacity-80 transition-all hover:opacity-100">
                                <div className="p-3 bg-green-500/10 rounded-full text-green-500">
                                    <CheckCircle className="w-6 h-6" />
                                </div>
                                <div className="space-y-1">
                                    <h5 className="text-xs font-bold text-green-500/80 uppercase tracking-widest">System Synced</h5>
                                    <p className="text-[10px] text-muted-foreground leading-tight px-2">
                                        All your documents are currently indexed and ready for retrieval.
                                    </p>
                                </div>
                                <Button
                                    onClick={() => handleReindex()}
                                    disabled={indexing}
                                    variant="outline"
                                    className="w-full border-green-500/20 text-green-500/80 hover:bg-green-500/10 hover:text-green-500 h-8 text-[10px] gap-2"
                                >
                                    <RefreshCw className={cn("w-3 h-3", indexing && "animate-spin")} />
                                    {indexing ? "RE-SCANNING..." : "FORCE RE-SCAN"}
                                </Button>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
