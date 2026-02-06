import React from 'react';
import {
    Plus, Clock, Search, Trash2, Database, Box, PlayCircle, Brain,
    LayoutGrid, Newspaper, GraduationCap, Settings, Code2, Loader2, Notebook,
    CalendarClock, Terminal, Zap
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { API_BASE } from '@/lib/api';
import axios from 'axios';
import { RagPanel } from '@/components/sidebar/RagPanel';
import { McpPanel } from '@/components/sidebar/McpPanel';
import { RemmePanel } from '@/components/sidebar/RemmePanel';
import { NotesPanel } from '@/components/sidebar/NotesPanel';
import { ExplorerPanel } from '@/components/sidebar/ExplorerPanel';
import { AppsSidebar } from '@/features/apps/components/AppsSidebar';
import { SettingsPanel } from '@/components/sidebar/SettingsPanel';
import { NewsPanel } from '@/components/sidebar/NewsPanel';

const NavIcon = ({ icon: Icon, label, tab, active, onClick }: {
    icon: any,
    label: string,
    tab?: 'runs' | 'rag' | 'notes' | 'mcp' | 'remme' | 'explorer' | 'apps' | 'news' | 'learn' | 'settings' | 'ide' | 'scheduler' | 'console' | 'skills',
    active: boolean,
    onClick: () => void
}) => {
    const clearSelection = useAppStore(state => state.clearSelection);
    const sidebarTab = useAppStore(state => state.sidebarTab);
    const selectedNodeId = useAppStore(state => state.selectedNodeId);
    const selectedAppCardId = useAppStore(state => state.selectedAppCardId);
    const selectedExplorerNodeId = useAppStore(state => state.selectedExplorerNodeId);
    const ragActiveDocumentId = useAppStore(state => state.ragActiveDocumentId);
    const selectedMcpServer = useAppStore(state => state.selectedMcpServer);
    const selectedRagFile = useAppStore(state => state.selectedRagFile);
    const showNewsChatPanel = useAppStore(state => state.showNewsChatPanel);

    const isInspectorOpen = React.useMemo(() => {
        if (sidebarTab === 'apps' && selectedAppCardId) return true;
        if (sidebarTab === 'runs' && selectedNodeId) return true;
        if (sidebarTab === 'explorer' && selectedExplorerNodeId) return true;
        if (sidebarTab === 'rag' && (ragActiveDocumentId || selectedRagFile)) return true;
        if (sidebarTab === 'mcp' && selectedMcpServer) return true;
        if (sidebarTab === 'news' && showNewsChatPanel) return true;
        return false;
    }, [sidebarTab, selectedNodeId, selectedAppCardId, selectedExplorerNodeId, ragActiveDocumentId, selectedMcpServer, selectedRagFile, showNewsChatPanel]);

    const handleIconClick = () => {
        if (active && isInspectorOpen) {
            // MCP should be persistent as per user request
            if (sidebarTab === 'mcp') return;

            clearSelection();
        } else {
            onClick();
        }
    };

    return (
        <button
            onClick={handleIconClick}
            className={cn(
                "w-12 h-12 flex flex-col items-center justify-center gap-0.5 transition-all rounded-xl group relative mx-auto",
                active
                    ? "text-primary glass border-primary/20 shadow-lg z-10"
                    : "text-muted-foreground hover:text-foreground opacity-60 hover:opacity-100 hover:bg-white/5"
            )}
            title={label}
        >
            <Icon className={cn("w-5 h-5 transition-colors", active ? "text-primary" : "group-hover:text-foreground")} />
            <span className={cn(
                "text-[7px] font-black uppercase tracking-tighter transition-all duration-200",
                active ? "text-primary opacity-100" : "text-muted-foreground/90 group-hover:text-foreground"
            )}>
                {label}
            </span>
        </button>
    );
};

export const Sidebar: React.FC<{ hideSubPanel?: boolean }> = ({ hideSubPanel }) => {
    const runs = useAppStore(state => state.runs);
    const currentRun = useAppStore(state => state.currentRun);
    const setCurrentRun = useAppStore(state => state.setCurrentRun);
    const fetchRuns = useAppStore(state => state.fetchRuns);
    const createNewRun = useAppStore(state => state.createNewRun);
    const sidebarTab = useAppStore(state => state.sidebarTab);
    const setSidebarTab = useAppStore(state => state.setSidebarTab);
    const deleteRun = useAppStore(state => state.deleteRun);
    const generateAppFromReport = useAppStore(state => state.generateAppFromReport);
    const isGeneratingApp = useAppStore(state => state.isGeneratingApp);

    // Fetch runs on mount
    React.useEffect(() => {
        fetchRuns();
    }, [fetchRuns]);

    const isNewRunOpen = useAppStore(state => state.isNewRunOpen);
    const setIsNewRunOpen = useAppStore(state => state.setIsNewRunOpen);
    const [newQuery, setNewQuery] = React.useState("");
    const [searchQuery, setSearchQuery] = React.useState("");
    const [isOptimizing, setIsOptimizing] = React.useState(false);

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
        await createNewRun(newQuery);
        setNewQuery("");
    };

    return (
        <div className="h-full flex overflow-hidden">
            {/* NavRail - Left Vertical Bar */}
            <div className="w-16 border-r border-white/10 bg-background/10 backdrop-blur-md flex flex-col items-center py-4 gap-2 shrink-0 z-20">
                {/* Top Tools */}
                <div className="flex-1 w-full px-2 space-y-2">
                    <NavIcon icon={PlayCircle} label="Runs" tab="runs" active={sidebarTab === 'runs'} onClick={() => setSidebarTab('runs')} />
                    <NavIcon icon={Database} label="RAG" tab="rag" active={sidebarTab === 'rag'} onClick={() => setSidebarTab('rag')} />
                    <NavIcon icon={Notebook} label="Notes" tab="notes" active={sidebarTab === 'notes'} onClick={() => setSidebarTab('notes')} />
                    <NavIcon icon={Box} label="MCP" tab="mcp" active={sidebarTab === 'mcp'} onClick={() => setSidebarTab('mcp')} />
                    <NavIcon icon={Brain} label="RemMe" tab="remme" active={sidebarTab === 'remme'} onClick={() => setSidebarTab('remme')} />
                    <NavIcon icon={Code2} label="Explorer" tab="explorer" active={sidebarTab === 'explorer'} onClick={() => setSidebarTab('explorer')} />

                    <div className="w-8 h-px bg-muted/50 my-2 mx-auto" />

                    <NavIcon icon={LayoutGrid} label="Apps" tab="apps" active={sidebarTab === 'apps'} onClick={() => setSidebarTab('apps')} />
                    <NavIcon icon={Code2} label="IDE" tab="ide" active={sidebarTab === 'ide'} onClick={() => setSidebarTab('ide')} />
                    <NavIcon icon={CalendarClock} label="Scheduler" tab="scheduler" active={sidebarTab === 'scheduler'} onClick={() => setSidebarTab('scheduler')} />
                    <NavIcon icon={Zap} label="Skills" tab="skills" active={sidebarTab === 'skills'} onClick={() => setSidebarTab('skills')} />
                    <NavIcon icon={Terminal} label="Console" tab="console" active={sidebarTab === 'console'} onClick={() => setSidebarTab('console')} />
                    <NavIcon icon={Newspaper} label="News" tab="news" active={sidebarTab === 'news'} onClick={() => setSidebarTab('news')} />
                    <NavIcon icon={GraduationCap} label="Learn" tab="learn" active={sidebarTab === 'learn'} onClick={() => setSidebarTab('learn')} />
                </div>

                {/* Bottom Tools */}
                <div className="w-full px-2">
                    <NavIcon icon={Settings} label="Settings" tab="settings" active={sidebarTab === 'settings'} onClick={() => setSidebarTab('settings')} />
                </div>
            </div>

            {/* Content Area */}
            {!hideSubPanel && (
                <div className="flex-1 min-w-0 bg-transparent border-l border-white/10 shadow-none flex flex-col overflow-hidden relative">
                    {sidebarTab === 'settings' && <SettingsPanel />}
                    {sidebarTab === 'runs' && (
                        <div className="flex flex-col h-full bg-transparent text-foreground">

                            <div className="p-2 border-b border-border/50 bg-muted/20 flex items-center gap-1.5 shrink-0">
                                <div className="relative flex-1 group">
                                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                                    <Input
                                        className="w-full bg-background/50 border-transparent focus:bg-background focus:border-border rounded-md text-xs pl-8 pr-2 h-8 transition-all placeholder:text-muted-foreground"
                                        placeholder="Search runs..."
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                    />
                                </div>

                                <Dialog open={isNewRunOpen} onOpenChange={setIsNewRunOpen}>
                                    <DialogTrigger asChild>
                                        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-background/80" title="New Run">
                                            <Plus className="w-4 h-4" />
                                        </Button>
                                    </DialogTrigger>
                                    <DialogContent className="bg-card border-border sm:max-w-lg text-foreground">
                                        <DialogHeader>
                                            <DialogTitle className="text-foreground text-lg">Start New Agent Run</DialogTitle>
                                        </DialogHeader>
                                        <div className="space-y-4 py-4">
                                            <div className="space-y-2">
                                                <label className="text-sm font-medium text-muted-foreground">What should the agent do?</label>
                                                <div className="relative">
                                                    <Input
                                                        placeholder="e.g., Research latest AI trends..."
                                                        value={newQuery}
                                                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewQuery(e.target.value)}
                                                        className="bg-muted border-input text-foreground placeholder:text-muted-foreground pr-24" // Extra padding for button
                                                        onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => e.key === 'Enter' && handleStartRun()}
                                                        autoFocus
                                                        disabled={isOptimizing}
                                                    />
                                                </div>
                                                <div className="flex justify-between items-center text-xs text-muted-foreground">
                                                    <span>Tip: Be specific about tools and outputs.</span>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        disabled={isOptimizing || !newQuery.trim()}
                                                        className="h-6 text-xs text-neon-yellow hover:text-neon-yellow hover:bg-neon-yellow/10 px-2 gap-1 disabled:opacity-50"
                                                        onClick={async () => {
                                                            if (!newQuery) return;
                                                            setIsOptimizing(true);
                                                            try {
                                                                const res = await axios.post(`${API_BASE}/optimizer/preview`, { query: newQuery });
                                                                if (res.data && res.data.optimized) {
                                                                    setNewQuery(res.data.optimized);
                                                                }
                                                            } catch (e) {
                                                                console.error("Optimization failed", e);
                                                            } finally {
                                                                setIsOptimizing(false);
                                                            }
                                                        }}
                                                    >
                                                        {isOptimizing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                                                        {isOptimizing ? "Optimizing..." : "Optimize"}
                                                    </Button>
                                                </div>
                                            </div>
                                        </div>
                                        <DialogFooter>
                                            <Button variant="outline" onClick={() => setIsNewRunOpen(false)} className="border-border text-foreground hover:bg-muted">Cancel</Button>
                                            <Button onClick={handleStartRun} className="bg-neon-yellow text-white hover:bg-neon-yellow/90 font-semibold">Start Run</Button>
                                        </DialogFooter>
                                    </DialogContent>
                                </Dialog>
                            </div>

                            {/* List - Matches Remme Style */}
                            <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide">
                                {filteredRuns.map((run) => {
                                    const isStale = run.status === 'running' && (Date.now() - run.createdAt > 60 * 60 * 1000); // 1 hour timeout
                                    const displayStatus = isStale ? 'failed' : run.status;
                                    const isActive = currentRun?.id === run.id;

                                    return (
                                        <div
                                            key={run.id}
                                            onClick={() => setCurrentRun(run.id)}
                                            className={cn(
                                                "group relative p-4 rounded-xl border transition-all duration-300 cursor-pointer",
                                                "hover:shadow-md",
                                                isActive
                                                    ? "border-neon-yellow/40 hover:border-neon-yellow/60 bg-neon-yellow/5"
                                                    : "border-border/50 hover:border-primary/50 hover:bg-accent/50"
                                            )}
                                        >
                                            <div className="flex justify-between items-start gap-3">
                                                <div className="flex-1 min-w-0">
                                                    <p className={cn(
                                                        "text-[13px] leading-relaxed font-medium transition-all duration-300",
                                                        isActive
                                                            ? "text-neon-yellow selection:bg-neon-yellow/30"
                                                            : displayStatus === 'failed'
                                                                ? "text-red-500 group-hover:text-red-400"
                                                                : "text-foreground group-hover:text-foreground/80"
                                                    )}>
                                                        {run.name}
                                                    </p>
                                                </div>
                                                {/* Build App Button - Top Right */}
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        const { isGeneratingApp, generateAppFromReport } = useAppStore.getState();
                                                        if (isGeneratingApp) return;
                                                        generateAppFromReport(run.id);
                                                    }}
                                                    disabled={useAppStore.getState().isGeneratingApp}
                                                    className={cn(
                                                        "opacity-0 group-hover:opacity-100 p-1.5 rounded-lg transition-all duration-200",
                                                        useAppStore.getState().isGeneratingApp
                                                            ? "bg-muted text-muted-foreground cursor-not-allowed"
                                                            : "hover:bg-neon-yellow/10 text-muted-foreground hover:text-neon-yellow"
                                                    )}
                                                    title="Build App from this Run"
                                                >
                                                    {useAppStore.getState().isGeneratingApp ? (
                                                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                    ) : (
                                                        <LayoutGrid className="w-3.5 h-3.5" />
                                                    )}
                                                </button>
                                            </div>

                                            {/* Footer - Only visible when Active */}
                                            {isActive && (
                                                <div className="mt-4 pt-3 border-t border-border/50 flex items-center justify-between animate-in fade-in slide-in-from-top-2 duration-200">
                                                    <div className="flex items-center gap-3">
                                                        <span className="flex items-center gap-1 text-[9px] text-muted-foreground font-mono">
                                                            <Clock className="w-3 h-3" />
                                                            {new Date(run.createdAt).toLocaleDateString()}
                                                        </span>

                                                        {run.total_tokens !== undefined && (
                                                            <span className="text-[9px] text-muted-foreground font-mono opacity-70">
                                                                • {run.total_tokens.toLocaleString()} tks
                                                            </span>
                                                        )}

                                                        {/* Delete Button - Moved to Footer */}
                                                        <button
                                                            className="p-1 hover:bg-red-500/10 rounded text-muted-foreground hover:text-red-400 transition-all duration-200"
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                if (confirm('Delete this run?')) useAppStore.getState().deleteRun(run.id);
                                                            }}
                                                            title="Delete run"
                                                        >
                                                            <Trash2 className="w-3 h-3" />
                                                        </button>

                                                    </div>
                                                    <span className={cn(
                                                        "px-2 py-0.5 rounded-full text-[9px] uppercase font-bold tracking-tighter",
                                                        displayStatus === 'completed' && "bg-green-500/10 text-green-400/80",
                                                        displayStatus === 'failed' && "bg-red-500/10 text-red-400/80",
                                                        displayStatus === 'running' && "bg-orange-500/10 text-orange-400 animate-pulse",
                                                    )}>
                                                        {displayStatus}
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                    {sidebarTab === 'rag' && <RagPanel />}
                    {sidebarTab === 'notes' && <NotesPanel />}
                    {sidebarTab === 'mcp' && <McpPanel />}
                    {sidebarTab === 'remme' && <RemmePanel />}
                    {sidebarTab === 'explorer' && <ExplorerPanel />}
                    {sidebarTab === 'apps' && <AppsSidebar />}
                    {sidebarTab === 'news' && <NewsPanel />}
                    {sidebarTab === 'learn' && (
                        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4 opacity-50">
                            <div className="p-6 bg-muted/50 rounded-full ring-1 ring-white/10">
                                <GraduationCap className="w-12 h-12" />
                            </div>
                            <div className="space-y-1">
                                <h2 className="text-xl font-bold text-foreground uppercase tracking-tighter">Under Construction</h2>
                                <p className="text-xs text-muted-foreground">This feature is currently in development and will be available in a future update.</p>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
