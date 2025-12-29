import React, { useState } from 'react';
import axios from 'axios';
import { useAppStore } from '@/store';
import { FileCode, Folder, ChevronRight, ChevronDown, Play, Code2, Globe, Trash2, X, Github } from 'lucide-react';
import { Button } from '@/components/ui/button';
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

    const toggleFolder = (path: string) => {
        setIsExpanded(prev => ({ ...prev, [path]: !prev[path] }));
    };

    const renderTree = (nodes: FileNode[], depth = 0) => {
        return nodes.map(node => (
            <div key={node.path} className="select-none">
                <div
                    className={cn(
                        "flex items-center py-1.5 px-2 hover:bg-muted/50 cursor-pointer rounded-md transition-colors group",
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
        <div className="flex flex-col h-full bg-card text-foreground overflow-hidden">
            {/* Header - Matches Remme Style */}
            <div className="p-4 border-b border-border flex items-center justify-between bg-card/50 backdrop-blur-md sticky top-0 z-10">
                <div className="flex items-center gap-2">
                    <div className="p-1.5 bg-neon-yellow/10 rounded-lg">
                        <Code2 className="w-5 h-5 text-neon-yellow" />
                    </div>
                    <div>
                        <h2 className="font-semibold text-sm tracking-tight text-foreground uppercase">Explorer</h2>
                        <p className="text-[10px] text-neon-yellow/80 font-mono tracking-widest">{analysisHistory.length} PROJECTS</p>
                    </div>
                </div>
                {explorerRootPath && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-foreground"
                        onClick={() => setExplorerRootPath(null)}
                        title="Close active project"
                    >
                        <X className="w-4 h-4" />
                    </Button>
                )}
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col">
                {/* HISTORY SECTION */}
                {analysisHistory.length > 0 && (
                    <div className="flex flex-col flex-1 min-h-0">
                        {!explorerRootPath && (
                            <div className="px-4 py-3 flex items-center justify-between flex-shrink-0">
                                <h3 className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.2em] select-none">Recent Analyses</h3>
                                <div className="h-px flex-1 bg-muted/50 ml-4" />
                            </div>
                        )}
                        <div className={cn("px-2 space-y-1 overflow-y-auto custom-scrollbar pb-2 flex-1", explorerRootPath ? "p-1" : "p-2")}>
                            {analysisHistory.map(item => (
                                <React.Fragment key={item.id}>
                                    <div
                                        className={cn(
                                            "group flex items-center justify-between p-2 rounded-lg cursor-pointer transition-all border border-transparent flex-shrink-0",
                                            explorerRootPath === item.path ? "bg-neon-yellow/10 border-neon-yellow/20" : "hover:bg-muted/50"
                                        )}
                                        onClick={() => loadHistoryItem(item)}
                                    >
                                        <div className="flex items-center gap-2 min-w-0">
                                            <div className={cn(
                                                "w-7 h-7 rounded flex items-center justify-center shrink-0",
                                                item.type === 'github' ? "bg-blue-500/10 text-blue-400" : "bg-neon-yellow/10 text-neon-yellow"
                                            )}>
                                                {item.type === 'github' ? <Github className="w-3.5 h-3.5" /> : <Folder className="w-3.5 h-3.5" />}
                                            </div>
                                            <div className="flex flex-col min-w-0">
                                                <span className="text-xs font-bold text-foreground truncate">{item.name}</span>
                                                <span className="text-[9px] text-muted-foreground truncate font-mono opacity-60">{item.path}</span>
                                            </div>
                                        </div>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); removeFromHistory(item.id); }}
                                            className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 text-muted-foreground transition-all"
                                        >
                                            <Trash2 className="w-3 h-3" />
                                        </button>
                                    </div>

                                    {/* NESTED FILE TREE */}
                                    {explorerRootPath === item.path && (
                                        <div className="ml-9 mt-1 mb-4 border-l border-border/50 pl-2">
                                            {explorerFiles.length > 0 ? (
                                                <div className="space-y-0.5">
                                                    {renderTree(explorerFiles)}
                                                </div>
                                            ) : (
                                                <div className="py-4 text-[10px] text-muted-foreground italic">
                                                    {item.type === 'github' || item.path.startsWith('http')
                                                        ? "GitHub architecture map loaded (Start Analysis to see details)"
                                                        : isAnalyzing ? "Loading files..." : "No files found."}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </React.Fragment>
                            ))}
                        </div>
                    </div>
                )}

                {/* CONNECT INPUT - Show when no project is selected */}
                <div className="flex-1 min-h-0">
                    {explorerRootPath ? null : (
                        <div className="flex flex-col p-6 space-y-4">
                            <div className="space-y-2">
                                <div className="relative">
                                    <input
                                        type="text"
                                        placeholder="GitHub URL or Local Absolute Path..."
                                        value={connectInput}
                                        onChange={(e) => setConnectInput(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
                                        className="w-full bg-background border border-border rounded-xl pl-10 pr-4 py-3 text-sm focus:outline-none focus:border-neon-yellow/50 transition-all placeholder:text-muted-foreground"
                                    />
                                    <Globe className="absolute left-3.5 top-3.5 w-4 h-4 text-muted-foreground" />
                                </div>
                                <Button
                                    onClick={handleConnect}
                                    disabled={isAnalyzing || !connectInput.trim()}
                                    className="w-full bg-neon-yellow text-neutral-950 hover:bg-neon-yellow/90 font-black text-xs py-5 rounded-xl shadow-xl shadow-neon-yellow/5 disabled:bg-muted disabled:text-muted-foreground"
                                >
                                    Connect Repository
                                </Button>
                            </div>

                            <p className="text-[10px] text-muted-foreground text-center leading-relaxed">
                                💡 <span className="text-muted-foreground">Mac tip:</span> Right-click folder in Finder → Get Info → copy path from "Where:"
                            </p>
                        </div>
                    )}
                </div>
            </div>

            {/* Bottom Analysis Action */}
            {explorerRootPath && (
                <div className="p-4 border-t border-border bg-card z-20">
                    <Button
                        disabled={isAnalyzing || isScanning}
                        onClick={handleAnalyze}
                        className={cn(
                            "w-full gap-2 font-black uppercase tracking-[0.15em] text-xs py-6 rounded-xl transition-all",
                            isAnalyzing || isScanning
                                ? "bg-muted text-muted-foreground"
                                : "bg-neon-yellow text-neutral-950 hover:bg-neon-yellow/90 shadow-[0_0_20px_rgba(234,255,0,0.1)] active:scale-95"
                        )}
                    >
                        {isAnalyzing ? (
                            <>
                                <div className="w-3.5 h-3.5 border-2 border-charcoal-900/10 border-t-charcoal-900 rounded-full animate-spin" />
                                Processing...
                            </>
                        ) : (
                            <>
                                <Play className="w-3.5 h-3.5 fill-current" />
                                {isScanning ? "Scanning..." : (
                                    analysisHistory.some(h => h.path === explorerRootPath) ? "Analyze Again" : "Analyze Context"
                                )}
                            </>
                        )}
                    </Button>
                </div>
            )}
            {/* Credits Footer */}
            <div className="p-3 text-center border-t border-border/50 bg-background">
                <p className="text-[10px] text-muted-foreground">
                    Inspired by <a href="https://github.com/KalaINC/flowstep" target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-neon-yellow transition-colors underline decoration-dotted">flowstep</a>
                </p>
            </div>


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

