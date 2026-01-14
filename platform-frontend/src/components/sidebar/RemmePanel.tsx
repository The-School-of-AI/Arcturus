import React, { useEffect, useState, useMemo } from 'react';
import { useAppStore } from '@/store';
import { Search, Brain, Trash2, Plus, AlertCircle, Edit2, TriangleAlert, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import axios from 'axios';
import { API_BASE } from '@/lib/api';

export const RemmePanel: React.FC = () => {
    const { memories, fetchMemories, addMemory, deleteMemory, cleanupDanglingMemories, isRemmeAddOpen: isAddOpen, setIsRemmeAddOpen: setIsAddOpen } = useAppStore();
    const [searchQuery, setSearchQuery] = useState("");
    const [newMemoryText, setNewMemoryText] = useState("");
    const [expandedMemoryId, setExpandedMemoryId] = useState<string | null>(null);

    useEffect(() => {
        fetchMemories();
    }, []);

    const filteredMemories = useMemo(() => {
        let items = [...memories];
        if (searchQuery.trim()) {
            items = items.filter(m =>
                m.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
                m.category.toLowerCase().includes(searchQuery.toLowerCase())
            );
        }
        // Sort newest first
        return items.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    }, [memories, searchQuery]);

    const danglingCount = useMemo(() => memories.filter(m => m.source_exists === false).length, [memories]);

    const handleAdd = async () => {
        if (!newMemoryText.trim()) return;
        await addMemory(newMemoryText);
        setNewMemoryText("");
        setIsAddOpen(false);
    };

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground">
            {/* Header & Search */}
            <div className="p-2 border-b border-border/50 bg-muted/20 flex items-center gap-1.5 shrink-0">
                <div className="relative flex-1 group">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    <Input
                        className="w-full bg-background/50 border-transparent focus:bg-background focus:border-border rounded-md text-xs pl-8 pr-2 h-8 transition-all placeholder:text-muted-foreground"
                        placeholder="Search your memories..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>

                <div className="flex items-center gap-1">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-background/80"
                        onClick={() => setIsAddOpen(!isAddOpen)}
                        title="Manual Add"
                    >
                        <Plus className="w-4 h-4" />
                    </Button>

                    <Button
                        variant="ghost"
                        size="icon"
                        disabled={danglingCount === 0}
                        className={cn(
                            "h-8 w-8 shrink-0",
                            danglingCount > 0
                                ? "text-orange-400 hover:text-orange-300 hover:bg-orange-400/10"
                                : "text-muted-foreground opacity-30 cursor-not-allowed"
                        )}
                        onClick={() => {
                            if (confirm(`Cleanup ${danglingCount} memories with missing source sessions?`)) {
                                cleanupDanglingMemories();
                            }
                        }}
                        title={danglingCount > 0 ? `Cleanup ${danglingCount} dangling memories` : "No dangling memories found"}
                    >
                        <TriangleAlert className="w-4 h-4" />
                    </Button>
                </div>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide">
                {filteredMemories.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20 px-8 text-center space-y-4 opacity-30">
                        <div className="relative">
                            <Brain className="w-12 h-12 mx-auto" />
                            <Search className="w-6 h-6 absolute -bottom-1 -right-1" />
                        </div>
                        <p className="text-[10px] font-bold uppercase tracking-widest leading-relaxed">No matching memory patterns found in neural cache</p>
                    </div>
                ) : (
                    filteredMemories.map((memory) => {
                        const isExpanded = expandedMemoryId === memory.id;
                        return (
                            <div
                                key={memory.id}
                                onClick={() => setExpandedMemoryId(isExpanded ? null : memory.id)}
                                className={cn(
                                    "group relative p-4 rounded-xl border transition-all duration-300 cursor-pointer",
                                    "hover:shadow-md",
                                    memory.source_exists === false
                                        ? "border-orange-500/20 hover:border-orange-500/40 bg-orange-500/5 shadow-[0_0_15px_rgba(249,115,22,0.05)]"
                                        : "border-border/50 hover:border-primary/50 hover:bg-accent/50"
                                )}
                            >
                                <div className="flex justify-between items-start gap-4">
                                    <div className="flex-1 min-w-0">
                                        <p className={cn(
                                            "text-[13px] text-foreground/90 leading-relaxed font-normal selection:bg-neon-yellow/30 transition-all duration-300",
                                            isExpanded ? "" : "line-clamp-2"
                                        )}>
                                            {memory.text}
                                        </p>
                                    </div>
                                    <div className="flex flex-col gap-2 -mr-1">
                                        <button
                                            className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/10 rounded-lg text-muted-foreground hover:text-red-400 transition-all duration-200"
                                            onClick={() => deleteMemory(memory.id)}
                                            title="Forget this memory"
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>

                                        {memory.source_exists === false && (
                                            <div
                                                className="p-1.5 rounded-lg text-orange-500/60 animate-pulse bg-orange-500/5"
                                                title="Source session has been deleted"
                                            >
                                                <TriangleAlert className="w-3.5 h-3.5" />
                                            </div>
                                        )}
                                    </div>
                                </div>

                                <div className="mt-4 pt-3 border-t border-border/10 flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <div className={cn(
                                            "px-2 py-0.5 rounded-md text-[8px] uppercase font-black tracking-tight",
                                            memory.category === 'derived'
                                                ? "bg-purple-500/10 text-purple-400"
                                                : "bg-blue-500/10 text-blue-400"
                                        )}>
                                            {memory.category}
                                        </div>
                                        <span className="text-[9px] text-muted-foreground/50 font-mono">
                                            {formatDistanceToNow(new Date(memory.created_at))} ago
                                        </span>
                                    </div>
                                    <div className="text-[9px] text-muted-foreground/40 font-mono truncate max-w-[100px] italic" title={memory.source}>
                                        {memory.source.split(',')[0]}
                                    </div>
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
};

