import React, { useState } from 'react';
import axios from 'axios';
import { useAppStore } from '@/store';
import {
    FileCode, Folder, ChevronRight, ChevronDown, FileText, File,
    Plus, Github, Loader2, RefreshCw, X, MoreHorizontal,
    FilePlus, FolderPlus, Copy, Scissors, Clipboard, Trash2,
    ExternalLink, Terminal as TerminalIcon
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { API_BASE } from '@/lib/api';
import {
    ContextMenu,
    ContextMenuContent,
    ContextMenuItem,
    ContextMenuSeparator,
    ContextMenuTrigger,
} from "@/components/ui/context-menu";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
    DropdownMenuSub,
    DropdownMenuSubTrigger,
    DropdownMenuSubContent,
    DropdownMenuPortal,
} from "@/components/ui/dropdown-menu";

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
    onRename: (path: string, newName: string) => void;
    onRefresh: () => void;
    onAction: (action: string, path: string, type?: 'file' | 'folder') => void;
}> = ({ item, level, expandedFolders, toggleFolder, onSelect, selectedPath, onRename, onRefresh, onAction }) => {
    const { clipboard, setClipboard, explorerRootPath } = useAppStore();
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
            case 'new-file':
                onAction('create-file', item.path);
                break;
            case 'new-folder':
                onAction('create-folder', item.path);
                break;
            case 'cut':
                setClipboard({ type: 'cut', path: item.path });
                break;
            case 'copy':
                setClipboard({ type: 'copy', path: item.path });
                break;
            case 'paste':
                onAction('paste', item.path);
                break;
            case 'copy-relative-path':
                if (explorerRootPath) {
                    const relative = item.path.replace(explorerRootPath, '').replace(/^\/+/, '');
                    navigator.clipboard.writeText(relative);
                }
                break;
            case 'copy-absolute-path':
                navigator.clipboard.writeText(item.path);
                break;
            case 'rename':
                setIsRenaming(true);
                break;
            case 'reveal':
                window.electronAPI.send('shell:reveal', item.path);
                break;
            case 'terminal':
                window.electronAPI.send('terminal:create', { cwd: isFolder ? item.path : item.path.split('/').slice(0, -1).join('/') });
                break;
            case 'delete':
                if (confirm(`Are you sure you want to delete ${item.name}?`)) {
                    window.electronAPI.invoke('fs:delete', item.path).then((res: any) => {
                        if (res.success) onRefresh();
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
                            level > 0 && "ml-3",
                            clipboard?.path === item.path && "opacity-50 grayscale-[0.5]"
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
            <ContextMenuContent className="w-56">
                {isFolder && (
                    <>
                        <ContextMenuItem onClick={() => handleContextMenuAction('new-file')}>
                            <FilePlus className="w-4 h-4 mr-2 text-muted-foreground" />
                            New File
                        </ContextMenuItem>
                        <ContextMenuItem onClick={() => handleContextMenuAction('new-folder')}>
                            <FolderPlus className="w-4 h-4 mr-2 text-muted-foreground" />
                            New Folder
                        </ContextMenuItem>
                        <ContextMenuSeparator />
                    </>
                )}

                <ContextMenuItem onClick={() => handleContextMenuAction('cut')}>
                    <Scissors className="w-4 h-4 mr-2 text-muted-foreground" />
                    Cut
                </ContextMenuItem>
                <ContextMenuItem onClick={() => handleContextMenuAction('copy')}>
                    <Copy className="w-4 h-4 mr-2 text-muted-foreground" />
                    Copy
                </ContextMenuItem>
                <ContextMenuItem onClick={() => handleContextMenuAction('paste')} disabled={!clipboard}>
                    <Clipboard className="w-4 h-4 mr-2 text-muted-foreground" />
                    Paste
                </ContextMenuItem>
                <ContextMenuSeparator />

                <ContextMenuItem onClick={() => handleContextMenuAction('copy-relative-path')}>
                    Copy Relative Path
                </ContextMenuItem>
                <ContextMenuItem onClick={() => handleContextMenuAction('copy-absolute-path')}>
                    Copy Absolute Path
                </ContextMenuItem>
                <ContextMenuSeparator />

                {isFolder && (
                    <ContextMenuItem onClick={() => handleContextMenuAction('terminal')}>
                        <TerminalIcon className="w-4 h-4 mr-2 text-muted-foreground" />
                        Open in Terminal
                    </ContextMenuItem>
                )}
                <ContextMenuItem onClick={() => handleContextMenuAction('reveal')}>
                    <ExternalLink className="w-4 h-4 mr-2 text-muted-foreground" />
                    Locate on Computer
                </ContextMenuItem>
                <ContextMenuSeparator />

                <ContextMenuItem onClick={() => handleContextMenuAction('rename')}>
                    Rename
                </ContextMenuItem>
                <ContextMenuItem onClick={() => handleContextMenuAction('delete')} className="text-red-500">
                    <Trash2 className="w-4 h-4 mr-2" />
                    Delete
                </ContextMenuItem>
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
                            onRefresh={onRefresh}
                            onAction={onAction}
                        />
                    ))}
                </div>
            )}
        </ContextMenu>
    );
};

export const ExplorerPanel: React.FC = () => {
    const {
        explorerRootPath, setExplorerRootPath,
        recentProjects,
        explorerFiles, setExplorerFiles,
        isAnalyzing, setIsAnalyzing,
        setFlowData, addToHistory,
        openDocument,
        activeDocumentId,
        clipboard, setClipboard
    } = useAppStore();

    const [isExpanded, setIsExpanded] = useState<Record<string, boolean>>({});
    const [creating, setCreating] = useState<{ parentPath: string; type: 'file' | 'folder' } | null>(null);
    const [creationValue, setCreationValue] = useState('');
    const creationInputRef = React.useRef<HTMLInputElement>(null);

    // Auto-load files on mount/change of root path
    React.useEffect(() => {
        if (explorerRootPath) {
            // Give backend some time to warm up if this is a fresh start/reload
            const timer = setTimeout(() => {
                refreshFiles();
            }, 2000);
            return () => clearTimeout(timer);
        }
    }, [explorerRootPath]);

    React.useEffect(() => {
        if (creating && creationInputRef.current) {
            creationInputRef.current.focus();
        }
    }, [creating]);

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

    const handleAction = async (action: string, path: string) => {
        switch (action) {
            case 'create-file':
                setCreating({ parentPath: path, type: 'file' });
                setIsExpanded(prev => ({ ...prev, [path]: true }));
                break;
            case 'create-folder':
                setCreating({ parentPath: path, type: 'folder' });
                setIsExpanded(prev => ({ ...prev, [path]: true }));
                break;
            case 'paste':
                if (clipboard) {
                    const dest = path + '/' + clipboard.path.split('/').pop();
                    let res;
                    if (clipboard.type === 'cut') {
                        res = await window.electronAPI.invoke('fs:move', { src: clipboard.path, dest });
                        setClipboard(null);
                    } else {
                        res = await window.electronAPI.invoke('fs:copy', { src: clipboard.path, dest });
                    }
                    if (res.success) refreshFiles();
                    else alert('Paste failed: ' + res.error);
                }
                break;
        }
    };

    const handleCreationSubmit = async () => {
        if (!creating || !creationValue.trim()) {
            setCreating(null);
            setCreationValue('');
            return;
        }

        const targetPath = creating.parentPath + '/' + creationValue.trim();
        try {
            const res = await window.electronAPI.invoke('fs:create', {
                type: creating.type,
                path: targetPath
            });
            if (res.success) {
                refreshFiles();
            } else {
                alert('Creation failed: ' + res.error);
            }
        } catch (e) {
            console.error('Creation failed', e);
        } finally {
            setCreating(null);
            setCreationValue('');
        }
    };

    const handleOpenProject = async () => {
        console.log('[Explorer] Initiating Open Project dialog...');
        try {
            setIsAnalyzing(true);
            const path = await window.electronAPI.invoke('dialog:openDirectory');
            console.log('[Explorer] Open Project dialog result:', path);
            if (path) {
                setExplorerRootPath(path);
                addToHistory({ name: path.split('/').pop() || path, path: path, type: 'local' });
            }
        } catch (error) {
            console.error('[Explorer] Open Project failed:', error);
            alert('Failed to open project: ' + (error as Error).message);
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
    };

    const renderCreationInput = (parentPath: string, level: number) => {
        if (!creating || creating.parentPath !== parentPath) return null;

        return (
            <div
                className="flex items-center gap-1.5 py-1 px-2 mx-1"
                style={{ paddingLeft: `${Math.max(4, (level + 1) * 12)}px` }}
            >
                <div className="shrink-0 flex items-center justify-center w-4 h-4">
                    {creating.type === 'folder' ? <Folder className="w-3.5 h-3.5 text-muted-foreground" /> : <File className="w-3.5 h-3.5 text-muted-foreground" />}
                </div>
                <input
                    ref={creationInputRef}
                    type="text"
                    value={creationValue}
                    onChange={(e) => setCreationValue(e.target.value)}
                    onBlur={handleCreationSubmit}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') handleCreationSubmit();
                        if (e.key === 'Escape') {
                            setCreating(null);
                            setCreationValue('');
                        }
                    }}
                    className="flex-1 bg-background border border-primary h-6 text-xs px-1 outline-none"
                    placeholder={`New ${creating.type}...`}
                />
            </div>
        );
    };

    const renderTree = (nodes: any[], level = 0) => {
        return nodes.map((node) => (
            <React.Fragment key={node.path}>
                <FileTreeItem
                    item={node}
                    level={level}
                    expandedFolders={isExpanded}
                    toggleFolder={toggleFolder}
                    onSelect={handleFileClick}
                    selectedPath={activeDocumentId}
                    onRename={handleRename}
                    onRefresh={refreshFiles}
                    onAction={handleAction}
                />
                {isExpanded[node.path] && node.type === 'folder' && renderCreationInput(node.path, level)}
            </React.Fragment>
        ));
    };

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground overflow-hidden">
            {/* Header */}
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

                <div className="flex items-center gap-0.5">
                    {explorerRootPath && (
                        <>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6"
                                onClick={() => handleAction('create-file', explorerRootPath)}
                                title="New File"
                            >
                                <FilePlus className="w-3.5 h-3.5" />
                            </Button>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6"
                                onClick={() => handleAction('create-folder', explorerRootPath)}
                                title="New Folder"
                            >
                                <FolderPlus className="w-3.5 h-3.5" />
                            </Button>
                        </>
                    )}
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
                            {explorerRootPath && (
                                <DropdownMenuItem onClick={() => window.electronAPI.send('terminal:create', { cwd: explorerRootPath })}>
                                    <TerminalIcon className="w-4 h-4 mr-2" />
                                    Open in Terminal
                                </DropdownMenuItem>
                            )}
                            {recentProjects.length > 0 && (
                                <DropdownMenuSub>
                                    <DropdownMenuSubTrigger>
                                        <RefreshCw className="w-4 h-4 mr-2" />
                                        Recent Projects
                                    </DropdownMenuSubTrigger>
                                    <DropdownMenuPortal>
                                        <DropdownMenuSubContent className="w-64">
                                            {recentProjects.map((projPath) => (
                                                <DropdownMenuItem
                                                    key={projPath}
                                                    onClick={() => setExplorerRootPath(projPath)}
                                                >
                                                    <Folder className="w-3.5 h-3.5 mr-2 opacity-50" />
                                                    <span className="truncate">{projPath.split('/').pop() || projPath}</span>
                                                </DropdownMenuItem>
                                            ))}
                                        </DropdownMenuSubContent>
                                    </DropdownMenuPortal>
                                </DropdownMenuSub>
                            )}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => setExplorerRootPath(null)} disabled={!explorerRootPath} className="text-red-500">
                                <X className="w-4 h-4 mr-2" />
                                Close Project
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>

            {/* File List */}
            <div className="flex-1 overflow-y-auto px-0 py-2 custom-scrollbar">
                {explorerFiles.length > 0 ? (
                    <>
                        {renderTree(explorerFiles)}
                        {renderCreationInput(explorerRootPath!, -1)}
                    </>
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
                                <div className="flex flex-col items-center gap-2">
                                    <p className="text-xs text-muted-foreground">No files found</p>
                                    <Button size="sm" variant="ghost" onClick={() => handleAction('create-file', explorerRootPath)}>
                                        <FilePlus className="w-3.5 h-3.5 mr-2" /> Create First File
                                    </Button>
                                </div>
                            )
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
