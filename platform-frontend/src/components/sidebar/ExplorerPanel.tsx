import React, { useState } from 'react';
import axios from 'axios';
import { useAppStore } from '@/store';
import { FolderOpen, FileCode, Folder, ChevronRight, ChevronDown, Play, Search, Code2, Plus, Globe, Trash2 } from 'lucide-react';
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
            setExplorerRootPath(directoryHandle.name);

            const files: FileNode[] = [];
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

            addToHistory({ name: directoryHandle.name, path: directoryHandle.name, type: 'local' });
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
                    addToHistory({ name: path.split('/').pop() || path, path, type: 'github', flowData: res.data.flow_data });
                    setExplorerFiles([]);
                }
            } else {
                const res = await axios.get(`http://localhost:8000/explorer/list?path=${encodeURIComponent(path)}`);
                setExplorerFiles(res.data);
                setExplorerRootPath(path);
                addToHistory({ name: path.split('/').pop() || path, path, type: 'local' });
            }
            setConnectInput('');
        } catch (err) {
            console.error("Connection failed:", err);
            alert("Failed to connect: " + (err as any).message);
        } finally {
            setIsAnalyzing(false);
        }
    };

    const loadHistoryItem = async (item: any) => {
        setExplorerRootPath(item.path);
        if (item.flowData) {
            setFlowData(item.flowData);
            setExplorerFiles([]);
        } else if (item.type === 'local') {
            try {
                const res = await axios.get(`http://localhost:8000/explorer/list?path=${encodeURIComponent(item.path)}`);
                setExplorerFiles(res.data);
            } catch {
                setExplorerFiles([]);
            }
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
                setFlowData(res.data.flow_data);
            }
        } catch (err) {
            console.error("Analysis failed:", err);
            alert("Analysis failed: " + (err as any).message);
        } finally {
            setIsAnalyzing(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-charcoal-900 text-white overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-white/10 flex flex-shrink-0 items-center justify-between bg-charcoal-900 z-10">
                <div className="flex items-center gap-2">
                    <Code2 className="w-5 h-5 text-neon-yellow" />
                    <h2 className="font-bold text-sm tracking-tight uppercase">Explorer</h2>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar">
                {/* 1. HISTORY SECTION (Top) */}
                {analysisHistory.length > 0 && (
                    <div className="pb-4">
                        <div className="px-4 py-3 flex items-center justify-between">
                            <h3 className="text-[10px] font-black text-gray-500 uppercase tracking-[0.2em] select-none">Recent Analyses</h3>
                            <div className="h-px flex-1 bg-white/5 ml-4" />
                        </div>
                        <div className="px-2 space-y-1">
                            {analysisHistory.map(item => (
                                <div
                                    key={item.id}
                                    className={cn(
                                        "group flex items-center justify-between p-2 rounded-lg cursor-pointer transition-all border border-transparent",
                                        explorerRootPath === item.path ? "bg-neon-yellow/10 border-neon-yellow/20" : "hover:bg-white/5"
                                    )}
                                    onClick={() => loadHistoryItem(item)}
                                >
                                    <div className="flex items-center gap-2 min-w-0">
                                        <div className={cn(
                                            "w-7 h-7 rounded flex items-center justify-center shrink-0",
                                            item.type === 'github' ? "bg-blue-500/10 text-blue-400" : "bg-neon-yellow/10 text-neon-yellow"
                                        )}>
                                            {item.type === 'github' ? <Globe className="w-3.5 h-3.5" /> : <Folder className="w-3.5 h-3.5" />}
                                        </div>
                                        <div className="flex flex-col min-w-0">
                                            <span className="text-xs font-bold text-gray-200 truncate">{item.name}</span>
                                            <span className="text-[9px] text-gray-500 truncate font-mono">{item.path}</span>
                                        </div>
                                    </div>
                                    <button
                                        onClick={(e) => { e.stopPropagation(); removeFromHistory(item.id); }}
                                        className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 text-gray-600 transition-all"
                                    >
                                        <Trash2 className="w-3 h-3" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* 2. MAIN AREA (Bottom) */}
                <div className="border-t border-white/5">
                    {!explorerRootPath ? (
                        <div className="flex flex-col">
                            <div className="px-4 py-3 flex items-center gap-4">
                                <h3 className="text-[10px] font-black text-gray-500 uppercase tracking-[0.2em] whitespace-nowrap">Connect New</h3>
                                <div className="h-px w-full bg-white/5" />
                            </div>

                            {/* Input Section */}
                            <div className="px-6 py-4 space-y-6">
                                <div className="space-y-4">
                                    <div className="space-y-2">
                                        <input
                                            type="text"
                                            placeholder="GitHub URL or Local Path..."
                                            value={connectInput}
                                            onChange={(e) => setConnectInput(e.target.value)}
                                            onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
                                            className="w-full bg-charcoal-950 border border-white/10 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-neon-yellow/50 transition-all placeholder:text-gray-600 shadow-inner"
                                        />
                                        <Button
                                            onClick={handleConnect}
                                            className="w-full bg-white/5 hover:bg-white/10 text-white font-bold text-xs py-5 rounded-xl border border-white/5 transition-all active:scale-[0.98]"
                                        >
                                            Connect Repo
                                        </Button>
                                    </div>
                                </div>

                                <div className="relative flex items-center py-2">
                                    <div className="flex-grow border-t border-white/5"></div>
                                    <span className="flex-shrink mx-4 text-[9px] font-black text-gray-600 uppercase tracking-[0.2em]">OR</span>
                                    <div className="flex-grow border-t border-white/5"></div>
                                </div>

                                <Button
                                    onClick={handleOpenFolder}
                                    className="w-full bg-neon-yellow text-charcoal-900 hover:bg-neon-yellow/90 font-black text-xs py-6 rounded-xl shadow-xl shadow-neon-yellow/5 active:scale-[0.98] group"
                                >
                                    <FolderOpen className="w-4 h-4 mr-2 group-hover:scale-110 transition-transform" />
                                    Open Local Folder
                                </Button>
                            </div>
                        </div>
                    ) : (
                        <div className="p-2 space-y-4">
                            <div className="flex items-center justify-between px-2 mb-2">
                                <div className="flex items-center gap-2 min-w-0">
                                    <div className="p-1.5 bg-neon-yellow/10 rounded">
                                        <Folder className="w-3.5 h-3.5 text-neon-yellow" />
                                    </div>
                                    <span className="text-[11px] font-mono text-gray-400 truncate">{explorerRootPath}</span>
                                </div>
                                <Button variant="ghost" size="icon" className="h-7 w-7 text-gray-500 hover:text-white" onClick={() => setExplorerRootPath(null)}>
                                    <Search className="w-3.5 h-3.5" />
                                </Button>
                            </div>
                            <div className="space-y-0.5">
                                {renderTree(explorerFiles)}
                            </div>
                        </div>
                    )}
                </div>

                {explorerRootPath && (
                    <div className="p-4 border-t border-white/10 bg-charcoal-950/50">
                        <Button
                            disabled={isAnalyzing}
                            onClick={handleAnalyze}
                            className={cn(
                                "w-full gap-2 font-bold uppercase tracking-wider text-xs py-5",
                                isAnalyzing ? "bg-gray-700" : "bg-neon-yellow text-charcoal-900 hover:bg-neon-yellow/90 shadow-lg shadow-neon-yellow/10"
                            )}
                        >
                            {isAnalyzing ? (
                                <>
                                    <div className="w-3.5 h-3.5 border-2 border-charcoal-900/10 border-t-charcoal-900 rounded-full animate-spin" />
                                    Analyzing...
                                </>
                            ) : (
                                <>
                                    <Play className="w-3.5 h-3.5 fill-current" />
                                    Start Analysis
                                </>
                            )}
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
};
