import React, { useState, useMemo } from 'react';
import axios from 'axios';
import { useAppStore } from '@/store';
import { FileCode, Folder, ChevronRight, ChevronDown, FileText, File, Plus, Github, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { API_BASE } from '@/lib/api';

interface FileNode {
    name: string;
    path: string;
    type: string; // 'folder' | 'file' | extension
    children?: FileNode[];
}

const FileTreeItem: React.FC<{
    item: FileNode;
    level: number;
    expandedFolders: Record<string, boolean>;
    toggleFolder: (path: string) => void;
    onSelect: (item: FileNode) => void;
    selectedPath: string | null;
}> = ({ item, level, expandedFolders, toggleFolder, onSelect, selectedPath }) => {
    const isFolder = item.type === 'folder';
    const isOpen = expandedFolders[item.path];

    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (isFolder) {
            toggleFolder(item.path);
        } else {
            onSelect(item);
        }
    };

    const getIcon = () => {
        if (isFolder) {
            const Icon = isOpen ? ChevronDown : ChevronRight;
            return <Icon className="w-3.5 h-3.5 text-muted-foreground" />;
        }
        // File icons based on extension/type
        if (item.name.endsWith('.tsx') || item.name.endsWith('.ts')) return <FileCode className="w-3.5 h-3.5 text-blue-400" />;
        if (item.name.endsWith('.css')) return <FileCode className="w-3.5 h-3.5 text-blue-300" />;
        if (item.name.endsWith('.json')) return <FileCode className="w-3.5 h-3.5 text-yellow-400" />;
        if (item.name.endsWith('.md')) return <FileText className="w-3.5 h-3.5 text-purple-400" />;
        if (item.name.endsWith('.py')) return <FileCode className="w-3.5 h-3.5 text-green-400" />;
        return <File className="w-3.5 h-3.5 text-muted-foreground" />;
    };

    return (
        <div>
            <div
                className={cn(
                    "group relative flex items-center gap-1.5 py-1 px-2 select-none cursor-pointer transition-colors rounded-sm mx-1",
                    selectedPath === item.path
                        ? "bg-accent text-accent-foreground"
                        : "hover:bg-accent/50 text-muted-foreground hover:text-foreground",
                    level > 0 && "ml-3"
                )}
                style={{ paddingLeft: `${Math.max(4, level * 12)}px` }}
                onClick={handleClick}
            >
                <div className="shrink-0 flex items-center justify-center w-4 h-4">
                    {getIcon()}
                </div>
                {isFolder && (
                    <Folder className={cn("w-3.5 h-3.5 mr-1", isOpen ? "text-foreground" : "text-muted-foreground")} />
                )}
                <span className="truncate text-[13px] leading-none py-1">{item.name}</span>
            </div>
            {isOpen && item.children && (
                <div>
                    {item.children.map((child) => (
                        <FileTreeItem
                            key={child.path}
                            item={child}
                            level={level + 1}
                            expandedFolders={expandedFolders}
                            toggleFolder={toggleFolder}
                            onSelect={onSelect}
                            selectedPath={selectedPath}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

export const ExplorerPanel: React.FC = () => {
    const {
        explorerRootPath, setExplorerRootPath,
        explorerFiles, setExplorerFiles,
        isAnalyzing, setIsAnalyzing,
        setFlowData, addToHistory,
        openDocument,
        activeDocumentId
    } = useAppStore();

    const [isExpanded, setIsExpanded] = useState<Record<string, boolean>>({});
    const [connectInput, setConnectInput] = useState('');

    const toggleFolder = (path: string) => {
        setIsExpanded(prev => ({ ...prev, [path]: !prev[path] }));
    };

    const handleFileClick = (node: FileNode) => {
        openDocument({
            id: node.path,
            title: node.name,
            type: node.name.split('.').pop() || 'txt',
            content: undefined // Content fetched by editor
        });
    };

    const handleConnect = async () => {
        if (!connectInput.trim()) return;
        const isGithub = connectInput.startsWith('http');
        const path = connectInput.trim();

        try {
            setIsAnalyzing(true);
            if (isGithub) {
                // ... existing github logic ...
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
                const res = await axios.get(`${API_BASE}/system/files?path=${encodeURIComponent(path)}`);
                const { files, root_path, error } = res.data;

                if (error) {
                    alert(`Path not found: ${root_path}`);
                    return;
                }

                setExplorerFiles(files);
                setExplorerRootPath(root_path);
                addToHistory({ name: root_path.split('/').pop() || root_path, path: root_path, type: 'local' });
            }
            setConnectInput('');
        } catch (err: any) {
            console.error("Connection failed:", err);
            alert("Failed to connect: " + (err.response?.data?.detail || err.message));
        } finally {
            setIsAnalyzing(false);
        }
    };

    const refreshFiles = async () => {
        if (!explorerRootPath) return;
        try {
            const res = await axios.get(`${API_BASE}/system/files?path=${encodeURIComponent(explorerRootPath)}`);
            if (res.data.files) setExplorerFiles(res.data.files);
        } catch (e) {
            console.error("Failed to refresh", e);
        }
    }

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground overflow-hidden">
            {/* Header / Connect */}
            {!explorerRootPath ? (
                <div className="p-4 bg-muted/50 border-b border-border space-y-3">
                    <div className="relative">
                        <Github className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                        <Input
                            placeholder="Absolute path or GitHub URL..."
                            value={connectInput}
                            onChange={(e) => setConnectInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
                            className="w-full bg-card border border-border rounded-lg text-xs pl-8 pr-3 py-2 text-foreground"
                        />
                    </div>
                    <Button
                        onClick={handleConnect}
                        disabled={isAnalyzing || !connectInput.trim()}
                        size="sm"
                        className="w-full bg-primary text-primary-foreground font-bold"
                    >
                        {isAnalyzing ? <Loader2 className="w-3 h-3 animate-spin mr-2" /> : <Plus className="w-3 h-3 mr-2" />}
                        {isAnalyzing ? "Connecting..." : "Connect Repository"}
                    </Button>
                </div>
            ) : (
                <div className="flex items-center justify-between p-2 px-3 border-b border-border/50 bg-muted/20">
                    <div className="flex items-center gap-2 truncate">
                        <div className="p-1 bg-primary/10 rounded">
                            <Folder className="w-3.5 h-3.5 text-primary" />
                        </div>
                        <span className="text-xs font-bold truncate" title={explorerRootPath}>
                            {explorerRootPath.split('/').pop()}
                        </span>
                    </div>
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={refreshFiles} title="Refresh Files">
                        <RefreshCw className="w-3 h-3 text-muted-foreground" />
                    </Button>
                </div>
            )}

            {/* File List */}
            <div className="flex-1 overflow-y-auto px-0 py-2 custom-scrollbar">
                {explorerFiles.length > 0 ? (
                    explorerFiles.map((node: any) => (
                        <FileTreeItem
                            key={node.path}
                            item={node}
                            level={0}
                            expandedFolders={isExpanded}
                            toggleFolder={toggleFolder}
                            onSelect={handleFileClick}
                            selectedPath={activeDocumentId}
                        />
                    ))
                ) : (
                    explorerRootPath && !isAnalyzing && (
                        <div className="flex flex-col items-center justify-center h-40 opacity-50">
                            <p className="text-xs text-muted-foreground">No files found</p>
                        </div>
                    )
                )}
            </div>
        </div>
    );
};


