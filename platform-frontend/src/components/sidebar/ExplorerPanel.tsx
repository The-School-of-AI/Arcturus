import React, { useState } from 'react';
import axios from 'axios';
import { useAppStore } from '@/store';
import { FolderOpen, FileCode, Folder, ChevronRight, ChevronDown, Play, Search, Code2, Plus, Globe, Trash2, X, Github } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

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

    const handleOpenFolder = async () => {
        try {
            // @ts-ignore - window.showDirectoryPicker is experimental
            const directoryHandle = await window.showDirectoryPicker();
            
            // Note: Browser file picker doesn't expose absolute path (security limitation)
            // Files can be browsed in this session, but won't persist after refresh
            // For persistent history, user should use "Connect Repository" with absolute path
            setExplorerRootPath(directoryHandle.name);

            async function scan(handle: any, currentPath: string): Promise<FileNode[]> {
                const results: FileNode[] = [];
                for await (const entry of handle.values()) {
                    const fullPath = `${currentPath}/${entry.name}`;
                    if (entry.kind === 'file') {
                        results.push({ name: entry.name, path: fullPath, type: 'file' });
                    } else if (entry.kind === 'directory') {
                        results.push({
                            name: entry.name,
                            path: fullPath,
                            type: 'folder',
                            children: await scan(entry, fullPath)
                        });
                    }
                }
                return results.sort((a, b) => (a.type === b.type ? a.name.localeCompare(b.name) : a.type === 'folder' ? -1 : 1));
            }

            const scannedFiles = await scan(directoryHandle, directoryHandle.name);
            setExplorerFiles(scannedFiles);

            // Add to history with cached files for current session
            // Note: After page refresh, cachedFiles won't persist (not in localStorage)
            // User will get a helpful message explaining they should use absolute paths
            addToHistory({ 
                name: directoryHandle.name, 
                path: directoryHandle.name, 
                type: 'local',
                cachedFiles: scannedFiles // Store for re-expansion during session
            });
        } catch (err) {
            console.error(err);
        }
    };

    const toggleFolder = (path: string) => {
        setIsExpanded(prev => ({ ...prev, [path]: !prev[path] }));
    };

    const renderTree = (nodes: FileNode[], depth = 0) => {
        return nodes.map(node => (
            <div key={node.path} className="select-none">
                <div
                    className={cn(
                        "flex items-center py-1.5 px-2 hover:bg-white/5 cursor-pointer rounded-md transition-colors group",
                        depth > 0 && "ml-2"
                    )}
                    onClick={() => node.type === 'folder' ? toggleFolder(node.path) : null}
                >
                    {node.type === 'folder' ? (
                        <>
                            {isExpanded[node.path] ? <ChevronDown className="w-3.5 h-3.5 mr-1.5 text-gray-500" /> : <ChevronRight className="w-3.5 h-3.5 mr-1.5 text-gray-500" />}
                            <Folder className="w-4 h-4 mr-2 text-neon-yellow/70" />
                        </>
                    ) : (
                        <FileCode className="w-4 h-4 mr-2 ml-5 text-blue-400/70" />
                    )}
                    <span className="text-[13px] text-gray-300 truncate font-medium group-hover:text-white">{node.name}</span>
                </div>
                {node.type === 'folder' && isExpanded[node.path] && node.children && (
                    <div className="border-l border-white/5 ml-3 mt-0.5 mb-1">
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
                const res = await axios.post('http://localhost:8000/explorer/analyze', { path, type: 'github' });
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
            const res = await axios.get(`http://localhost:8000/explorer/list?path=${encodeURIComponent(path)}`);
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

        // Check for cached files first (from browser picker during this session)
        if (item.cachedFiles && item.cachedFiles.length > 0) {
            setExplorerFiles(item.cachedFiles);
            return;
        }

        if (item.type === 'local') {
            try {
                const res = await axios.get(`http://localhost:8000/explorer/list?path=${encodeURIComponent(item.path)}`);
                const { files, root_path, error } = res.data;
                
                if (error) {
                    // Path doesn't exist or can't be resolved
                    const isAbsolutePath = item.path.startsWith('/') || item.path.includes(':\\');
                    const message = isAbsolutePath 
                        ? `Path no longer exists: ${item.path}\n\nDo you want to remove it from history?`
                        : `Cannot resolve path "${item.path}".\n\nBrowser-selected folders cannot be reloaded after refresh.\nPlease use "Connect Repository" with an absolute path instead.\n\nRemove from history?`;
                    
                    const shouldRemove = window.confirm(message);
                    if (shouldRemove) {
                        removeFromHistory(item.id);
                        setExplorerRootPath(null);
                    }
                    setExplorerFiles([]);
                    return;
                }
                
                setExplorerFiles(files || []);
                // Update the path in history if backend resolved it to absolute
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

    const handleAnalyze = async () => {
        if (!explorerRootPath) return;
        setIsAnalyzing(true);
        try {
            const isGithub = explorerRootPath.startsWith('http');
            const res = await axios.post('http://localhost:8000/explorer/analyze', {
                path: explorerRootPath,
                type: isGithub ? 'github' : 'local'
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
                        const filesRes = await axios.get(`http://localhost:8000/explorer/list?path=${encodeURIComponent(root_path)}`);
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

    return (
        <div className="flex flex-col h-full bg-charcoal-900 text-white overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-white/10 flex flex-shrink-0 items-center justify-between bg-charcoal-900 z-10 shadow-xl">
                <div className="flex items-center gap-2">
                    <Code2 className="w-5 h-5 text-neon-yellow" />
                    <h2 className="font-bold text-sm tracking-tight uppercase">Explorer</h2>
                </div>
                {explorerRootPath && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-gray-500 hover:text-white"
                        onClick={() => setExplorerRootPath(null)}
                        title="Close active project"
                    >
                        <X className="w-4 h-4" />
                    </Button>
                )}
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col">
                {/* 1. HISTORY SECTION (Always visible at top if exists) */}
                {analysisHistory.length > 0 && (
                    <div className="flex flex-col flex-1 min-h-0">
                        {!explorerRootPath && (
                            <div className="px-4 py-3 flex items-center justify-between flex-shrink-0">
                                <h3 className="text-[10px] font-black text-gray-500 uppercase tracking-[0.2em] select-none">Recent Analyses</h3>
                                <div className="h-px flex-1 bg-white/5 ml-4" />
                            </div>
                        )}
                        <div className={cn("px-2 space-y-1 overflow-y-auto custom-scrollbar pb-2 flex-1", explorerRootPath ? "p-1" : "p-2")}>
                            {analysisHistory.map(item => (
                                <React.Fragment key={item.id}>
                                    <div
                                        className={cn(
                                            "group flex items-center justify-between p-2 rounded-lg cursor-pointer transition-all border border-transparent flex-shrink-0",
                                            explorerRootPath === item.path ? "bg-neon-yellow/10 border-neon-yellow/20" : "hover:bg-white/5"
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
                                                <span className="text-xs font-bold text-gray-200 truncate">{item.name}</span>
                                                <span className="text-[9px] text-gray-500 truncate font-mono opacity-60">{item.path}</span>
                                            </div>
                                        </div>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); removeFromHistory(item.id); }}
                                            className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 text-gray-600 transition-all"
                                        >
                                            <Trash2 className="w-3 h-3" />
                                        </button>
                                    </div>

                                    {/* NESTED FILE TREE - Only show for selected item */}
                                    {explorerRootPath === item.path && (
                                        <div className="ml-9 mt-1 mb-4 border-l border-white/5 pl-2">
                                            {explorerFiles.length > 0 ? (
                                                <div className="space-y-0.5">
                                                    {renderTree(explorerFiles)}
                                                </div>
                                            ) : (
                                                <div className="py-4 text-[10px] text-gray-500 italic">
                                                    {item.type === 'github' || item.path.startsWith('http')
                                                        ? "GitHub architecture map loaded (Start Analysis to see details)"
                                                        : isAnalyzing ? "Loading files..." : "File tree unavailable for this local path."}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </React.Fragment>
                            ))}
                        </div>
                    </div>
                )}
                <div className="flex-1 min-h-0">
                    {explorerRootPath ? null : (
                        <div className="flex flex-col p-6 space-y-6">
                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <div className="relative">
                                        <input
                                            type="text"
                                            placeholder="GitHub URL or Local Absolute Path..."
                                            value={connectInput}
                                            onChange={(e) => setConnectInput(e.target.value)}
                                            onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
                                            className="w-full bg-charcoal-950 border border-white/10 rounded-xl pl-10 pr-4 py-3 text-sm focus:outline-none focus:border-neon-yellow/50 transition-all placeholder:text-gray-600"
                                        />
                                        <Globe className="absolute left-3.5 top-3.5 w-4 h-4 text-gray-600" />
                                    </div>
                                    <Button
                                        onClick={handleConnect}
                                        disabled={isAnalyzing}
                                        className="w-full bg-white/5 hover:bg-white/10 text-white font-bold text-xs py-5 rounded-xl border border-white/5 transition-all"
                                    >
                                        Connect Repository
                                    </Button>
                                </div>
                            </div>

                            <div className="relative flex items-center">
                                <div className="flex-grow border-t border-white/5"></div>
                                <span className="flex-shrink mx-4 text-[9px] font-black text-gray-600 uppercase tracking-[0.2em]">Local Access</span>
                                <div className="flex-grow border-t border-white/5"></div>
                            </div>

                            <Button
                                onClick={handleOpenFolder}
                                className="w-full bg-neon-yellow text-charcoal-900 hover:bg-neon-yellow/90 font-black text-xs py-6 rounded-xl shadow-xl shadow-neon-yellow/5"
                            >
                                <FolderOpen className="w-4 h-4 mr-2" />
                                Select Folder
                            </Button>

                            <p className="text-[10px] text-gray-500 text-center leading-relaxed italic">
                                Note: Absolute paths are required for backend analysis of local folders.
                            </p>
                        </div>
                    )}
                </div>
            </div>

            {/* Bottom Analysis Action */}
            {
                explorerRootPath && (
                    <div className="p-4 border-t border-white/10 bg-charcoal-900 z-20">
                        <Button
                            disabled={isAnalyzing}
                            onClick={handleAnalyze}
                            className={cn(
                                "w-full gap-2 font-black uppercase tracking-[0.15em] text-xs py-6 rounded-xl transition-all",
                                isAnalyzing ? "bg-gray-800 text-gray-500" : "bg-neon-yellow text-charcoal-900 hover:bg-neon-yellow/90 shadow-[0_0_20px_rgba(234,255,0,0.1)] active:scale-95"
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
                                    Start Analysis
                                </>
                            )}
                        </Button>
                    </div>
                )
            }
        </div>
    );
};
