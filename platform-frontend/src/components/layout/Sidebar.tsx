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
import { SettingsModal } from '@/features/settings/SettingsModal';

export const Sidebar: React.FC = () => {
    const { runs, currentRun, setCurrentRun, fetchRuns, createNewRun, sidebarTab, setSidebarTab } = useAppStore();
    const [settingsOpen, setSettingsOpen] = React.useState(false);

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
        tab?: 'runs' | 'rag' | 'mcp' | 'remme' | 'explorer' | 'apps' | 'news' | 'learn',
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
                        : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
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
            <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />

            {/* NavRail - Left Vertical Bar */}
            <div className="w-16 border-r border-border bg-charcoal-950 flex flex-col items-center py-4 gap-2 shrink-0 z-20">
                {/* Top Tools */}
                <div className="flex-1 w-full px-2 space-y-2">
                    <NavIcon icon={PlayCircle} label="Runs" tab="runs" />
                    <NavIcon icon={Database} label="RAG" tab="rag" />
                    <NavIcon icon={Box} label="MCP" tab="mcp" />
                    <NavIcon icon={Brain} label="RemMe" tab="remme" />
                    <NavIcon icon={Code2} label="Explorer" tab="explorer" />

                    <div className="w-8 h-px bg-white/5 my-2 mx-auto" />

                    <NavIcon icon={LayoutGrid} label="Apps" tab="apps" />
                    <NavIcon icon={Newspaper} label="News" tab="news" />
                    <NavIcon icon={GraduationCap} label="Learn" tab="learn" />
                </div>

                {/* Bottom Tools */}
                <div className="w-full px-2">
                    <NavIcon icon={Settings} label="Settings" onClick={() => setSettingsOpen(true)} />
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 min-w-0 bg-charcoal-900/40 backdrop-blur-sm flex flex-col overflow-hidden relative">
                {sidebarTab === 'runs' && (
                    <>
                        <div className="p-4 border-b border-border space-y-3">
                            <Dialog open={isNewRunOpen} onOpenChange={setIsNewRunOpen}>
                                <DialogTrigger asChild>
                                    <Button
                                        className="w-full gap-2 bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20 transition-all font-semibold"
                                    >
                                        <Plus className="w-4 h-4" />
                                        New Run
                                    </Button>
                                </DialogTrigger>
                                <DialogContent className="bg-charcoal-900 border-border sm:max-w-md text-white">
                                    <DialogHeader>
                                        <DialogTitle className="text-white text-lg">Start New Agent Run</DialogTitle>
                                    </DialogHeader>
                                    <div className="space-y-4 py-4">
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium text-gray-300">What should the agent do?</label>
                                            <Input
                                                placeholder="e.g., Research latest AI trends..."
                                                value={newQuery}
                                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewQuery(e.target.value)}
                                                className="bg-charcoal-800 border-gray-600 text-white placeholder:text-gray-500"
                                                onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => e.key === 'Enter' && handleStartRun()}
                                                autoFocus
                                            />
                                        </div>
                                    </div>
                                    <DialogFooter>
                                        <Button variant="outline" onClick={() => setIsNewRunOpen(false)} className="border-border text-white hover:bg-white/10">Cancel</Button>
                                        <Button onClick={handleStartRun} className="bg-neon-yellow text-charcoal-900 hover:bg-neon-yellow/90 font-semibold">Start Run</Button>
                                    </DialogFooter>
                                </DialogContent>
                            </Dialog>

                            <div className="relative">
                                <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-muted-foreground" />
                                <input
                                    className="w-full bg-background/50 border border-input rounded-md pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all text-white placeholder:text-muted-foreground"
                                    placeholder="Search runs..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                />
                            </div>
                        </div>

                        <div className="flex-1 overflow-y-auto p-2 space-y-2 custom-scrollbar">
                            {filteredRuns.map((run) => (
                                <div
                                    key={run.id}
                                    onClick={() => setCurrentRun(run.id)}
                                    className={cn(
                                        "group p-3 rounded-lg cursor-pointer transition-all border border-transparent",
                                        currentRun?.id === run.id
                                            ? "bg-accent/40 border-primary/20 shadow-sm"
                                            : "hover:bg-white/5"
                                    )}
                                >
                                    <div className="flex justify-between items-start mb-1 gap-2">
                                        <h3 className={cn(
                                            "font-medium text-sm line-clamp-2 leading-tight flex-1 break-words",
                                            currentRun?.id === run.id ? "text-primary font-bold" : "text-foreground"
                                        )}>
                                            {run.name}
                                        </h3>
                                    </div>

                                    <div className="flex items-center justify-between text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
                                        <div className="flex items-center gap-1">
                                            <Clock className="w-3 h-3" />
                                            <span>{new Date(run.createdAt).toLocaleDateString()}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span
                                                className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-destructive/10 rounded cursor-pointer"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    if (confirm('Are you sure you want to delete this run?')) {
                                                        useAppStore.getState().deleteRun(run.id);
                                                    }
                                                }}
                                            >
                                                <Trash2 className="w-3 h-3 text-muted-foreground hover:text-destructive" />
                                            </span>
                                            <span className={cn(
                                                "px-1.5 py-0.5 rounded-sm",
                                                run.status === 'completed' && "text-green-500 bg-green-500/10",
                                                run.status === 'failed' && "text-red-500 bg-red-500/10",
                                                run.status === 'running' && "text-yellow-500 bg-yellow-500/10 animate-pulse",
                                            )}>
                                                {run.status}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                )}
                {sidebarTab === 'rag' && <RagPanel />}
                {sidebarTab === 'mcp' && <McpPanel />}
                {sidebarTab === 'remme' && <RemmePanel />}
                {sidebarTab === 'explorer' && <ExplorerPanel />}
                {sidebarTab === 'apps' && <AppsSidebar />}
                {['news', 'learn'].includes(sidebarTab) && (
                    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4 opacity-50">
                        <div className="p-6 bg-white/5 rounded-full ring-1 ring-white/10">
                            {sidebarTab === 'news' && <Newspaper className="w-12 h-12" />}
                            {sidebarTab === 'learn' && <GraduationCap className="w-12 h-12" />}
                        </div>
                        <div className="space-y-1">
                            <h2 className="text-xl font-bold text-white uppercase tracking-tighter">Under Construction</h2>
                            <p className="text-xs text-muted-foreground">This feature is currently in development and will be available in a future update.</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
