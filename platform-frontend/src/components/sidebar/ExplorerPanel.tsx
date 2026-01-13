import React, { useState } from 'react';
import axios from 'axios';
import { useAppStore } from '@/store';
import { FileCode, Folder, ChevronRight, ChevronDown, FileText, File, Plus, Github, Loader2, RefreshCw, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { API_BASE } from '@/lib/api';
import {
    ContextMenu,
    ContextMenuContent,
    ContextMenuItem,
    ContextMenuSeparator,
    ContextMenuTrigger,
} from "@/components/ui/context-menu";

interface FileNode {
    name: string;
    path: string;
    type: string; // 'folder' | 'file' | extension
    children?: FileNode[];
}

// ... (other imports)

const FileTreeItem: React.FC<{
    item: FileNode;
    level: number;
    expandedFolders: Record<string, boolean>;
    toggleFolder: (path: string) => void;
    onSelect: (item: FileNode) => void;
    selectedPath: string | null;
    onRename: (path: string, newName: string) => void;
}> = ({ item, level, expandedFolders, toggleFolder, onSelect, selectedPath, onRename }) => {
    const isFolder = item.type === 'folder';
    const isOpen = expandedFolders[item.path];
    const [isRenaming, setIsRenaming] = useState(false);
    const [renameValue, setRenameValue] = useState(item.name);
    const inputRef = React.useRef<HTMLInputElement>(null);

    React.useEffect(() => {
        if (isRenaming && inputRef.current) {
            inputRef.current.focus();
            inputRef.current.select();
        }
    }, [isRenaming]);

    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (isRenaming) return;
        if (isFolder) {
            toggleFolder(item.path);
        } else {
            onSelect(item);
        }
    };

    const handleRenameSubmit = () => {
        if (renameValue.trim() && renameValue !== item.name) {
            onRename(item.path, renameValue.trim());
        }
        setIsRenaming(false);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleRenameSubmit();
        } else if (e.key === 'Escape') {
            setRenameValue(item.name);
            setIsRenaming(false);
        }
    };

    const handleContextMenuAction = (action: string) => {
        switch (action) {
            case 'rename':
                setIsRenaming(true);
                break;
            case 'reveal':
                window.electronAPI.send('shell:reveal', item.path);
                break;
            case 'terminal':
                window.electronAPI.send('terminal:create', { cwd: isFolder ? item.path : item.path.split('/').slice(0, -1).join('/') });
                break;
            case 'copy-path':
                navigator.clipboard.writeText(item.path);
                break;
            case 'delete':
                if (confirm(`Are you sure you want to delete ${item.name}?`)) {
                    window.electronAPI.invoke('fs:delete', item.path).then(() => {
                        // Parent handles refresh
                    });
                }
                break;
        }
    };

    const getIcon = () => {
        if (isFolder) {
            const Icon = isOpen ? ChevronDown : ChevronRight;
            return <Icon className="w-3.5 h-3.5 text-muted-foreground" />;
        }
        // File icons (same as before)
        if (item.name.endsWith('.tsx') || item.name.endsWith('.ts')) return <FileCode className="w-3.5 h-3.5 text-blue-400" />;
        if (item.name.endsWith('.css')) return <FileCode className="w-3.5 h-3.5 text-blue-300" />;
        if (item.name.endsWith('.json')) return <FileCode className="w-3.5 h-3.5 text-yellow-400" />;
        if (item.name.endsWith('.md')) return <FileText className="w-3.5 h-3.5 text-purple-400" />;
        if (item.name.endsWith('.py')) return <FileCode className="w-3.5 h-3.5 text-green-400" />;
        return <File className="w-3.5 h-3.5 text-muted-foreground" />;
    };

    return (
        <ContextMenu>
            <ContextMenuTrigger disabled={isRenaming}>
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

                        {isRenaming ? (
                            <input
                                ref={inputRef}
                                type="text"
                                value={renameValue}
                                onChange={(e) => setRenameValue(e.target.value)}
                                onBlur={handleRenameSubmit}
                                onKeyDown={handleKeyDown}
                                onClick={(e) => e.stopPropagation()}
                                className="flex-1 bg-background border border-primary h-6 text-xs px-1 outline-none"
                            />
                        ) : (
                            <span className="truncate text-[13px] leading-none py-1">{item.name}</span>
                        )}
                    </div>
                </div>
            </ContextMenuTrigger>
            <ContextMenuContent className="w-48">
                <ContextMenuItem onClick={() => handleContextMenuAction('rename')}>
                    Rename
                </ContextMenuItem>
                <ContextMenuItem onClick={() => handleContextMenuAction('reveal')}>Reveal in Finder</ContextMenuItem>
                <ContextMenuItem onClick={() => handleContextMenuAction('terminal')}>Open in Terminal</ContextMenuItem>
                <ContextMenuItem onClick={() => handleContextMenuAction('copy-path')}>Copy Path</ContextMenuItem>
                <ContextMenuSeparator />
                <ContextMenuItem onClick={() => handleContextMenuAction('delete')} className="text-red-500">Delete</ContextMenuItem>
            </ContextMenuContent>

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
                            onRename={onRename}
                        />
                    ))}
                </div>
            )}
        </ContextMenu>
    );
};

import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal } from 'lucide-react';

// ... (existing FileTreeItem Code - Unchanged)

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

    // Auto-load files on mount/change of root path
    React.useEffect(() => {
        if (explorerRootPath) {
            refreshFiles();
        }
    }, [explorerRootPath]);

    const toggleFolder = (path: string) => {
        setIsExpanded(prev => ({ ...prev, [path]: !prev[path] }));
    };

    const handleFileClick = (node: FileNode) => {
        openDocument({
            id: node.path,
            title: node.name,
            type: node.name.split('.').pop() || 'txt',
            content: undefined
        });
    };

    const handleRename = async (path: string, newName: string) => {
        const oldPath = path;
        const newPath = path.substring(0, path.lastIndexOf('/')) + '/' + newName;

        try {
            const res = await window.electronAPI.invoke('fs:rename', { oldPath, newPath });
            if (res.success) {
                refreshFiles();
            } else {
                alert('Rename failed: ' + res.error);
            }
        } catch (e) {
            console.error('Rename failed', e);
        }
    };

    const handleOpenProject = async () => {
        try {
            setIsAnalyzing(true);
            const path = await window.electronAPI.invoke('dialog:openDirectory');
            if (path) {
                // Set path, side-effect will trigger refreshFiles
                setExplorerRootPath(path);
                addToHistory({ name: path.split('/').pop() || path, path: path, type: 'local' });
            }
        } catch (error) {
            console.error(error);
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
            {/* Header with Dropdown Action Menu */}
            <div className="flex items-center justify-between p-2 px-3 border-b border-border/50 bg-muted/20">
                <div className="flex items-center gap-2 truncate flex-1">
                    {explorerRootPath ? (
                        <>
                            <div className="p-1 bg-primary/10 rounded">
                                <Folder className="w-3.5 h-3.5 text-primary" />
                            </div>
                            <span className="text-xs font-bold truncate" title={explorerRootPath}>
                                {explorerRootPath.split('/').pop()}
                            </span>
                        </>
                    ) : (
                        <span className="text-xs text-muted-foreground italic pl-1">No Project Open</span>
                    )}
                </div>

                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-6 w-6">
                            <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                        <DropdownMenuItem onClick={handleOpenProject}>
                            <Folder className="w-4 h-4 mr-2" />
                            Open Project...
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={refreshFiles} disabled={!explorerRootPath}>
                            <RefreshCw className="w-4 h-4 mr-2" />
                            Refresh Files
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => setExplorerRootPath(null)} disabled={!explorerRootPath} className="text-red-500">
                            <X className="w-4 h-4 mr-2" />
                            Close Project
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>

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
                            onRename={handleRename}
                        />
                    ))
                ) : (
                    <div className="flex flex-col items-center justify-center h-full opacity-50 gap-2">
                        {!explorerRootPath ? (
                            <>
                                <p className="text-xs text-muted-foreground">No folder opened.</p>
                                <Button size="sm" variant="outline" onClick={handleOpenProject}>Open Folder</Button>
                            </>
                        ) : (
                            isAnalyzing ? (
                                <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                            ) : (
                                <p className="text-xs text-muted-foreground">No files found</p>
                            )
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};


