import React from 'react';
import {
    Plus, Clock, Search, Trash2, Database, PlayCircle, Brain,
    LayoutGrid, Newspaper, GraduationCap, Settings, Code2, Loader2, Notebook,
    CalendarClock, Terminal, Zap, Wand2, Shield, FolderOpen, Mic, Network,
    MessageSquare, PanelLeftClose, PanelLeft
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Kbd } from "@/components/ui/kbd";
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { API_BASE } from '@/lib/api';
import axios from 'axios';
import { RagPanel } from '@/components/sidebar/RagPanel';
import { RemmePanel } from '@/components/sidebar/RemmePanel';
import { NotesPanel } from '@/components/sidebar/NotesPanel';
import { ExplorerPanel } from '@/components/sidebar/ExplorerPanel';
import { EchoPanel } from '@/components/sidebar/EchoPanel';
import { AppsSidebar } from '@/features/apps/components/AppsSidebar';
import { SettingsPanel } from '@/components/sidebar/SettingsPanel';
import { NewsPanel } from '@/components/sidebar/NewsPanel';
import { GraphPanel } from '@/components/sidebar/GraphPanel';
import { StudioSidebar } from '@/features/studio/StudioSidebar';
import { SwarmSidebar } from '@/features/swarm/SwarmSidebar';
import { CanvasPanel } from '@/components/sidebar/CanvasPanel';
import { SchedulerPanel } from '@/components/sidebar/SchedulerPanel';

// ── Navigation Structure ─────────────────────────────────────────────────────
// Grouped into logical categories for progressive disclosure

type SidebarTabId = 'runs' | 'rag' | 'notes' | 'mcp' | 'remme' | 'explorer' | 'graph' | 'apps' | 'news' | 'learn' | 'settings' | 'ide' | 'scheduler' | 'console' | 'skills' | 'canvas' | 'studio' | 'admin' | 'echo' | 'swarm';

interface NavItem {
    id: SidebarTabId;
    label: string;
    icon: any;
    tooltip: string;
    shortcut?: string;
}

interface NavGroup {
    label: string;
    items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
    {
        label: 'Core',
        items: [
            { id: 'echo', label: 'Echo', icon: Mic, tooltip: 'Voice assistant & agent interaction', shortcut: '1' },
            { id: 'runs', label: 'Runs', icon: PlayCircle, tooltip: 'Agent task executions & history', shortcut: '2' },
            { id: 'rag', label: 'RAG', icon: Database, tooltip: 'Knowledge base & document management', shortcut: '3' },
            { id: 'notes', label: 'Notes', icon: Notebook, tooltip: 'Markdown notes with AI analysis', shortcut: '4' },
            { id: 'remme', label: 'Memory', icon: Brain, tooltip: 'Persistent memory vault', shortcut: '5' },
            { id: 'graph', label: 'Graph', icon: Network, tooltip: 'Knowledge graph explorer' },
        ],
    },
    {
        label: 'Build',
        items: [
            { id: 'apps', label: 'Apps', icon: LayoutGrid, tooltip: 'Dashboard builder with 60+ widgets', shortcut: '6' },
            { id: 'canvas', label: 'Canvas', icon: LayoutGrid, tooltip: 'Interactive widget surface', shortcut: '7' },
            { id: 'ide', label: 'IDE', icon: Code2, tooltip: 'Code editor with terminal & git', shortcut: '8' },
            { id: 'studio', label: 'Forge', icon: Wand2, tooltip: 'Document & presentation studio' },
        ],
    },
    {
        label: 'Tools',
        items: [
            { id: 'scheduler', label: 'Scheduler', icon: CalendarClock, tooltip: 'Automated recurring tasks' },
            { id: 'skills', label: 'Skills', icon: Zap, tooltip: 'Agent plugin store' },
            { id: 'console', label: 'Console', icon: Terminal, tooltip: 'System event log' },
            { id: 'news', label: 'News', icon: Newspaper, tooltip: 'RSS feeds & web browser' },
        ],
    },
];

const BOTTOM_ITEMS: NavItem[] = [
    { id: 'admin', label: 'Admin', icon: Shield, tooltip: 'System monitoring & diagnostics' },
    { id: 'settings', label: 'Settings', icon: Settings, tooltip: 'Configuration & integrations' },
];

// ── NavIcon Component ────────────────────────────────────────────────────────

const NavIcon = ({ item, active, expanded, onClick }: {
    item: NavItem;
    active: boolean;
    expanded: boolean;
    onClick: () => void;
}) => {
    const clearSelection = useAppStore(state => state.clearSelection);
    const sidebarTab = useAppStore(state => state.sidebarTab);
    const selectedNodeId = useAppStore(state => state.selectedNodeId);
    const selectedAppCardId = useAppStore(state => state.selectedAppCardId);
    const selectedExplorerNodeId = useAppStore(state => state.selectedExplorerNodeId);
    const ragActiveDocumentId = useAppStore(state => state.ragActiveDocumentId);
    const selectedRagFile = useAppStore(state => state.selectedRagFile);
    const showNewsChatPanel = useAppStore(state => state.showNewsChatPanel);
    const currentRun = useAppStore(state => state.currentRun);
    const setSidebarSubPanelOpen = useAppStore(state => state.setSidebarSubPanelOpen);
    const toggleSidebarSubPanel = useAppStore(state => state.toggleSidebarSubPanel);

    const isInspectorOpen = React.useMemo(() => {
        if (sidebarTab === 'apps' && selectedAppCardId) return true;
        if (sidebarTab === 'runs' && selectedNodeId) return true;
        if (sidebarTab === 'explorer' && selectedExplorerNodeId) return true;
        if (sidebarTab === 'rag' && (ragActiveDocumentId || selectedRagFile)) return true;
        if (sidebarTab === 'news' && showNewsChatPanel) return true;
        if (sidebarTab === 'echo' && currentRun) return true;
        return false;
    }, [sidebarTab, selectedNodeId, selectedAppCardId, selectedExplorerNodeId, ragActiveDocumentId, selectedRagFile, showNewsChatPanel, currentRun]);

    const handleClick = () => {
        if (active && isInspectorOpen) {
            clearSelection();
        } else if (active) {
            if (setSidebarSubPanelOpen) {
                setSidebarSubPanelOpen(true);
            } else {
                toggleSidebarSubPanel();
            }
        } else {
            onClick();
        }
    };

    const Icon = item.icon;

    const btn = (
        <button
            onClick={handleClick}
            className={cn(
                "relative flex items-center gap-3 w-full rounded-lg transition-all duration-150 group",
                expanded ? "px-3 py-2" : "justify-center p-2 mx-auto w-10 h-10",
                active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
            )}
        >
            {/* Active indicator — left accent bar */}
            {active && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-primary rounded-r-full" />
            )}

            <Icon className={cn(
                "w-4 h-4 shrink-0 transition-colors",
                active ? "text-primary" : "group-hover:text-foreground"
            )} />

            {expanded && (
                <>
                    <span className={cn(
                        "text-sm font-medium truncate transition-colors",
                        active ? "text-primary" : "text-foreground/80 group-hover:text-foreground"
                    )}>
                        {item.label}
                    </span>
                    {item.shortcut && (
                        <Kbd className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
                            {item.shortcut}
                        </Kbd>
                    )}
                </>
            )}
        </button>
    );

    if (expanded) return btn;

    return (
        <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>{btn}</TooltipTrigger>
            <TooltipContent side="right" className="flex items-center gap-2">
                <span>{item.label}</span>
                {item.shortcut && <Kbd>{item.shortcut}</Kbd>}
            </TooltipContent>
        </Tooltip>
    );
};

// ── NavGroup Component ───────────────────────────────────────────────────────

const NavGroupSection = ({ group, expanded, sidebarTab, setSidebarTab }: {
    group: NavGroup;
    expanded: boolean;
    sidebarTab: string;
    setSidebarTab: (tab: any) => void;
}) => {
    return (
        <div className="space-y-0.5">
            {expanded && (
                <div className="px-3 py-1.5">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                        {group.label}
                    </span>
                </div>
            )}
            {!expanded && (
                <div className="w-6 h-px bg-border/50 mx-auto my-1.5" />
            )}
            {group.items.map((item) => (
                <NavIcon
                    key={item.id}
                    item={item}
                    active={sidebarTab === item.id}
                    expanded={expanded}
                    onClick={() => setSidebarTab(item.id)}
                />
            ))}
        </div>
    );
};

// ── Main Sidebar ─────────────────────────────────────────────────────────────

export const Sidebar: React.FC<{ hideSubPanel?: boolean }> = ({ hideSubPanel }) => {
    const runs = useAppStore(state => state.runs);
    const currentRun = useAppStore(state => state.currentRun);
    const setCurrentRun = useAppStore(state => state.setCurrentRun);
    const fetchRuns = useAppStore(state => state.fetchRuns);
    const createNewRun = useAppStore(state => state.createNewRun);
    const sidebarTab = useAppStore(state => state.sidebarTab);
    const setSidebarTab = useAppStore(state => state.setSidebarTab);
    const isSidebarExpanded = useAppStore(state => state.isSidebarExpanded);
    const toggleSidebarExpanded = useAppStore(state => state.toggleSidebarExpanded);

    React.useEffect(() => {
        fetchRuns();
    }, [fetchRuns]);

    const isNewRunOpen = useAppStore(state => state.isNewRunOpen);
    const setIsNewRunOpen = useAppStore(state => state.setIsNewRunOpen);
    const spaces = useAppStore(state => state.spaces);
    const currentSpaceId = useAppStore(state => state.currentSpaceId);
    const fetchSpaces = useAppStore(state => state.fetchSpaces);
    const [newQuery, setNewQuery] = React.useState("");
    const [searchQuery, setSearchQuery] = React.useState("");
    const [isOptimizing, setIsOptimizing] = React.useState(false);
    const [runSpaceId, setRunSpaceId] = React.useState<string | null>(null);
    const [runSourceFilter, setRunSourceFilter] = React.useState<'all' | 'manual' | 'scheduled'>('manual');

    React.useEffect(() => {
        if (isNewRunOpen) {
            setRunSpaceId(currentSpaceId);
            fetchSpaces();
        }
    }, [isNewRunOpen, currentSpaceId, fetchSpaces]);

    const filteredRuns = React.useMemo(() => {
        let list = runs;
        if (currentSpaceId) {
            list = list.filter((r) => r.space_id === currentSpaceId);
        } else {
            list = list.filter((r) => !r.space_id || r.space_id === '__global__');
        }
        if (runSourceFilter === 'manual') {
            list = list.filter((r) => !r.id.startsWith('auto_'));
        } else if (runSourceFilter === 'scheduled') {
            list = list.filter((r) => r.id.startsWith('auto_'));
        }
        if (searchQuery.trim()) {
            list = list.filter((run) =>
                run.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                run.id.includes(searchQuery)
            );
        }
        return list;
    }, [runs, searchQuery, currentSpaceId, runSourceFilter]);

    const currentSpaceName = currentSpaceId
        ? spaces.find((s) => s.space_id === currentSpaceId)?.name || 'Space'
        : 'Global';

    const handleStartRun = async () => {
        if (!newQuery.trim()) return;
        setIsNewRunOpen(false);
        await createNewRun(newQuery, undefined, runSpaceId);
        setNewQuery("");
    };

    // Keyboard shortcuts for tab switching
    React.useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Only trigger with Ctrl/Cmd + number
            if (!(e.metaKey || e.ctrlKey)) return;
            const allItems = NAV_GROUPS.flatMap(g => g.items);
            const shortcutItem = allItems.find(i => i.shortcut === e.key);
            if (shortcutItem) {
                e.preventDefault();
                setSidebarTab(shortcutItem.id);
            }
            // Cmd+\ to toggle sidebar
            if (e.key === '\\') {
                e.preventDefault();
                toggleSidebarExpanded();
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [setSidebarTab, toggleSidebarExpanded]);

    const expanded = isSidebarExpanded;

    return (
        <div className="h-full flex overflow-hidden">
            {/* NavRail / Expanded Sidebar */}
            <div className={cn(
                "bg-sidebar border-r border-sidebar-border flex flex-col shrink-0 z-20 transition-all duration-300 ease-out",
                expanded ? "w-[200px]" : "w-[52px]"
            )}>
                {/* Toggle button */}
                <div className={cn(
                    "flex items-center shrink-0 border-b border-sidebar-border",
                    expanded ? "justify-end px-2 h-10" : "justify-center h-10"
                )}>
                    <Tooltip delayDuration={0}>
                        <TooltipTrigger asChild>
                            <button
                                onClick={toggleSidebarExpanded}
                                className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                            >
                                {expanded ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeft className="w-4 h-4" />}
                            </button>
                        </TooltipTrigger>
                        <TooltipContent side="right">
                            <span className="flex items-center gap-2">
                                {expanded ? 'Collapse' : 'Expand'} sidebar
                                <Kbd>&#8984;\</Kbd>
                            </span>
                        </TooltipContent>
                    </Tooltip>
                </div>

                {/* Nav Groups — scrollable */}
                <div className={cn(
                    "flex-1 overflow-y-auto overflow-x-hidden no-scrollbar",
                    expanded ? "px-2 py-3 space-y-4" : "py-3 px-1 space-y-1"
                )}>
                    {NAV_GROUPS.map((group) => (
                        <NavGroupSection
                            key={group.label}
                            group={group}
                            expanded={expanded}
                            sidebarTab={sidebarTab}
                            setSidebarTab={setSidebarTab}
                        />
                    ))}
                </div>

                {/* Bottom section — Settings & Admin */}
                <div className={cn(
                    "shrink-0 border-t border-sidebar-border",
                    expanded ? "px-2 py-2 space-y-0.5" : "py-2 px-1 space-y-1"
                )}>
                    {BOTTOM_ITEMS.map((item) => (
                        <NavIcon
                            key={item.id}
                            item={item}
                            active={sidebarTab === item.id}
                            expanded={expanded}
                            onClick={() => setSidebarTab(item.id)}
                        />
                    ))}
                </div>
            </div>

            {/* Content Area — Sub Panel */}
            {!hideSubPanel && (
                <div className="flex-1 min-w-0 bg-sidebar border-l border-sidebar-border flex flex-col overflow-hidden relative animate-panel-in-left">
                    {sidebarTab === 'settings' && <SettingsPanel />}
                    {sidebarTab === 'runs' && (
                        <div className="flex flex-col h-full bg-transparent text-foreground">
                            <div className="p-2 border-b border-border/50 bg-surface-1 space-y-2 shrink-0">
                                <div className="flex items-center gap-1.5">
                                    <div className="relative flex-1 group">
                                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                                        <Input
                                            className="w-full bg-secondary border-border focus:bg-background focus:border-border rounded-md text-xs pl-8 pr-2 h-8 transition-all placeholder:text-muted-foreground"
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
                                                    <Label className="text-sm font-medium text-muted-foreground">Space</Label>
                                                    <Select
                                                        value={runSpaceId ?? "__global__"}
                                                        onValueChange={(v) => setRunSpaceId(v === "__global__" ? null : v)}
                                                    >
                                                        <SelectTrigger className="bg-muted border-input text-foreground">
                                                            <SelectValue placeholder="Global" />
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            <SelectItem value="__global__">Global (all runs)</SelectItem>
                                                            {spaces.map((s) => (
                                                                <SelectItem key={s.space_id} value={s.space_id}>
                                                                    {s.name || 'Unnamed Space'}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                </div>
                                                <div className="space-y-2">
                                                    <Label className="text-sm font-medium text-muted-foreground">What should the agent do?</Label>
                                                    <div className="relative">
                                                        <Input
                                                            placeholder="e.g., Research latest AI trends..."
                                                            value={newQuery}
                                                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewQuery(e.target.value)}
                                                            className="bg-muted border-input text-foreground placeholder:text-muted-foreground pr-24"
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
                                                            className="h-6 text-xs text-primary hover:text-primary hover:bg-primary/10 px-2 gap-1 disabled:opacity-50"
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
                                                <Button onClick={handleStartRun} className="bg-primary text-primary-foreground hover:bg-primary/90 font-semibold">Start Run</Button>
                                            </DialogFooter>
                                        </DialogContent>
                                    </Dialog>
                                </div>
                                <div className="flex items-center justify-between">
                                    <button
                                        onClick={() => useAppStore.getState().setIsSpacesModalOpen(true)}
                                        className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                                        title="Manage Spaces"
                                    >
                                        <FolderOpen className="w-3 h-3" />
                                        Space: {currentSpaceName}
                                    </button>
                                    <div className="flex items-center gap-0.5 bg-surface-2 rounded-md p-0.5">
                                        {(['all', 'manual', 'scheduled'] as const).map((f) => (
                                            <button
                                                key={f}
                                                onClick={() => setRunSourceFilter(f)}
                                                className={cn(
                                                    "px-1.5 py-0.5 rounded text-2xs font-medium transition-colors capitalize",
                                                    runSourceFilter === f
                                                        ? "bg-background text-foreground shadow-xs"
                                                        : "text-muted-foreground hover:text-foreground"
                                                )}
                                            >
                                                {f}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            {/* Run List */}
                            <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-hide">
                                {filteredRuns.map((run) => {
                                    const isStale = run.status === 'running' && (Date.now() - run.createdAt > 60 * 60 * 1000);
                                    const displayStatus = isStale ? 'failed' : run.status;
                                    const isActive = currentRun?.id === run.id;

                                    return (
                                        <div
                                            key={run.id}
                                            onClick={() => setCurrentRun(run.id)}
                                            className={cn(
                                                "group relative p-3 rounded-xl border transition-all duration-200 cursor-pointer stagger-item",
                                                isActive
                                                    ? "border-primary/30 bg-primary/5 shadow-xs"
                                                    : "border-border/50 hover:border-border hover:bg-accent/50"
                                            )}
                                        >
                                            <div className="flex justify-between items-start gap-3">
                                                <div className="flex-1 min-w-0">
                                                    <p className={cn(
                                                        "text-[13px] leading-relaxed font-medium transition-colors",
                                                        isActive
                                                            ? "text-primary"
                                                            : displayStatus === 'failed'
                                                                ? "text-red-500"
                                                                : "text-foreground"
                                                    )}>
                                                        {run.source && run.source !== 'web' && (
                                                            <span className="inline-flex items-center gap-1 mr-1.5 px-1.5 py-0.5 rounded text-xs font-semibold uppercase bg-primary/10 text-primary border border-primary/20">
                                                                <MessageSquare className="w-2.5 h-2.5" />
                                                                {run.source}
                                                            </span>
                                                        )}
                                                        {run.name}
                                                    </p>
                                                </div>
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        const { isGeneratingApp, generateAppFromReport } = useAppStore.getState();
                                                        if (isGeneratingApp) return;
                                                        generateAppFromReport(run.id);
                                                    }}
                                                    disabled={useAppStore.getState().isGeneratingApp}
                                                    className={cn(
                                                        "opacity-0 group-hover:opacity-100 p-1.5 rounded-lg transition-all duration-150",
                                                        useAppStore.getState().isGeneratingApp
                                                            ? "bg-muted text-muted-foreground cursor-not-allowed"
                                                            : "hover:bg-primary/10 text-muted-foreground hover:text-primary"
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

                                            {isActive && (
                                                <div className="mt-3 pt-2.5 border-t border-border/40 flex items-center justify-between animate-content-in">
                                                    <div className="flex items-center gap-3">
                                                        <span className="flex items-center gap-1 text-2xs text-muted-foreground font-mono">
                                                            <Clock className="w-3 h-3" />
                                                            {new Date(run.createdAt).toLocaleDateString()}
                                                        </span>
                                                        {run.total_tokens !== undefined && (
                                                            <span className="text-2xs text-muted-foreground font-mono opacity-70">
                                                                {run.total_tokens.toLocaleString()} tks
                                                            </span>
                                                        )}
                                                        <button
                                                            className="p-1 hover:bg-red-500/10 rounded text-muted-foreground hover:text-red-400 transition-all"
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
                                                        "px-2 py-0.5 rounded-full text-2xs uppercase font-bold tracking-tight",
                                                        displayStatus === 'completed' && "bg-success-muted text-success",
                                                        displayStatus === 'failed' && "bg-red-500/10 text-red-400/80",
                                                        displayStatus === 'running' && "bg-warning-muted text-warning animate-pulse",
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
                    {sidebarTab === 'remme' && <RemmePanel />}
                    {sidebarTab === 'graph' && <GraphPanel />}
                    {sidebarTab === 'explorer' && <ExplorerPanel />}
                    {sidebarTab === 'echo' && <EchoPanel />}
                    {sidebarTab === 'studio' && <StudioSidebar />}
                    {sidebarTab === 'swarm' && <SwarmSidebar />}
                    {sidebarTab === 'canvas' && <CanvasPanel />}
                    {sidebarTab === 'scheduler' && <SchedulerPanel />}
                    {/* Persist AppsSidebar */}
                    <div style={{ display: sidebarTab === 'apps' ? 'block' : 'none', height: '100%' }}>
                        <AppsSidebar />
                    </div>
                    {/* Persist NewsPanel */}
                    <div style={{ display: sidebarTab === 'news' ? 'block' : 'none', height: '100%' }}>
                        <NewsPanel />
                    </div>
                    {sidebarTab === 'learn' && (
                        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4 opacity-50">
                            <div className="p-6 bg-surface-2 rounded-full ring-1 ring-border">
                                <GraduationCap className="w-12 h-12" />
                            </div>
                            <div className="space-y-1">
                                <h2 className="text-xl font-bold text-foreground uppercase tracking-tight">Under Construction</h2>
                                <p className="text-xs text-muted-foreground">This feature is currently in development.</p>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
