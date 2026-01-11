import React, { useState, useMemo } from 'react';
import axios from 'axios';
import { useAppStore } from '@/store';
import { FileCode, Folder, ChevronRight, ChevronDown, Play, Code2, Globe, Trash2, X, Github, Plus, Search, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { FileSelectionModal } from './FileSelectionModal';
import { API_BASE } from '@/lib/api';

interface FileNode {
    name: string;
    path: string;
    type: 'file' | 'folder';
    children?: FileNode[];
}

export const ExplorerPanel: React.FC = () => {
    const {
        explorerRootPath, setExplorerRootPath,
        explorerFiles, setExplorerFiles,
        isAnalyzing, setIsAnalyzing,
        setFlowData, analysisHistory, addToHistory, removeFromHistory
    } = useAppStore();
    const [isExpanded, setIsExpanded] = useState<Record<string, boolean>>({});
    const [connectInput, setConnectInput] = useState('');
    const [scannedFiles, setScannedFiles] = useState<any[]>([]);
    const [isScanning, setIsScanning] = useState(false);
    const [showSelectionModal, setShowSelectionModal] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");

    const toggleFolder = (path: string) => {
        setIsExpanded(prev => ({ ...prev, [path]: !prev[path] }));
    };

    const renderTree = (nodes: FileNode[], depth = 0) => {
        return nodes.map(node => (
            <div key={node.path} className="select-none">
                <div
                    className={cn(
                        "group relative flex items-center py-2 px-3 rounded-lg border transition-all duration-300 cursor-pointer mb-1",
                        "border-border/30 hover:border-primary/30 hover:bg-accent/30 bg-card/30",
                        depth > 0 && "ml-2"
                    )}
                    onClick={() => node.type === 'folder' ? toggleFolder(node.path) : null}
                >
                    {node.type === 'folder' ? (
                        <>
                            {isExpanded[node.path] ? <ChevronDown className="w-3.5 h-3.5 mr-1.5 text-muted-foreground" /> : <ChevronRight className="w-3.5 h-3.5 mr-1.5 text-muted-foreground" />}
                            <Folder className="w-4 h-4 mr-2 text-neon-yellow/70" />
                        </>
                    ) : (
                        <FileCode className="w-4 h-4 mr-2 ml-5 text-blue-400/70" />
                    )}
                    <span className="text-[13px] text-muted-foreground truncate font-medium group-hover:text-foreground">{node.name}</span>
                </div>
                {node.type === 'folder' && isExpanded[node.path] && node.children && (
                    <div className="border-l border-border/50 ml-3 mt-0.5 mb-1">
                        {renderTree(node.children, depth + 1)}
                    </div>
                )}
            </div>
        ));
    };

    const filteredHistory = useMemo(() => {
        if (!searchQuery.trim()) return analysisHistory;
        return analysisHistory.filter(item =>
            item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            item.path.toLowerCase().includes(searchQuery.toLowerCase())
        );
    }, [analysisHistory, searchQuery]);

    const handleConnect = async () => {
        if (!connectInput.trim()) return;
        const isGithub = connectInput.startsWith('http');
        const path = connectInput.trim();

        try {
            setIsAnalyzing(true);
            if (isGithub) {
                const res = await axios.post(`${API_BASE}/explorer/analyze`, { path, type: 'github' });
                if (res.data.success) {
                    setFlowData(res.data.flow_data);
                    setExplorerRootPath(path);
                    addToHistory({
                        name: path.split('/').pop() || path,
                        path,
                        type: 'github',
                        flowData: res.data.flow_data
                    });
                    setExplorerFiles([]);
                }
            } else {
                const res = await axios.get(`${API_BASE}/explorer/list?path=${encodeURIComponent(path)}`);
                const { files, root_path, error } = res.data;

                if (error) {
                    alert(`Path not found: ${root_path}`);
                    return;
                }

                setExplorerFiles(files);
                setExplorerRootPath(root_path);
                addToHistory({ name: root_path.split('/').pop() || root_path, path: root_path, type: 'local' });
            }
            setConnectInput(''); // Clear after success
        } catch (err: any) {
            console.error("Connection failed:", err);
            const detail = err.response?.data?.detail || err.message;
            alert("Failed to connect: " + detail);
        } finally {
            setIsAnalyzing(false);
        }
    };

    const loadHistoryItem = async (item: any) => {
        // Toggle: if already selected, collapse by deselecting
        if (explorerRootPath === item.path) {
            setExplorerRootPath(null);
            setExplorerFiles([]);
            return;
        }

        setExplorerRootPath(item.path);
        if (item.flowData) {
            setFlowData(item.flowData);
        }

        if (item.type === 'local') {
            try {
                const res = await axios.get(`${API_BASE}/explorer/list?path=${encodeURIComponent(item.path)}`);
                const { files, root_path, error } = res.data;

                if (error) {
                    const shouldRemove = window.confirm(
                        `Path no longer exists: ${item.path}\n\nDo you want to remove it from history?`
                    );
                    if (shouldRemove) {
                        removeFromHistory(item.id);
                        setExplorerRootPath(null);
                    }
                    setExplorerFiles([]);
                    return;
                }

                setExplorerFiles(files || []);
                if (root_path && root_path !== item.path) {
                    useAppStore.getState().updateHistoryItem(item.path, { path: root_path, name: root_path.split('/').pop() || item.name });
                }
            } catch (err) {
                console.error("Failed to load local history item files:", err);
                setExplorerFiles([]);
            }
        } else if (item.type === 'github') {
            setExplorerFiles([]);
        }
    };

    const performAnalysis = async (selectedFiles: string[] | null) => {
        setIsAnalyzing(true);
        try {
            const isGithub = explorerRootPath!.startsWith('http');
            const res = await axios.post(`${API_BASE}/explorer/analyze`, {
                path: explorerRootPath,
                type: isGithub ? 'github' : 'local',
                files: selectedFiles
            });

            if (res.data.success) {
                const flow_data = res.data.flow_data;
                const root_path = res.data.root_path; // Get the absolute path
                setFlowData(flow_data);
                setExplorerRootPath(root_path);
                useAppStore.getState().updateHistoryItem(explorerRootPath || '', { flowData: flow_data, path: root_path });

                // Refresh file tree if we have a valid absolute path
                const isAbsolutePath = root_path && (root_path.startsWith('/') || root_path.includes(':\\'));
                if (isAbsolutePath && !root_path.startsWith('http')) {
                    try {
                        const filesRes = await axios.get(`${API_BASE}/explorer/list?path=${encodeURIComponent(root_path)}`);
                        if (filesRes.data.files && filesRes.data.files.length > 0) {
                            setExplorerFiles(filesRes.data.files);
                        }
                    } catch (e) {
                        console.error("Failed to refresh files after analysis", e);
                    }
                }
            }
        } catch (err: any) {
            console.error("Analysis failed:", err);
            const detail = err.response?.data?.detail || err.message;
            alert("Analysis failed: " + detail);
        } finally {
            setIsAnalyzing(false);
        }
    };

    const handleAnalyze = async () => {
        if (!explorerRootPath) return;

        // Check if this is a browser-picked folder (no absolute path)
        const isAbsolutePath = explorerRootPath.startsWith('/') || explorerRootPath.includes(':\\') || explorerRootPath.startsWith('http');
        if (!isAbsolutePath) {
            alert(
                `Cannot analyze "${explorerRootPath}".\n\n` +
                `Browser-selected folders don't provide the full path needed for analysis.\n\n` +
                `To analyze this folder, please use "Connect Repository" and enter the absolute path ` +
                `(e.g., /Users/yourname/path/to/${explorerRootPath})`
            );
            return;
        }

        // 1. SCAN PROJECT
        setIsScanning(true);
        try {
            const isGithub = explorerRootPath.startsWith('http');
            if (isGithub) {
                // For GitHub, we still do the old immediate analysis for now (or implement remote scan later)
                // Fallback to legacy behavior for GitHub to keep it working
                await performAnalysis(null);
            } else {
                // Local: Scan first
                const res = await axios.get(`${API_BASE}/explorer/scan?path=${encodeURIComponent(explorerRootPath)}`);
                if (res.data.success) {
                    setScannedFiles(res.data.scan.files);
                    setShowSelectionModal(true);
                }
            }
        } catch (err: any) {
            console.error("Scan failed:", err);
            alert("Scan failed: " + (err.response?.data?.detail || err.message));
        } finally {
            setIsScanning(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground overflow-hidden">
            {/* Header with Connect Button */}
            <div className="p-3 border-b border-border/50 bg-muted/20">
                <Button
                    className="w-full gap-2 bg-primary text-primary-inventory hover:bg-primary/90 shadow-lg shadow-primary/20 transition-all font-semibold"
                    onClick={() => {
                        if (!explorerRootPath) {
                            // If not connected, toggle expanded input? 
                            // For now let's just use a dialog style for connect
                        }
                        setExplorerRootPath(null);
                        setFlowData(null);
                    }}
                >
                    <Plus className="w-4 h-4" />
                    Connect Repository
                </Button>
            </div>

            {/* Connect Input Area (Standardized) */}
            {!explorerRootPath && (
                <div className="p-4 bg-muted/50 border-b border-border space-y-3 animate-in fade-in duration-300">
                    <div className="relative">
                        <Github className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                        <Input
                            placeholder="Absolute path or GitHub URL..."
                            value={connectInput}
                            onChange={(e) => setConnectInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
                            className="w-full bg-card border border-border rounded-lg text-xs pl-8 pr-3 py-2 focus:outline-none focus:ring-1 focus:ring-neon-yellow/50 text-foreground placeholder:text-muted-foreground transition-all h-auto"
                        />
                    </div>
                    <Button
                        onClick={handleConnect}
                        disabled={isAnalyzing || !connectInput.trim()}
                        size="sm"
                        className="w-full bg-neon-yellow text-neutral-950 hover:bg-neon-yellow/90 font-bold"
                    >
                        {isAnalyzing && <Loader2 className="w-3 h-3 mr-2 animate-spin" />}
                        Initialize
                    </Button>
                </div>
            )}

            {/* Search */}
            <div className="px-4 pt-4 pb-2 bg-transparent border-b border-border/50">
                <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                    <Input
                        className="w-full bg-muted border border-border rounded-lg text-xs pl-8 pr-3 py-2 focus:outline-none focus:ring-1 focus:ring-neon-yellow/50 text-foreground placeholder:text-muted-foreground transition-all h-auto"
                        placeholder="Search history..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col p-4 space-y-4">
                {/* HISTORY SECTION */}
                {filteredHistory.length > 0 ? (
                    <div className="space-y-4">
                        {filteredHistory.map(item => (
                            <div key={item.id} className="space-y-1">
                                <div
                                    className={cn(
                                        "group relative p-4 rounded-xl border transition-all duration-300 cursor-pointer",
                                        "bg-gradient-to-br from-card to-muted/20",
                                        "hover:shadow-md",
                                        explorerRootPath === item.path
                                            ? "border-neon-yellow/40 hover:border-neon-yellow/60 bg-neon-yellow/5"
                                            : "border-border/50 hover:border-primary/50 hover:bg-accent/50"
                                    )}
                                    onClick={() => loadHistoryItem(item)}
                                >
                                    <div className="flex justify-between items-center gap-3">
                                        <div className={cn(
                                            "w-8 h-8 rounded-lg flex items-center justify-center transition-colors shadow-sm",
                                            explorerRootPath === item.path ? "bg-primary text-primary-inventory" : "bg-muted/50 text-muted-foreground"
                                        )}>
                                            {item.type === 'github' ? <Github className="w-4 h-4" /> : <Folder className="w-4 h-4" />}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <span className={cn(
                                                    "text-xs font-bold uppercase tracking-wide truncate",
                                                    explorerRootPath === item.path ? "text-primary shadow-primary/10" : "text-foreground"
                                                )}>
                                                    {item.name}
                                                </span>
                                            </div>
                                            <div className="text-[10px] text-muted-foreground truncate opacity-70 font-mono">
                                                {item.type} • {item.path}
                                            </div>
                                        </div>
                                        <Button
                                            size="icon"
                                            variant="ghost"
                                            className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-destructive/20 hover:text-destructive"
                                            onClick={(e: React.MouseEvent) => { e.stopPropagation(); removeFromHistory(item.id); }}
                                        >
                                            <Trash2 className="w-3 h-3" />
                                        </Button>
                                    </div>
                                </div>

                                {/* NESTED FILE TREE */}
                                {explorerRootPath === item.path && (
                                    <div className="ml-5 mt-2 mb-4 border-l border-border/50 pl-3 animate-in slide-in-from-left-2 duration-300">
                                        {explorerFiles.length > 0 ? (
                                            <div className="space-y-0.5">
                                                {renderTree(explorerFiles)}
                                            </div>
                                        ) : (
                                            <div className="py-2 text-[10px] text-muted-foreground/60 italic font-mono">
                                                {item.type === 'github' || item.path.startsWith('http')
                                                    ? "[REMOTE ARCHITECTURE SYNCED]"
                                                    : isAnalyzing ? "STREAMING CONTEXT..." : "NULL FILESYSTEM"}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center py-20 px-8 text-center space-y-4 opacity-30">
                        <Code2 className="w-12 h-12" />
                        <p className="text-[10px] font-bold uppercase tracking-widest leading-relaxed">No repository context initialized</p>
                    </div>
                )}
            </div>

            {/* Bottom Analysis Action */}
            {explorerRootPath && (
                <div className="p-4 border-t border-border bg-card/50 backdrop-blur-md z-20">
                    <Button
                        disabled={isAnalyzing || isScanning}
                        onClick={handleAnalyze}
                        className={cn(
                            "w-full gap-2 font-black uppercase tracking-[0.15em] text-[10px] py-6 rounded-xl transition-all",
                            isAnalyzing || isScanning
                                ? "bg-muted text-muted-foreground"
                                : "bg-neon-yellow text-neutral-950 hover:bg-neon-yellow/90 shadow-lg shadow-neon-yellow/10"
                        )}
                    >
                        {isAnalyzing ? (
                            <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                Processing Context...
                            </>
                        ) : (
                            <>
                                <Play className="w-3.5 h-3.5 fill-current" />
                                {isScanning ? "Scanning Workspace..." : (
                                    analysisHistory.some(h => h.path === explorerRootPath) ? "Refresh Analysis" : "Analyze Repository"
                                )}
                            </>
                        )}
                    </Button>
                </div>
            )}

            <FileSelectionModal
                isOpen={showSelectionModal}
                onClose={() => setShowSelectionModal(false)}
                onConfirm={(files) => {
                    setShowSelectionModal(false);
                    performAnalysis(files);
                }}
                files={scannedFiles}
                rootPath={explorerRootPath || ''}
            />
        </div>
    );
};


