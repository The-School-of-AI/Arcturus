import React, { useEffect, useState, useMemo } from 'react';
import { useAppStore } from '@/store';
import { Search, Brain, Trash2, Plus, AlertCircle, Edit2, TriangleAlert, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';

export const RemmePanel: React.FC = () => {
    const { memories, fetchMemories, addMemory, deleteMemory, cleanupDanglingMemories } = useAppStore();
    const [searchQuery, setSearchQuery] = useState("");
    const [isAddOpen, setIsAddOpen] = useState(false);
    const [newMemoryText, setNewMemoryText] = useState("");

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
        <div className="flex flex-col h-full bg-[#0a0a0a] text-white">
            {/* Header */}
            <div className="p-4 border-b border-white/10 flex items-center justify-between bg-charcoal-900/50 backdrop-blur-md sticky top-0 z-10">
                <div className="flex items-center gap-2">
                    <div className="p-1.5 bg-neon-yellow/10 rounded-lg">
                        <Brain className="w-5 h-5 text-neon-yellow animate-pulse" />
                    </div>
                    <div>
                        <h2 className="font-semibold text-sm tracking-tight text-gray-100 uppercase">Memory Vault</h2>
                        <p className="text-[10px] text-neon-yellow/50 font-mono tracking-widest">{memories.length} PERSISTENT FACTS</p>
                    </div>
                </div>
                <div className="flex items-center gap-1">
                    <Sparkles className="w-4 h-4 text-neon-yellow/20" />
                </div>
            </div>

            {/* Search */}
            <div className="p-3 border-b border-white/5 bg-[#0d0d0d]">
                <div className="relative group">
                    <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-600 group-focus-within:text-neon-yellow transition-colors" />
                    <Input
                        className="pl-9 bg-charcoal-900/50 border-white/5 text-sm focus:ring-1 focus:ring-neon-yellow/30 placeholder:text-gray-700 h-9 transition-all"
                        placeholder="Search your memories..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
            </div>

            {/* Actions Area */}
            <div className="p-2 grid grid-cols-2 gap-2 border-b border-white/5 bg-charcoal-900/30">
                <Button
                    variant="ghost"
                    size="sm"
                    className="text-[11px] text-gray-400 hover:text-neon-yellow hover:bg-neon-yellow/5 h-8"
                    onClick={() => setIsAddOpen(!isAddOpen)}
                >
                    <Plus className="w-3.5 h-3.5 mr-1.5" /> Manual Add
                </Button>

                <Button
                    variant="ghost"
                    size="sm"
                    disabled={danglingCount === 0}
                    className={cn(
                        "text-[11px] h-8",
                        danglingCount > 0
                            ? "text-orange-400 hover:text-orange-300 hover:bg-orange-400/10"
                            : "text-gray-600 opacity-50 cursor-not-allowed"
                    )}
                    onClick={() => {
                        if (confirm(`Cleanup ${danglingCount} memories with missing source sessions?`)) {
                            cleanupDanglingMemories();
                        }
                    }}
                >
                    <TriangleAlert className="w-3.5 h-3.5 mr-1.5" /> Cleanup ({danglingCount})
                </Button>
            </div>

            {/* Add New Memory Overlay/Area */}
            {isAddOpen && (
                <div className="p-4 bg-charcoal-800 border-b border-white/10 animate-in slide-in-from-top-2">
                    <textarea
                        className="w-full bg-[#0a0a0a] border border-white/10 rounded-lg p-3 text-sm text-gray-200 mb-3 focus:outline-none focus:border-neon-yellow/50 transition-colors placeholder:text-gray-700"
                        rows={3}
                        placeholder="Define a new fact for the agent to remember..."
                        value={newMemoryText}
                        onChange={(e) => setNewMemoryText(e.target.value)}
                        autoFocus
                    />
                    <div className="flex justify-end gap-2">
                        <Button size="sm" variant="ghost" onClick={() => setIsAddOpen(false)}>Cancel</Button>
                        <Button size="sm" className="bg-neon-yellow text-charcoal-900 hover:bg-neon-yellow/90 font-bold px-4 shadow-[0_0_15px_rgba(234,255,0,0.2)]" onClick={handleAdd}>
                            Save Fact
                        </Button>
                    </div>
                </div>
            )}

            {/* List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide">
                {filteredMemories.length === 0 ? (
                    <div className="text-center py-20 text-gray-700">
                        <div className="relative inline-block mb-4">
                            <Brain className="w-12 h-12 mx-auto opacity-10" />
                            <Search className="w-6 h-6 absolute bottom-0 right-0 opacity-20" />
                        </div>
                        <p className="text-xs font-mono tracking-widest uppercase opacity-40">No matching patterns</p>
                    </div>
                ) : (
                    filteredMemories.map((memory) => (
                        <div
                            key={memory.id}
                            className={cn(
                                "group relative p-4 rounded-xl border transition-all duration-300",
                                "bg-gradient-to-br from-charcoal-800/80 to-charcoal-900/40",
                                "hover:from-charcoal-800 hover:to-charcoal-900 hover:shadow-[0_8px_30px_rgb(0,0,0,0.12)]",
                                memory.source_exists === false
                                    ? "border-orange-500/20 hover:border-orange-500/40"
                                    : "border-white/5 hover:border-white/20"
                            )}
                        >
                            <div className="flex justify-between items-start gap-3">
                                <div className="flex-1 min-w-0">
                                    <p className={cn(
                                        "text-[13px] text-gray-200 leading-relaxed font-normal selection:bg-neon-yellow/30",
                                        "line-clamp-2 group-hover:line-clamp-none transition-all duration-300"
                                    )}>
                                        {memory.text}
                                    </p>
                                </div>
                                <div className="flex flex-col gap-2 -mr-1">
                                    <button
                                        className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/10 rounded-lg text-gray-600 hover:text-red-400 transition-all duration-200"
                                        onClick={() => deleteMemory(memory.id)}
                                        title="Forget this memory"
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>

                                    {memory.source_exists === false && (
                                        <div
                                            className="p-1.5 rounded-lg text-orange-500/60 animate-pulse bg-orange-500/5 group-hover:opacity-100 transition-opacity"
                                            title="Source session has been deleted"
                                        >
                                            <TriangleAlert className="w-3.5 h-3.5" />
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <span className={cn(
                                        "px-2 py-0.5 rounded-full text-[9px] uppercase font-bold tracking-tighter",
                                        memory.category === 'derived'
                                            ? "bg-purple-500/10 text-purple-400/80"
                                            : "bg-blue-500/10 text-blue-400/80"
                                    )}>
                                        {memory.category}
                                    </span>
                                    <span className="text-[9px] text-gray-600 font-mono">
                                        {formatDistanceToNow(new Date(memory.created_at))} ago
                                    </span>
                                </div>
                                <div className="text-[9px] text-gray-700 font-mono truncate max-w-[80px] hover:text-gray-400 transition-colors cursor-help" title={memory.source}>
                                    SRC: {memory.source.split(',')[0]}
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};
