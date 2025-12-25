import React, { useState, useMemo, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Check, Search, FileCode, FileImage, FileText, Database, ShieldAlert, BadgeInfo } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

interface ScannedFile {
    path: string;
    size: number;
    lines: number;
    type: 'code' | 'binary' | 'asset';
    extension: string;
}

interface FileSelectionModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (selectedPaths: string[]) => void;
    files: ScannedFile[];
    rootPath: string;
}

export const FileSelectionModal: React.FC<FileSelectionModalProps> = ({ isOpen, onClose, onConfirm, files, rootPath }) => {
    const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
    const [searchQuery, setSearchQuery] = useState('');

    // Initial Auto-Select Logic
    useEffect(() => {
        if (isOpen && files.length > 0) {
            const initialSet = new Set<string>();
            files.forEach(f => {
                // Auto-select code files < 500 lines, not binary
                if (f.type === 'code' && f.lines < 500 && f.lines > 0) {
                    initialSet.add(f.path);
                }
            });
            setSelectedPaths(initialSet);
        }
    }, [isOpen, files]);

    const filteredFiles = useMemo(() => {
        if (!searchQuery) return files;
        return files.filter(f => f.path.toLowerCase().includes(searchQuery.toLowerCase()));
    }, [files, searchQuery]);

    const stats = useMemo(() => {
        let count = 0;
        let tokens = 0;
        let size = 0;

        files.forEach(f => {
            if (selectedPaths.has(f.path)) {
                count++;
                size += f.size;
                // Rough token estimation: 1 token ~= 4 chars or 1 line ~= 10 tokens avg code
                tokens += f.lines * 8;
            }
        });
        return { count, tokens, size };
    }, [selectedPaths, files]);

    const toggleFile = (path: string) => {
        const newSet = new Set(selectedPaths);
        if (newSet.has(path)) {
            newSet.delete(path);
        } else {
            newSet.add(path);
        }
        setSelectedPaths(newSet);
    };

    const toggleAll = () => {
        if (selectedPaths.size === filteredFiles.length) {
            setSelectedPaths(new Set());
        } else {
            const newSet = new Set<string>();
            filteredFiles.forEach(f => {
                if (f.type !== 'binary') newSet.add(f.path);
            });
            setSelectedPaths(newSet);
        }
    };

    const formatSize = (bytes: number) => {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    };

    const getIcon = (type: string) => {
        switch (type) {
            case 'code': return <FileCode className="w-3.5 h-3.5 text-blue-400" />;
            case 'binary': return <Database className="w-3.5 h-3.5 text-orange-400" />;
            case 'asset': return <FileImage className="w-3.5 h-3.5 text-purple-400" />;
            default: return <FileText className="w-3.5 h-3.5 text-gray-400" />;
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-4xl h-[80vh] bg-charcoal-900 border-white/10 flex flex-col p-0 gap-0 overflow-hidden">
                {/* Header */}
                <DialogHeader className="p-6 pb-4 border-b border-white/10 bg-charcoal-800/50">
                    <DialogTitle className="flex items-center justify-between">
                        <div className="flex flex-col gap-1">
                            <span className="text-lg font-bold text-white tracking-tight">Select Context for Analysis</span>
                            <span className="text-xs font-mono text-gray-500">{rootPath}</span>
                        </div>
                        <div className="flex items-center gap-4 text-xs font-mono bg-black/40 px-3 py-1.5 rounded-lg border border-white/5">
                            <span className={cn(stats.tokens > 1000000 ? "text-red-400 animate-pulse" : "text-neon-yellow")}>
                                ~{Math.round(stats.tokens / 1000)}k Tokens
                            </span>
                            <span className="text-gray-500">|</span>
                            <span>{stats.count} Files</span>
                            <span className="text-gray-500">|</span>
                            <span>{formatSize(stats.size)}</span>
                        </div>
                    </DialogTitle>
                </DialogHeader>

                {/* Toolbar */}
                <div className="flex items-center gap-3 p-3 px-6 bg-charcoal-900 border-b border-white/5">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
                        <input
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Filter files..."
                            className="w-full bg-white/5 border border-white/10 rounded-md py-1.5 pl-9 pr-3 text-xs text-gray-200 focus:outline-none focus:border-neon-yellow/50 transition-all font-mono"
                        />
                    </div>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={toggleAll}
                        className="text-[10px] uppercase font-bold tracking-wider text-gray-400 hover:text-white"
                    >
                        {selectedPaths.size === filteredFiles.length ? "Select None" : "Select All"}
                    </Button>
                </div>

                {/* File List */}
                <ScrollArea className="flex-1 bg-charcoal-950/50">
                    <div className="p-2 space-y-0.5">
                        {filteredFiles.map((file) => {
                            const isSelected = selectedPaths.has(file.path);
                            const isLarge = file.lines > 1000;
                            const isBinary = file.type === 'binary';

                            return (
                                <div
                                    key={file.path}
                                    onClick={() => !isBinary && toggleFile(file.path)}
                                    className={cn(
                                        "flex items-center gap-3 p-2 rounded-md cursor-pointer transition-all hover:bg-white/5 border border-transparent font-mono",
                                        isSelected ? "bg-neon-yellow/5 border-neon-yellow/10" : "opacity-70 hover:opacity-100",
                                        isBinary && "opacity-40 cursor-not-allowed grayscale hover:bg-transparent"
                                    )}
                                >
                                    <div className={cn(
                                        "w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors",
                                        isSelected ? "bg-neon-yellow border-neon-yellow" : "border-white/20 bg-transparent",
                                        isBinary && "border-white/5 bg-white/5"
                                    )}>
                                        {isSelected && <Check className="w-3 h-3 text-black stroke-[3]" />}
                                    </div>

                                    <div className="flex items-center gap-2 flex-1 min-w-0">
                                        {getIcon(file.type)}
                                        <span className={cn(
                                            "text-xs truncate",
                                            isSelected ? "text-white font-medium" : "text-gray-400"
                                        )}>
                                            {file.path}
                                        </span>
                                    </div>

                                    {/* Warnings / Badges */}
                                    <div className="flex items-center gap-3 shrink-0">
                                        {isLarge && (
                                            <span className="flex items-center gap-1 text-[10px] text-amber-500/80 bg-amber-500/10 px-1.5 py-0.5 rounded">
                                                <BadgeInfo className="w-3 h-3" />
                                                Large
                                            </span>
                                        )}
                                        {isBinary && (
                                            <span className="text-[10px] text-gray-600 italic px-2">Binary</span>
                                        )}

                                        <div className="w-20 text-right text-[10px] text-gray-500">
                                            {file.lines > 0 ? `${file.lines} lines` : ''}
                                        </div>
                                        <div className="w-16 text-right text-[10px] text-gray-600">
                                            {formatSize(file.size)}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </ScrollArea>

                {/* Footer */}
                <DialogFooter className="p-4 border-t border-white/10 bg-charcoal-900 gap-3">
                    <div className="flex-1 text-[10px] text-gray-500 italic flex items-center gap-2">
                        <ShieldAlert className="w-3 h-3 text-amber-500" />
                        Gemini 1.5 Pro Context Window: ~1M Tokens. Select wisely.
                    </div>
                    <Button variant="ghost" onClick={onClose} className="rounded-xl">Cancel</Button>
                    <Button
                        onClick={() => onConfirm(Array.from(selectedPaths))}
                        disabled={selectedPaths.size === 0}
                        className="bg-neon-yellow text-black hover:bg-neon-yellow/80 rounded-xl px-8 font-bold tracking-wide"
                    >
                        ANALYZE CONTEXT
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
