import React, { useEffect, useState } from 'react';
import { FileText, File, Folder, CheckCircle, AlertCircle, RefreshCw, ChevronRight, ChevronDown, FolderPlus, UploadCloud, GripHorizontal } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

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
}> = ({ item, level, onSelect, selectedPath }) => {
    const [isOpen, setIsOpen] = useState(false);
    const isFolder = item.type === 'folder';

    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (isFolder) {
            setIsOpen(!isOpen);
            onSelect(item); // Allow selecting folders too
        } else {
            onSelect(item);
        }
    };

    const getIcon = () => {
        if (isFolder) return isOpen ? <ChevronDown className="w-4 h-4 text-yellow-500" /> : <ChevronRight className="w-4 h-4 text-yellow-500" />;
        switch (item.type) {
            case 'pdf': return <FileText className="w-4 h-4 text-red-400" />;
            case 'doc':
            case 'docx': return <FileText className="w-4 h-4 text-blue-400" />;
            case 'txt':
            case 'md': return <FileText className="w-4 h-4 text-gray-400" />;
            case 'png':
            case 'jpg':
            case 'jpeg': return <File className="w-4 h-4 text-purple-400" />;
            default: return <File className="w-4 h-4 text-muted-foreground" />;
        }
    };

    return (
        <div>
            <div
                className={cn(
                    "flex items-center gap-1.5 py-1.5 px-2 rounded cursor-pointer select-none transition-colors",
                    selectedPath === item.path ? "bg-primary/20 text-white" : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
                    level > 0 && "ml-3"
                )}
                style={{ paddingLeft: `${level * 12 + 8}px` }}
                onClick={handleClick}
            >
                {getIcon()}
                <span className="truncate text-sm">{item.name}</span>
                {!isFolder && (
                    item.indexed ? (
                        <CheckCircle className="w-3 h-3 text-green-500 ml-auto" />
                    ) : (
                        <div className="w-2 h-2 rounded-full bg-yellow-500/50 ml-auto" />
                    )
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
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

export const RagPanel: React.FC = () => {
    const [files, setFiles] = useState<RagItem[]>([]);
    const [selectedFile, setSelectedFile] = useState<RagItem | null>(null);
    const [loading, setLoading] = useState(false);
    const [splitRatio, setSplitRatio] = useState(60);

    // New Folder State
    const [isNewFolderOpen, setIsNewFolderOpen] = useState(false);
    const [newFolderName, setNewFolderName] = useState("");

    // Upload State
    const fileInputRef = React.useRef<HTMLInputElement>(null);

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

    useEffect(() => {
        fetchFiles();
    }, []);

    const handleCreateFolder = async () => {
        if (!newFolderName.trim()) return;

        let path = newFolderName;
        if (selectedFile?.type === 'folder') {
            path = `${selectedFile.path}/${newFolderName}`;
        }

        try {
            await axios.post(`${API_BASE}/rag/create_folder`, null, {
                params: { folder_path: path }
            });
            setIsNewFolderOpen(false);
            setNewFolderName("");
            fetchFiles();
        } catch (e) {
            alert("Failed to create folder");
        }
    };

    const handleUploadClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            const formData = new FormData();
            formData.append("file", file);

            if (selectedFile?.type === 'folder') {
                formData.append("path", selectedFile.path);
            }

            try {
                await axios.post(`${API_BASE}/rag/upload`, formData, {
                    headers: { "Content-Type": "multipart/form-data" }
                });
                fetchFiles();
            } catch (error) {
                alert("Failed to upload file");
            }
        }
    };

    // Drag Logic
    const startResizing = (mouseDownEvent: React.MouseEvent) => {
        const startY = mouseDownEvent.clientY;
        const startHeight = splitRatio;

        const onMouseMove = (mouseMoveEvent: MouseEvent) => {
            const containerHeight = document.getElementById('rag-panel-container')?.offsetHeight || 500;
            const deltaY = mouseMoveEvent.clientY - startY;
            const deltaPercent = (deltaY / containerHeight) * 100;
            const newHeight = Math.min(Math.max(startHeight + deltaPercent, 20), 80);
            setSplitRatio(newHeight);
        };

        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            document.body.style.cursor = 'default';
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
        document.body.style.cursor = 'row-resize';
    };

    return (
        <div id="rag-panel-container" className="flex flex-col h-full bg-charcoal-900 border-r border-border">
            {/* Top Panel: File Tree */}
            <div style={{ height: `${splitRatio}%` }} className="flex flex-col min-h-0">
                <div className="p-3 border-b border-border flex justify-between items-center bg-charcoal-900/50 shrink-0">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                        <Folder className="w-3 h-3" />
                        Documents
                    </h3>
                    <div className="flex items-center gap-1">
                        <Dialog open={isNewFolderOpen} onOpenChange={setIsNewFolderOpen}>
                            <DialogTrigger asChild>
                                <button className="p-1 text-muted-foreground hover:text-primary transition-colors" title="New Folder">
                                    <FolderPlus className="w-3.5 h-3.5" />
                                </button>
                            </DialogTrigger>
                            <DialogContent className="bg-charcoal-900 border-border sm:max-w-xs">
                                <DialogHeader>
                                    <DialogTitle className="text-white text-sm">New Folder</DialogTitle>
                                </DialogHeader>
                                <div className="py-2">
                                    <Input
                                        placeholder="Folder Name"
                                        value={newFolderName}
                                        onChange={(e) => setNewFolderName(e.target.value)}
                                        className="bg-charcoal-800 border-gray-600 text-white h-8 text-xs"
                                    />
                                    {selectedFile?.type === 'folder' && (
                                        <p className="text-[10px] text-muted-foreground mt-1">Inside: {selectedFile.name}</p>
                                    )}
                                </div>
                                <DialogFooter>
                                    <Button size="sm" onClick={handleCreateFolder} className="h-7 text-xs bg-primary text-primary-foreground">Create</Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        <button onClick={handleUploadClick} className="p-1 text-muted-foreground hover:text-primary transition-colors" title="Upload File">
                            <UploadCloud className="w-3.5 h-3.5" />
                        </button>
                        <input
                            type="file"
                            ref={fileInputRef}
                            className="hidden"
                            onChange={handleFileChange}
                        />

                        <button onClick={fetchFiles} className="p-1 text-muted-foreground hover:text-primary transition-colors" title="Refresh">
                            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
                        </button>
                    </div>
                </div>
                <div className="flex-1 overflow-y-auto py-2">
                    {files.map((file) => (
                        <FileTree
                            key={file.path}
                            item={file}
                            level={0}
                            onSelect={setSelectedFile}
                            selectedPath={selectedFile?.path}
                        />
                    ))}
                    {files.length === 0 && !loading && (
                        <div className="text-center p-4 text-xs text-muted-foreground opacity-50">
                            No documents found
                        </div>
                    )}
                </div>
            </div>

            {/* Draggable Handle */}
            <div
                className="h-1.5 bg-charcoal-800 hover:bg-primary/50 cursor-row-resize flex items-center justify-center shrink-0 transition-colors"
                onMouseDown={startResizing}
            >
                <div className="w-8 h-0.5 bg-white/10 rounded-full" />
            </div>

            {/* Bottom Panel: Details */}
            <div style={{ height: `${100 - splitRatio}%` }} className="bg-charcoal-900/30 p-4 space-y-4 overflow-y-auto min-h-0">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-4">Index Status</h3>

                {selectedFile ? (
                    <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
                        <div className="space-y-1">
                            <label className="text-[10px] uppercase text-muted-foreground font-semibold">Filename</label>
                            <div className="text-sm font-mono text-white break-all">{selectedFile.name}</div>
                        </div>

                        <div className="space-y-1">
                            <label className="text-[10px] uppercase text-muted-foreground font-semibold">Status</label>
                            <div className="flex items-center gap-2">
                                {selectedFile.indexed ? (
                                    <>
                                        <CheckCircle className="w-4 h-4 text-green-500" />
                                        <span className="text-green-400 text-xs font-medium">Indexed & Ready</span>
                                    </>
                                ) : (
                                    <>
                                        <AlertCircle className="w-4 h-4 text-yellow-500" />
                                        <span className="text-yellow-400 text-xs font-medium">Pending Indexing</span>
                                    </>
                                )}
                            </div>
                        </div>

                        <div className="space-y-1">
                            <label className="text-[10px] uppercase text-muted-foreground font-semibold">Content Hash</label>
                            <div className="text-[10px] font-mono text-muted-foreground bg-black/20 p-2 rounded border border-white/5 break-all">
                                {selectedFile.hash}
                            </div>
                        </div>

                        <div className="space-y-1">
                            <label className="text-[10px] uppercase text-muted-foreground font-semibold">File Size</label>
                            <div className="text-xs text-muted-foreground">
                                {selectedFile.size ? (selectedFile.size / 1024).toFixed(2) : 0} KB
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground opacity-50 space-y-2">
                        <FileText className="w-8 h-8" />
                        <span className="text-xs">Select a file to view details</span>
                    </div>
                )}
            </div>
        </div>
    );
};
