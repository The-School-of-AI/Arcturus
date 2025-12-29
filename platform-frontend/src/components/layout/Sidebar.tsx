import React from 'react';
import {
    Plus, Clock, Search, Trash2, Database, Box, PlayCircle, Brain,
    LayoutGrid, Newspaper, GraduationCap, Settings, Code2
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { RagPanel } from '@/components/sidebar/RagPanel';
import { McpPanel } from '@/components/sidebar/McpPanel';
import { RemmePanel } from '@/components/sidebar/RemmePanel';
import { ExplorerPanel } from '@/components/sidebar/ExplorerPanel';
import { AppsSidebar } from '@/features/apps/components/AppsSidebar';

export const Sidebar: React.FC = () => {
    const { runs, currentRun, setCurrentRun, fetchRuns, createNewRun, sidebarTab, setSidebarTab } = useAppStore();

    // Fetch runs on mount
    React.useEffect(() => {
        fetchRuns();
    }, []);

    const [isNewRunOpen, setIsNewRunOpen] = React.useState(false);
    const [newQuery, setNewQuery] = React.useState("");
    const [searchQuery, setSearchQuery] = React.useState("");

    // Filter runs
    const filteredRuns = React.useMemo(() => {
        if (!searchQuery.trim()) return runs;
        return runs.filter(run =>
            run.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            run.id.includes(searchQuery)
        );
    }, [runs, searchQuery]);

    const handleStartRun = async () => {
        if (!newQuery.trim()) return;
        setIsNewRunOpen(false);
        await createNewRun(newQuery, "gemini-2.0-pro");
        setNewQuery("");
    };

    const NavIcon = ({ icon: Icon, label, tab, onClick }: {
        icon: any,
        label: string,
        tab?: 'runs' | 'rag' | 'mcp' | 'remme' | 'explorer' | 'apps' | 'news' | 'learn' | 'settings',
        onClick?: () => void
    }) => {
        const active = sidebarTab === tab;
        return (
            <button
                onClick={onClick || (() => tab && setSidebarTab(tab))}
                className={cn(
                    "w-full aspect-square flex flex-col items-center justify-center gap-1 transition-all rounded-lg group relative",
                    active
                        ? "text-neon-yellow bg-neon-yellow/10"
                        : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                )}
                title={label}
            >
                <Icon className={cn("w-5 h-5 transition-transform group-hover:scale-110", active && "drop-shadow-[0_0_8px_rgba(255,255,0,0.4)]")} />
                <span className="text-[10px] font-medium opacity-60 group-hover:opacity-100">{label}</span>
                {active && <div className="absolute left-0 top-2 bottom-2 w-1 bg-neon-yellow rounded-r-full shadow-[0_0_8px_rgba(255,255,0,0.6)]" />}
            </button>
        );
    };

    return (
        <div className="h-full flex overflow-hidden">
            {/* NavRail - Left Vertical Bar */}
            <div className="w-16 border-r border-border bg-background flex flex-col items-center py-4 gap-2 shrink-0 z-20">
                {/* Top Tools */}
                <div className="flex-1 w-full px-2 space-y-2">
                    <NavIcon icon={PlayCircle} label="Runs" tab="runs" />
                    <NavIcon icon={Database} label="RAG" tab="rag" />
                    <NavIcon icon={Box} label="MCP" tab="mcp" />
                    <NavIcon icon={Brain} label="RemMe" tab="remme" />
                    <NavIcon icon={Code2} label="Explorer" tab="explorer" />

                    <div className="w-8 h-px bg-muted/50 my-2 mx-auto" />

                    <NavIcon icon={LayoutGrid} label="Apps" tab="apps" />
                    <NavIcon icon={Newspaper} label="News" tab="news" />
                    <NavIcon icon={GraduationCap} label="Learn" tab="learn" />
                </div>

                {/* Bottom Tools */}
                <div className="w-full px-2">
                    <NavIcon icon={Settings} label="Settings" tab="settings" />
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 min-w-0 bg-card/40 backdrop-blur-sm flex flex-col overflow-hidden relative">
                {sidebarTab === 'runs' && (
                    <div className="flex flex-col h-full bg-card text-foreground">
                        {/* Header - Matches Remme Style */}
                        <div className="p-4 border-b border-border flex items-center justify-between bg-card/50 backdrop-blur-md sticky top-0 z-10">
                            <div className="flex items-center gap-2">
                                <div className="p-1.5 bg-neon-yellow/10 rounded-lg">
                                    <PlayCircle className="w-5 h-5 text-neon-yellow" />
                                </div>
                                <div>
                                    <h2 className="font-semibold text-sm tracking-tight text-foreground uppercase">Agent Runs</h2>
                                    <p className="text-[10px] text-neon-yellow/80 font-mono tracking-widest">{runs.length} SESSIONS</p>
                                </div>
                            </div>
                        </div>

                        {/* New Run Button */}
                        <div className="p-3 border-b border-border/50 bg-muted/20">
                            <Dialog open={isNewRunOpen} onOpenChange={setIsNewRunOpen}>
                                <DialogTrigger asChild>
                                    <Button
                                        className="w-full gap-2 bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20 transition-all font-semibold"
                                    >
                                        <Plus className="w-4 h-4" />
                                        New Run
                                    </Button>
                                </DialogTrigger>
                                <DialogContent className="bg-card border-border sm:max-w-md text-foreground">
                                    <DialogHeader>
                                        <DialogTitle className="text-foreground text-lg">Start New Agent Run</DialogTitle>
                                    </DialogHeader>
                                    <div className="space-y-4 py-4">
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium text-muted-foreground">What should the agent do?</label>
                                            <Input
                                                placeholder="e.g., Research latest AI trends..."
                                                value={newQuery}
                                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewQuery(e.target.value)}
                                                className="bg-muted border-input text-foreground placeholder:text-muted-foreground"
                                                onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => e.key === 'Enter' && handleStartRun()}
                                                autoFocus
                                            />
                                        </div>
                                    </div>
                                    <DialogFooter>
                                        <Button variant="outline" onClick={() => setIsNewRunOpen(false)} className="border-border text-foreground hover:bg-muted">Cancel</Button>
                                        <Button onClick={handleStartRun} className="bg-neon-yellow text-neutral-950 hover:bg-neon-yellow/90 font-semibold">Start Run</Button>
                                    </DialogFooter>
                                </DialogContent>
                            </Dialog>
                        </div>

                        {/* Search - Matches Remme Style */}
                        <div className="p-3 border-b border-border/50 bg-muted/20">
                            <div className="relative group">
                                <Search className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground group-focus-within:text-neon-yellow transition-colors" />
                                <Input
                                    className="pl-9 bg-card/50 border-border/50 text-sm focus:ring-1 focus:ring-neon-yellow/30 placeholder:text-muted-foreground h-9 transition-all"
                                    placeholder="Search runs..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                />
                            </div>
                        </div>

                        {/* List - Matches Remme Style */}
                        <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide">
                            {filteredRuns.map((run) => (
                                <div
                                    key={run.id}
                                    onClick={() => setCurrentRun(run.id)}
                                    className={cn(
                                        "group relative p-4 rounded-xl border transition-all duration-300 cursor-pointer",
                                        "bg-gradient-to-br from-card to-muted/20",
                                        "hover:shadow-md",
                                        currentRun?.id === run.id
                                            ? "border-neon-yellow/40 hover:border-neon-yellow/60"
                                            : "border-border/50 hover:border-white/20"
                                    )}
                                >
                                    <div className="flex justify-between items-start gap-3">
                                        <div className="flex-1 min-w-0">
                                            <p className={cn(
                                                "text-[13px] leading-relaxed font-medium selection:bg-neon-yellow/30",
                                                "line-clamp-2 group-hover:line-clamp-none transition-all duration-300",
                                                currentRun?.id === run.id ? "text-neon-yellow" : "text-foreground"
                                            )}>
                                                {run.name}
                                            </p>
                                        </div>
                                        <div className="flex flex-col gap-2 -mr-1">
                                            <button
                                                className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/10 rounded-lg text-muted-foreground hover:text-red-400 transition-all duration-200"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    if (confirm('Delete this run?')) useAppStore.getState().deleteRun(run.id);
                                                }}
                                                title="Delete run"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    </div>

                                    <div className="mt-4 pt-3 border-t border-border/50 flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            <span className="flex items-center gap-1 text-[9px] text-muted-foreground font-mono">
                                                <Clock className="w-3 h-3" />
                                                {new Date(run.createdAt).toLocaleDateString()}
                                            </span>
                                        </div>
                                        <span className={cn(
                                            "px-2 py-0.5 rounded-full text-[9px] uppercase font-bold tracking-tighter",
                                            run.status === 'completed' && "bg-green-500/10 text-green-400/80",
                                            run.status === 'failed' && "bg-red-500/10 text-red-400/80",
                                            run.status === 'running' && "bg-yellow-500/10 text-yellow-400/80 animate-pulse",
                                        )}>
                                            {run.status}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                {sidebarTab === 'rag' && <RagPanel />}
                {sidebarTab === 'mcp' && <McpPanel />}
                {sidebarTab === 'remme' && <RemmePanel />}
                {sidebarTab === 'explorer' && <ExplorerPanel />}
                {sidebarTab === 'apps' && <AppsSidebar />}
                {['news', 'learn'].includes(sidebarTab) && (
                    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4 opacity-50">
                        <div className="p-6 bg-muted/50 rounded-full ring-1 ring-white/10">
                            {sidebarTab === 'news' && <Newspaper className="w-12 h-12" />}
                            {sidebarTab === 'learn' && <GraduationCap className="w-12 h-12" />}
                        </div>
                        <div className="space-y-1">
                            <h2 className="text-xl font-bold text-foreground uppercase tracking-tighter">Under Construction</h2>
                            <p className="text-xs text-muted-foreground">This feature is currently in development and will be available in a future update.</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
