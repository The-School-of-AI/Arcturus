import React from 'react';
import { Plus, Clock, Search, Trash2 } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { mockRuns } from '@/lib/mockData';

export const Sidebar: React.FC = () => {
    // In a real app, runs would come from store, initialized with mockRuns
    // For now we just use mockRuns directly or store if initialized
    const { runs, currentRun, setCurrentRun, addRun } = useAppStore();

    // Initialize if empty (development only hack)
    React.useEffect(() => {
        if (runs.length === 0) {
            mockRuns.forEach(r => addRun(r));
        }
    }, []);

    return (
        <div className="h-full flex flex-col">
            <div className="p-4 border-b border-border space-y-3">
                <Button className="w-full gap-2 bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20 transition-all font-semibold">
                    <Plus className="w-4 h-4" />
                    New Run
                </Button>

                <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-muted-foreground" />
                    <input
                        className="w-full bg-background/50 border border-input rounded-md pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
                        placeholder="Search runs..."
                    />
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {runs.map((run) => (
                    <div
                        key={run.id}
                        onClick={() => setCurrentRun(run.id)}
                        className={cn(
                            "group p-3 rounded-lg cursor-pointer transition-all border border-transparent",
                            currentRun?.id === run.id
                                ? "bg-accent/50 border-primary/20 shadow-sm"
                                : "hover:bg-accent/30 hover:border-border"
                        )}
                    >
                        <div className="flex justify-between items-start mb-1">
                            <h3 className={cn(
                                "font-medium text-sm truncate pr-2",
                                currentRun?.id === run.id ? "text-primary" : "text-foreground"
                            )}>
                                {run.name}
                            </h3>
                            <span className={cn(
                                "text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded-full",
                                run.status === 'completed' && "text-green-500 bg-green-500/10",
                                run.status === 'failed' && "text-red-500 bg-red-500/10",
                                run.status === 'running' && "text-yellow-500 bg-yellow-500/10",
                            )}>
                                {run.status}
                            </span>
                        </div>

                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <div className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                <span>{new Date(run.createdAt).toLocaleDateString()}</span>
                            </div>
                            <span className="opacity-0 group-hover:opacity-100 transition-opacity">
                                <Trash2 className="w-3 h-3 hover:text-destructive cursor-pointer" />
                            </span>
                        </div>

                        <div className="mt-2 flex gap-1 flex-wrap">
                            <span className="text-[10px] bg-background/80 border border-border px-1.5 py-0.5 rounded text-muted-foreground">
                                {run.model.split(':')[0]}
                            </span>
                            {run.ragEnabled && (
                                <span className="text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.5 rounded">
                                    RAG
                                </span>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
