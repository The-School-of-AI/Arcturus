import React, { useEffect, useState, useMemo } from 'react';
import { useAppStore } from '@/store';
import { Search, Brain, Trash2, Plus, AlertCircle, Edit2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';

export const RemmePanel: React.FC = () => {
    const { memories, fetchMemories, addMemory, deleteMemory } = useAppStore();
    const [searchQuery, setSearchQuery] = useState("");
    const [isAddOpen, setIsAddOpen] = useState(false);
    const [newMemoryText, setNewMemoryText] = useState("");

    useEffect(() => {
        fetchMemories();
    }, []);

    const filteredMemories = useMemo(() => {
        if (!searchQuery.trim()) return memories;
        return memories.filter(m =>
            m.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
            m.category.toLowerCase().includes(searchQuery.toLowerCase())
        );
    }, [memories, searchQuery]);

    const handleAdd = async () => {
        if (!newMemoryText.trim()) return;
        await addMemory(newMemoryText);
        setNewMemoryText("");
        setIsAddOpen(false);
    };

    return (
        <div className="flex flex-col h-full bg-charcoal-900 text-white">
            {/* Header */}
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Brain className="w-5 h-5 text-neon-yellow" />
                    <h2 className="font-semibold text-lg tracking-tight">Memory Vault</h2>
                </div>
                <div className="text-xs text-gray-500 font-mono">
                    {memories.length} FACTS
                </div>
            </div>

            {/* Search */}
            <div className="p-3 border-b border-white/5">
                <div className="relative">
                    <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
                    <Input
                        className="pl-9 bg-charcoal-800 border-white/10 text-sm focus:ring-neon-yellow/50"
                        placeholder="Search your memories..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
            </div>

            {/* Add New Memory */}
            {isAddOpen ? (
                <div className="p-4 bg-charcoal-800 border-b border-white/10 animate-in slide-in-from-top-2">
                    <textarea
                        className="w-full bg-charcoal-900 border border-white/20 rounded p-2 text-sm text-white mb-2 focus:outline-none focus:border-neon-yellow"
                        rows={3}
                        placeholder="e.g., I prefer using dark mode..."
                        value={newMemoryText}
                        onChange={(e) => setNewMemoryText(e.target.value)}
                        autoFocus
                    />
                    <div className="flex justify-end gap-2">
                        <Button size="sm" variant="ghost" onClick={() => setIsAddOpen(false)}>Cancel</Button>
                        <Button size="sm" className="bg-neon-yellow text-charcoal-900 hover:bg-neon-yellow/90" onClick={handleAdd}>
                            Save Memory
                        </Button>
                    </div>
                </div>
            ) : (
                <div className="p-2 flex justify-center border-b border-white/5 bg-charcoal-800/30">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="text-xs text-gray-400 hover:text-neon-yellow w-full"
                        onClick={() => setIsAddOpen(true)}
                    >
                        <Plus className="w-3 h-3 mr-1" /> Add Manual Memory
                    </Button>
                </div>
            )}

            {/* List */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
                {filteredMemories.length === 0 ? (
                    <div className="text-center py-10 text-gray-500">
                        <Brain className="w-10 h-10 mx-auto mb-2 opacity-20" />
                        <p className="text-sm">No memories found.</p>
                    </div>
                ) : (
                    filteredMemories.map((memory) => (
                        <div
                            key={memory.id}
                            className="group relative p-3 rounded-lg bg-charcoal-800 border border-white/5 hover:border-white/20 transition-all hover:shadow-lg"
                        >
                            <div className="flex justify-between items-start gap-2">
                                <p className="text-sm text-gray-200 leading-relaxed font-medium">
                                    {memory.text}
                                </p>
                                <button
                                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 rounded text-gray-500 hover:text-red-400 transition-all"
                                    onClick={() => deleteMemory(memory.id)}
                                    title="Forget this memory"
                                >
                                    <Trash2 className="w-3 h-3" />
                                </button>
                            </div>

                            <div className="mt-2 flex items-center justify-between text-[10px] text-gray-500 font-mono">
                                <div className="flex items-center gap-2">
                                    <span className={cn(
                                        "px-1.5 py-0.5 rounded uppercase tracking-wider",
                                        memory.category === 'derived' ? "bg-purple-500/10 text-purple-400" : "bg-blue-500/10 text-blue-400"
                                    )}>
                                        {memory.category}
                                    </span>
                                    <span>• {formatDistanceToNow(new Date(memory.created_at))} ago</span>
                                </div>
                                <span className="opacity-50">
                                    SRC: {memory.source}
                                </span>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};
