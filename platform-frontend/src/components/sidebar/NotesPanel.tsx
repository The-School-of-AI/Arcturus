import React, { useEffect, useState, useMemo } from 'react';
import { FileText, File, Folder, ChevronRight, ChevronDown, FolderPlus, Plus, Trash2, Search, Loader2, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useAppStore } from '@/store';
import { API_BASE } from '@/lib/api';
// Context menu removed due to missing component


import {
    ContextMenu,
    ContextMenuContent,
    ContextMenuItem,
    ContextMenuSeparator,
    ContextMenuTrigger,
} from "@/components/ui/context-menu";

interface NoteItem {
    name: string;
    path: string;
    type: string;
    children?: NoteItem[];
}

const NoteTreeItem: React.FC<{
    item: NoteItem;
    level: number;
    onSelect: (item: NoteItem) => void;
    selectedPath: string | undefined;
    onDelete: (path: string) => void;
    onRename: (path: string, newName: string) => void;
    onAction: (action: string, path: string, type: string) => void;
    expandedFolders: string[];
    toggleFolder: (path: string) => void;
    onRefresh: () => void;
}> = ({ item, level, onSelect, selectedPath, onDelete, onRename, onAction, expandedFolders, toggleFolder, onRefresh }) => {
    const { clipboard, setClipboard } = useAppStore();
    const isFolder = item.type === 'folder';
    const isOpen = expandedFolders.includes(item.path);
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
        }
        onSelect(item);
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

    const handleContextMenuAction = async (action: string) => {
        switch (action) {
            case 'cut':
                setClipboard({ type: 'cut', path: item.path });
                break;
            case 'copy':
                setClipboard({ type: 'copy', path: item.path });
                break;
            case 'paste':
                onAction('paste', item.path, item.type);
                break;
            case 'copy-relative-path':
                navigator.clipboard.writeText(item.path);
                break;
            case 'copy-absolute-path':
                try {
                    const res = await axios.get(`${API_BASE}/rag/absolute_path`, { params: { path: item.path } });
                    if (res.data.absolute_path) {
                        navigator.clipboard.writeText(res.data.absolute_path);
                    }
                } catch (e) {
                    console.error("Failed to get absolute path", e);
                }
                break;
            case 'rename':
                setIsRenaming(true);
                break;
            case 'reveal':
                try {
                    const res = await axios.get(`${API_BASE}/rag/absolute_path`, { params: { path: item.path } });
                    if (res.data.absolute_path) {
                        window.electronAPI.send('shell:reveal', res.data.absolute_path);
                    }
                } catch (e) {
                    console.error("Failed to reveal item", e);
                }
                break;
            case 'delete':
                onDelete(item.path);
                break;
        }
    };

    const getIcon = () => {
        if (isFolder) return isOpen ? <ChevronDown className="w-4 h-4 text-yellow-500" /> : <ChevronRight className="w-4 h-4 text-yellow-500" />;
        return <FileText className="w-4 h-4 text-blue-400" />;
    };

    return (
        <ContextMenu>
            <ContextMenuTrigger disabled={isRenaming}>
                <div
                    className={cn(
                        "group relative flex items-center gap-1.5 py-1.5 px-3 transition-all duration-200 cursor-pointer select-none",
                        selectedPath === item.path
                            ? "bg-blue-500/10 text-blue-500 shadow-[inset_2px_0_0_0_#2b7fff]"
                            : "hover:bg-accent/30 text-muted-foreground hover:text-foreground",
                        clipboard?.path === item.path && "opacity-50 grayscale-[0.5]"
                    )}
                    style={{ paddingLeft: `${level * 12 + 12}px` }}
                    onClick={handleClick}
                >
                    {getIcon()}
                    <div className="flex-1 truncate text-xs font-medium">
                        {isRenaming ? (
                            <input
                                ref={inputRef}
                                type="text"
                                value={renameValue}
                                onChange={(e) => setRenameValue(e.target.value)}
                                onBlur={handleRenameSubmit}
                                onKeyDown={handleKeyDown}
                                onClick={(e) => e.stopPropagation()}
                                className="w-full bg-background border border-primary h-5 text-xs px-1 outline-none"
                            />
                        ) : (
                            item.name
                        )}
                    </div>
                    {/* Delete button appears on hover or selection */}
                    <div
                        className={cn("opacity-0 group-hover:opacity-100 flex items-center bg-background/50 rounded p-0.5", selectedPath === item.path && "opacity-100")}
                        onClick={(e) => { e.stopPropagation(); onDelete(item.path); }}
                    >
                        <Trash2 className="w-3 h-3 hover:text-red-500" />
                    </div>
                </div>
            </ContextMenuTrigger>
            <ContextMenuContent className="w-56">
                <ContextMenuItem onClick={() => handleContextMenuAction('cut')}>
                    Cut
                </ContextMenuItem>
                <ContextMenuItem onClick={() => handleContextMenuAction('copy')}>
                    Copy
                </ContextMenuItem>
                <ContextMenuItem onClick={() => handleContextMenuAction('paste')} disabled={!clipboard}>
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
                <ContextMenuItem onClick={() => handleContextMenuAction('reveal')}>
                    Locate on Computer
                </ContextMenuItem>
                <ContextMenuItem onClick={() => handleContextMenuAction('rename')}>
                    Rename
                </ContextMenuItem>
                <ContextMenuItem onClick={() => handleContextMenuAction('delete')} className="text-red-500 hover:text-red-500">
                    Delete
                </ContextMenuItem>
            </ContextMenuContent>

            {isFolder && isOpen && item.children && (
                <div>
                    {item.children.map((child) => (
                        <NoteTreeItem
                            key={child.path}
                            item={child}
                            level={level + 1}
                            onSelect={onSelect}
                            selectedPath={selectedPath}
                            onDelete={onDelete}
                            onRename={onRename}
                            onAction={onAction}
                            expandedFolders={expandedFolders}
                            toggleFolder={toggleFolder}
                            onRefresh={onRefresh}
                        />
                    ))}
                </div>
            )}
        </ContextMenu>
    );
};

export const NotesPanel: React.FC = () => {
    const {
        setActiveNotesDocument,
        notesActiveDocumentId,
        openNotesDocument,
        notesFiles,
        fetchNotesFiles,
        isNotesLoading,
        expandedNotesFolders,
        toggleNoteFolder,
        clipboard,
        setClipboard
    } = useAppStore();

    const [searchQuery, setSearchQuery] = useState("");

    // Dialog States
    const [isNewFolderOpen, setIsNewFolderOpen] = useState(false);
    const [newFolderName, setNewFolderName] = useState("");
    const [isNewNoteOpen, setIsNewNoteOpen] = useState(false);
    const [newNoteName, setNewNoteName] = useState("");

    const [selectedItem, setSelectedItem] = useState<NoteItem | null>(null);
    const [grepResults, setGrepResults] = useState<any[]>([]);
    const [isSearching, setIsSearching] = useState(false);

    useEffect(() => {
        fetchNotesFiles();
    }, []);

    const handleCreateFolder = async () => {
        if (!newFolderName.trim()) return;

        // Determine parent path: if selectedItem is folder, put inside, else put in root of Notes
        let parentPath = "Notes";
        if (selectedItem?.type === 'folder') {
            // Removing "Notes/" prefix might be needed if API expects relative to data root?
            // API expects path relative to data root.
            // selectedItem.path is typically "Notes/Subfolder"
            parentPath = selectedItem.path;
        } else if (selectedItem?.type !== 'folder' && selectedItem?.path.includes('/')) {
            // Sibling
            const parts = selectedItem.path.split('/');
            parts.pop();
            parentPath = parts.join('/');
        }

        const fullPath = `${parentPath}/${newFolderName}`;

        try {
            await axios.post(`${API_BASE}/rag/create_folder`, null, { params: { folder_path: fullPath } });
            setIsNewFolderOpen(false);
            setNewFolderName("");
            fetchNotesFiles();
        } catch (e) { alert("Failed to create folder"); }
    };

    const handleCreateNote = async () => {
        if (!newNoteName.trim()) return;

        let parentPath = "Notes";
        if (selectedItem?.type === 'folder') {
            parentPath = selectedItem.path;
        } else if (selectedItem?.type !== 'folder' && selectedItem?.path.includes('/')) {
            const parts = selectedItem.path.split('/');
            parts.pop();
            parentPath = parts.join('/');
        }

        let fileName = newNoteName;
        if (!fileName.endsWith('.md')) fileName += '.md';

        const fullPath = `${parentPath}/${fileName}`;

        try {
            const formData = new FormData();
            formData.append('path', fullPath);
            formData.append('content', "# " + newNoteName);

            await axios.post(`${API_BASE}/rag/create_file`, formData, {
                headers: { "Content-Type": "multipart/form-data" }
            });
            setIsNewNoteOpen(false);
            setNewNoteName("");
            await fetchNotesFiles();

            // Open it
            openNotesDocument({
                id: fullPath,
                title: fileName,
                type: 'md'
            });
        } catch (e) { alert("Failed to create note"); }
    };

    const handleDelete = async (path: string) => {
        if (!confirm(`Are you sure you want to delete ${path}?`)) return;
        try {
            const formData = new FormData();
            formData.append('path', path);
            await axios.post(`${API_BASE}/rag/delete`, formData);
            fetchNotesFiles();
        } catch (e) { alert("Failed to delete item"); }
    };

    // Recursive search logic
    const filterNodes = (nodes: NoteItem[], query: string): NoteItem[] => {
        if (!query) return nodes;
        return nodes.reduce((acc: NoteItem[], node) => {
            const matches = node.name.toLowerCase().includes(query.toLowerCase());
            if (node.type === 'folder' && node.children) {
                const filteredChildren = filterNodes(node.children, query);
                if (matches || filteredChildren.length > 0) {
                    acc.push({ ...node, children: filteredChildren });
                }
            } else if (matches) {
                acc.push(node);
            }
            return acc;
        }, []);
    };

    // Debounced search
    useEffect(() => {
        if (!searchQuery.trim()) {
            setGrepResults([]);
            setIsSearching(false);
            return;
        }

        const timer = setTimeout(async () => {
            setIsSearching(true);
            try {
                const res = await axios.get(`${API_BASE}/rag/ripgrep_search`, {
                    params: {
                        query: searchQuery,
                        target_dir: "Notes"
                    }
                });

                const results = res.data?.results || [];
                const seen = new Set();
                const filtered = results.filter((r: any) => {
                    if (seen.has(r.file)) return false;
                    seen.add(r.file);
                    return true;
                });
                setGrepResults(filtered);
            } catch (e) {
                console.error("Search failed", e);
            } finally {
                setIsSearching(false);
            }
        }, 400);

        return () => clearTimeout(timer);
    }, [searchQuery]);

    const displayedFiles = useMemo(() => filterNodes(notesFiles, searchQuery), [notesFiles, searchQuery]);

    const handleRename = async (path: string, newName: string) => {
        const oldPath = path;
        const newPath = path.substring(0, path.lastIndexOf('/')) + '/' + newName;
        try {
            const formData = new FormData();
            formData.append('old_path', oldPath);
            formData.append('new_path', newPath);
            await axios.post(`${API_BASE}/rag/rename`, formData);
            fetchNotesFiles();
        } catch (e) {
            console.error("Rename failed", e);
            alert("Rename failed");
        }
    };

    const handleAction = async (action: string, targetPath: string, targetType: string) => {
        if (action === 'paste' && clipboard) {
            // If target is a folder, paste inside. If file, paste as sibling.
            let parentDir = targetPath;
            if (targetType !== 'folder') {
                const parts = targetPath.split('/');
                parts.pop();
                parentDir = parts.join('/');
            }

            const dest = `${parentDir}/${clipboard.path.split('/').pop()}`;

            const endpoint = clipboard.type === 'cut' ? '/rag/move' : '/rag/copy';
            try {
                const formData = new FormData();
                formData.append('src', clipboard.path);
                formData.append('dest', dest);
                await axios.post(`${API_BASE}${endpoint}`, formData);
                if (clipboard.type === 'cut') setClipboard(null);
                fetchNotesFiles();
            } catch (e) {
                console.error("Paste failed", e);
                alert("Paste failed");
            }
        }
    };

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground">
            {/* Header */}
            <div className="p-2 border-b border-border/50 bg-muted/20 flex items-center gap-1.5 shrink-0">
                {/* Search */}
                <div className="relative flex-1 group">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    <Input
                        className="w-full bg-background/50 border-transparent focus:bg-background focus:border-border rounded-md text-xs pl-8 pr-2 h-8 transition-all placeholder:text-muted-foreground"
                        placeholder="Search notes..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>

                <div className="flex items-center">
                    <Dialog open={isNewNoteOpen} onOpenChange={setIsNewNoteOpen}>
                        <DialogTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-background/80" title="New Note">
                                <Plus className="w-4 h-4" />
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader><DialogTitle>Create New Note</DialogTitle></DialogHeader>
                            <Input placeholder="Note Name" value={newNoteName} onChange={e => setNewNoteName(e.target.value)} autoFocus onKeyDown={e => e.key === 'Enter' && handleCreateNote()} />
                            <DialogFooter><Button onClick={handleCreateNote}>Create</Button></DialogFooter>
                        </DialogContent>
                    </Dialog>

                    <Dialog open={isNewFolderOpen} onOpenChange={setIsNewFolderOpen}>
                        <DialogTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-background/80" title="New Folder">
                                <FolderPlus className="w-4 h-4" />
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader><DialogTitle>Create New Folder</DialogTitle></DialogHeader>
                            <Input placeholder="Folder Name" value={newFolderName} onChange={e => setNewFolderName(e.target.value)} autoFocus onKeyDown={e => e.key === 'Enter' && handleCreateFolder()} />
                            <DialogFooter><Button onClick={handleCreateFolder}>Create</Button></DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>

            {/* File Tree or Search Results */}
            <div className="flex-1 overflow-y-auto p-2 scrollbar-hide">
                {isNotesLoading ? (
                    <div className="flex items-center justify-center h-20 text-muted-foreground/50">
                        <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading...
                    </div>
                ) : isSearching ? (
                    <div className="flex items-center justify-center h-20 text-muted-foreground/50">
                        <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Searching...
                    </div>
                ) : searchQuery.trim() ? (
                    grepResults.length === 0 ? (
                        <div className="flex flex-col items-center justify-center gap-2 p-8 text-muted-foreground/50">
                            <Search className="w-8 h-8 opacity-20" />
                            <span className="text-xs">No matches found</span>
                        </div>
                    ) : (
                        <div className="space-y-1.5">
                            {grepResults.map((res, i) => (
                                <div
                                    key={i}
                                    className={cn(
                                        "group relative p-2.5 rounded-lg border border-border/40 hover:border-primary/40 hover:bg-primary/5 transition-all duration-200 cursor-pointer overflow-hidden bg-card/10"
                                    )}
                                    onClick={() => openNotesDocument({
                                        id: res.file.startsWith('Notes/') ? res.file : `Notes/${res.file}`,
                                        title: (res.file || '').split('/').pop() || 'note',
                                        type: 'md',
                                        targetLine: res.line,
                                        searchText: res.content
                                    })}
                                >
                                    <div className="flex items-center justify-between mb-1">
                                        <div className="flex items-center gap-1.5 truncate flex-1">
                                            <FileText className="w-3 h-3 text-blue-400/70" />
                                            <span className="text-[10px] font-bold text-muted-foreground truncate">{res.file.replace(/^Notes\//, '')}</span>
                                        </div>
                                        <span className="text-[9px] font-mono bg-muted px-1 rounded text-muted-foreground shrink-0">L{res.line}</span>
                                    </div>
                                    <div className="text-[10px] text-foreground/80 font-mono line-clamp-2 break-all opacity-80 group-hover:opacity-100">
                                        {res.content}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )
                ) : displayedFiles.length === 0 ? (
                    <div className="flex flex-col items-center justify-center gap-2 p-8 text-muted-foreground/50">
                        <FileText className="w-8 h-8 opacity-20" />
                        <span className="text-xs">No notes found</span>
                    </div>
                ) : (
                    displayedFiles.map((item) => (
                        <NoteTreeItem
                            key={item.path}
                            item={item}
                            level={0}
                            onSelect={(item) => {
                                setSelectedItem(item);
                                if (item.type !== 'folder') {
                                    openNotesDocument({
                                        id: item.path,
                                        title: item.name,
                                        type: item.type
                                    });
                                }
                            }}
                            selectedPath={notesActiveDocumentId || selectedItem?.path}
                            onDelete={handleDelete}
                            onRename={handleRename}
                            onAction={handleAction}
                            expandedFolders={expandedNotesFolders}
                            toggleFolder={toggleNoteFolder}
                            onRefresh={fetchNotesFiles}
                        />
                    ))
                )}
            </div>
        </div>
    );
};
