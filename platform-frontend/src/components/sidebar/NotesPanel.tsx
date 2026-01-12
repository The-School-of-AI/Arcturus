import React, { useEffect, useState, useMemo } from 'react';
import { FileText, File, Folder, ChevronRight, ChevronDown, FolderPlus, Plus, Trash2, Search, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useAppStore } from '@/store';
import { API_BASE } from '@/lib/api';
// Context menu removed due to missing component


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
}> = ({ item, level, onSelect, selectedPath, onDelete }) => {
    const [isOpen, setIsOpen] = useState(false);
    const isFolder = item.type === 'folder';

    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (isFolder) {
            setIsOpen(!isOpen);
        }
        onSelect(item);
    };

    const getIcon = () => {
        if (isFolder) return isOpen ? <ChevronDown className="w-4 h-4 text-yellow-500" /> : <ChevronRight className="w-4 h-4 text-yellow-500" />;
        return <FileText className="w-4 h-4 text-blue-400" />;
    };

    return (
        <div>
            <div
                className={cn(
                    "group relative flex items-center gap-1.5 py-1.5 px-3 transition-all duration-200 cursor-pointer select-none",
                    selectedPath === item.path
                        ? "bg-blue-500/10 text-blue-500 shadow-[inset_2px_0_0_0_#2b7fff]"
                        : "hover:bg-accent/30 text-muted-foreground hover:text-foreground",
                )}
                style={{ paddingLeft: `${level * 12 + 12}px` }}
                onClick={handleClick}
            >
                {getIcon()}
                <div className="flex-1 truncate text-xs font-medium">
                    {item.name}
                </div>
                {/* Delete button appears on hover or selection */}
                <div
                    className={cn("opacity-0 group-hover:opacity-100 flex items-center bg-background/50 rounded p-0.5", selectedPath === item.path && "opacity-100")}
                    onClick={(e) => { e.stopPropagation(); onDelete(item.path); }}
                >
                    <Trash2 className="w-3 h-3 hover:text-red-500" />
                </div>
            </div>

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
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

export const NotesPanel: React.FC = () => {
    const {
        setActiveDocument,
        activeDocumentId,
        openDocument,
        notesFiles,
        fetchNotesFiles,
        isNotesLoading
    } = useAppStore();

    const [searchQuery, setSearchQuery] = useState("");

    // Dialog States
    const [isNewFolderOpen, setIsNewFolderOpen] = useState(false);
    const [newFolderName, setNewFolderName] = useState("");
    const [isNewNoteOpen, setIsNewNoteOpen] = useState(false);
    const [newNoteName, setNewNoteName] = useState("");

    const [selectedItem, setSelectedItem] = useState<NoteItem | null>(null);

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
            openDocument({
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

    const displayedFiles = useMemo(() => filterNodes(notesFiles, searchQuery), [notesFiles, searchQuery]);

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground">
            {/* Header */}
            <div className="p-3 border-b border-border/50 bg-muted/20 space-y-3">
                <div className="flex items-center gap-2">
                    <Dialog open={isNewNoteOpen} onOpenChange={setIsNewNoteOpen}>
                        <DialogTrigger asChild>
                            <Button className="flex-1 gap-2 bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20 h-9 transition-all font-semibold text-xs">
                                <Plus className="w-3.5 h-3.5" /> New Note
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
                            <Button variant="outline" size="icon" className="h-9 w-9 border-border bg-background/50 hover:bg-accent hover:text-accent-foreground text-muted-foreground transition-all duration-200">
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

                {/* Search */}
                <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                    <Input
                        className="w-full bg-muted border border-border rounded-lg text-xs pl-8 pr-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary/50 text-foreground placeholder:text-muted-foreground transition-all h-auto"
                        placeholder="Search notes..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
            </div>

            {/* File Tree */}
            <div className="flex-1 overflow-y-auto p-2 scrollbar-hide">
                {isNotesLoading ? (
                    <div className="flex items-center justify-center h-20 text-muted-foreground/50">
                        <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading...
                    </div>
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
                                    openDocument({
                                        id: item.path,
                                        title: item.name,
                                        type: item.type
                                    });
                                }
                            }}
                            selectedPath={activeDocumentId || selectedItem?.path}
                            onDelete={handleDelete}
                        />
                    ))
                )}
            </div>
        </div>
    );
};
