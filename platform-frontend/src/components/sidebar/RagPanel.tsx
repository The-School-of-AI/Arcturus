import React, { useEffect, useState } from 'react';
import { FileText, File, Folder, CheckCircle, AlertCircle, RefreshCw, ChevronRight, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';

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
        } else {
            onSelect(item);
        }
    };

    const getIcon = () => {
        if (isFolder) return isOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />;
        switch (item.type) {
            case 'pdf': return <FileText className="w-3 h-3 text-red-400" />;
            case 'doc':
            case 'docx': return <FileText className="w-3 h-3 text-blue-400" />;
            case 'txt':
            case 'md': return <FileText className="w-3 h-3 text-gray-400" />;
            case 'png':
            case 'jpg':
            case 'jpeg': return <File className="w-3 h-3 text-purple-400" />;
            default: return <File className="w-3 h-3 text-muted-foreground" />;
        }
    };

    return (
        <div>
            <div
                className={cn(
                    "flex items-center gap-1.5 py-1 px-2 rounded cursor-pointer select-none transition-colors",
                    selectedPath === item.path ? "bg-primary/20 text-white" : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
                    level > 0 && "ml-3"
                )}
                style={{ paddingLeft: `${level * 12 + 8}px` }}
                onClick={handleClick}
            >
                {getIcon()}
                <span className="truncate text-xs">{item.name}</span>
                {!isFolder && (
                    item.indexed ? (
                        <CheckCircle className="w-2.5 h-2.5 text-green-500 ml-auto" />
                    ) : (
                        <div className="w-1.5 h-1.5 rounded-full bg-yellow-500/50 ml-auto" />
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
    const [splitRatio, setSplitRatio] = useState(60); // Percentage height of top panel

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

    // Drag Logic
    const startResizing = (mouseDownEvent: React.MouseEvent) => {
        const startY = mouseDownEvent.clientY;
        const startHeight = splitRatio;

        const onMouseMove = (mouseMoveEvent: MouseEvent) => {
            const containerHeight = document.getElementById('rag-panel-container')?.offsetHeight || 500;
            const deltaY = mouseMoveEvent.clientY - startY;
            const deltaPercent = (deltaY / containerHeight) * 100;
            const newHeight = Math.min(Math.max(startHeight + deltaPercent, 20), 80); // Clamp between 20% and 80%
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
                    <button onClick={fetchFiles} className="text-muted-foreground hover:text-primary transition-colors">
                        <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} />
                    </button>
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
