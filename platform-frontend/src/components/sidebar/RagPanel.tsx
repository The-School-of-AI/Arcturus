import React, { useEffect, useState } from 'react';
import { FileText, File, Folder, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';

interface RagFile {
    name: string;
    path: string;
    type: string;
    size: number;
    indexed: boolean;
    hash: string;
}

const API_BASE = 'http://localhost:8000';

export const RagPanel: React.FC = () => {
    const [files, setFiles] = useState<RagFile[]>([]);
    const [selectedFile, setSelectedFile] = useState<RagFile | null>(null);
    const [loading, setLoading] = useState(false);

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

    const getFileIcon = (type: string) => {
        switch (type) {
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
        <div className="flex flex-col h-full">
            {/* Top 60%: File List */}
            <div className="h-[60%] border-b border-border flex flex-col">
                <div className="p-3 border-b border-border flex justify-between items-center bg-charcoal-900/50">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Documents</h3>
                    <button onClick={fetchFiles} className="text-muted-foreground hover:text-primary">
                        <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} />
                    </button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {files.map((file) => (
                        <div
                            key={file.path}
                            onClick={() => setSelectedFile(file)}
                            className={cn(
                                "flex items-center gap-2 p-2 rounded cursor-pointer text-sm transition-colors",
                                selectedFile?.path === file.path
                                    ? "bg-white/10 text-white"
                                    : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
                            )}
                        >
                            {getFileIcon(file.type)}
                            <span className="truncate flex-1">{file.name}</span>
                            {file.indexed ? (
                                <CheckCircle className="w-3 h-3 text-green-500" />
                            ) : (
                                <div className="w-2 h-2 rounded-full bg-yellow-500/50" />
                            )}
                        </div>
                    ))}
                    {files.length === 0 && !loading && (
                        <div className="text-center p-4 text-xs text-muted-foreground opacity-50">
                            No documents found in mcp_servers/documents
                        </div>
                    )}
                </div>
            </div>

            {/* Bottom 40%: Details */}
            <div className="h-[40%] bg-charcoal-900/50 p-4 space-y-4 overflow-y-auto">
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
                                {(selectedFile.size / 1024).toFixed(2)} KB
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
