import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    PlayCircle, Database, Notebook, Brain, Network, LayoutGrid,
    Code2, Wand2, CalendarClock, Zap, Terminal, Newspaper,
    Shield, Settings, Mic, Search, Plus, Moon, Sun,
    FolderOpen, BarChart3, RefreshCw, ArrowRight
} from 'lucide-react';
import { useAppStore } from '@/store';
import { useTheme } from '@/components/theme';
import { cn } from '@/lib/utils';
import { Kbd } from '@/components/ui/kbd';

// ── Types ────────────────────────────────────────────────────────────────────

interface CommandItem {
    id: string;
    label: string;
    description?: string;
    icon: any;
    category: 'navigate' | 'action' | 'settings';
    shortcut?: string;
    action: () => void;
    keywords?: string[];
}

// ── Fuzzy match helper ───────────────────────────────────────────────────────

function fuzzyMatch(query: string, text: string): boolean {
    const q = query.toLowerCase();
    const t = text.toLowerCase();
    if (t.includes(q)) return true;

    let qi = 0;
    for (let ti = 0; ti < t.length && qi < q.length; ti++) {
        if (t[ti] === q[qi]) qi++;
    }
    return qi === q.length;
}

// ── Command Palette Component ────────────────────────────────────────────────

export const CommandPalette: React.FC = () => {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [selectedIndex, setSelectedIndex] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const listRef = useRef<HTMLDivElement>(null);

    const setSidebarTab = useAppStore(state => state.setSidebarTab);
    const setIsNewRunOpen = useAppStore(state => state.setIsNewRunOpen);
    const setIsSpacesModalOpen = useAppStore(state => state.setIsSpacesModalOpen);
    const fetchRuns = useAppStore(state => state.fetchRuns);
    const fetchApps = useAppStore(state => state.fetchApps);
    const { theme, toggleTheme } = useTheme();

    // Build command list
    const commands: CommandItem[] = useMemo(() => [
        // ── Navigate ──
        { id: 'nav-echo', label: 'Echo', description: 'Voice assistant & agent interaction', icon: Mic, category: 'navigate', shortcut: '⌘1', action: () => setSidebarTab('echo'), keywords: ['voice', 'speak', 'talk'] },
        { id: 'nav-runs', label: 'Agent Runs', description: 'Task executions & history', icon: PlayCircle, category: 'navigate', shortcut: '⌘2', action: () => setSidebarTab('runs'), keywords: ['agent', 'execute', 'task'] },
        { id: 'nav-rag', label: 'RAG Documents', description: 'Knowledge base & documents', icon: Database, category: 'navigate', shortcut: '⌘3', action: () => setSidebarTab('rag'), keywords: ['documents', 'knowledge', 'upload', 'pdf'] },
        { id: 'nav-notes', label: 'Notes', description: 'Markdown notes & wiki', icon: Notebook, category: 'navigate', shortcut: '⌘4', action: () => setSidebarTab('notes'), keywords: ['markdown', 'write', 'editor'] },
        { id: 'nav-memory', label: 'Memory Vault', description: 'Persistent memory & facts', icon: Brain, category: 'navigate', shortcut: '⌘5', action: () => setSidebarTab('remme'), keywords: ['remme', 'remember', 'facts', 'profile'] },
        { id: 'nav-graph', label: 'Knowledge Graph', description: 'Entity & relationship explorer', icon: Network, category: 'navigate', action: () => setSidebarTab('graph'), keywords: ['neo4j', 'entities', 'relationships'] },
        { id: 'nav-apps', label: 'App Builder', description: 'Dashboard builder with widgets', icon: LayoutGrid, category: 'navigate', shortcut: '⌘6', action: () => setSidebarTab('apps'), keywords: ['dashboard', 'widgets', 'charts'] },
        { id: 'nav-canvas', label: 'Canvas', description: 'Interactive widget surface', icon: LayoutGrid, category: 'navigate', shortcut: '⌘7', action: () => setSidebarTab('canvas'), keywords: ['whiteboard', 'draw', 'interactive'] },
        { id: 'nav-ide', label: 'IDE', description: 'Code editor with terminal', icon: Code2, category: 'navigate', shortcut: '⌘8', action: () => setSidebarTab('ide'), keywords: ['code', 'editor', 'terminal', 'git'] },
        { id: 'nav-forge', label: 'Forge', description: 'Document & presentation studio', icon: Wand2, category: 'navigate', action: () => setSidebarTab('studio'), keywords: ['slides', 'presentation', 'document', 'studio'] },
        { id: 'nav-scheduler', label: 'Scheduler', description: 'Automated recurring tasks', icon: CalendarClock, category: 'navigate', action: () => setSidebarTab('scheduler'), keywords: ['cron', 'automate', 'recurring'] },
        { id: 'nav-skills', label: 'Skill Store', description: 'Agent plugin marketplace', icon: Zap, category: 'navigate', action: () => setSidebarTab('skills'), keywords: ['plugins', 'install', 'marketplace'] },
        { id: 'nav-console', label: 'Mission Control', description: 'System event log', icon: Terminal, category: 'navigate', action: () => setSidebarTab('console'), keywords: ['logs', 'events', 'debug'] },
        { id: 'nav-news', label: 'News Feed', description: 'RSS feeds & web browser', icon: Newspaper, category: 'navigate', action: () => setSidebarTab('news'), keywords: ['rss', 'articles', 'browse'] },
        { id: 'nav-admin', label: 'Admin', description: 'System monitoring & diagnostics', icon: Shield, category: 'navigate', action: () => setSidebarTab('admin'), keywords: ['health', 'monitoring', 'flags'] },
        { id: 'nav-settings', label: 'Settings', description: 'Configuration & integrations', icon: Settings, category: 'navigate', action: () => setSidebarTab('settings'), keywords: ['config', 'api', 'keys', 'model'] },

        // ── Actions ──
        { id: 'act-new-run', label: 'New Agent Run', description: 'Start a new agent task', icon: Plus, category: 'action', action: () => { setSidebarTab('runs'); setTimeout(() => setIsNewRunOpen(true), 100); }, keywords: ['start', 'create', 'run'] },
        { id: 'act-spaces', label: 'Manage Spaces', description: 'Create or switch project spaces', icon: FolderOpen, category: 'action', action: () => setIsSpacesModalOpen(true), keywords: ['project', 'workspace', 'switch'] },
        { id: 'act-refresh', label: 'Refresh Data', description: 'Reload current view data', icon: RefreshCw, category: 'action', action: () => { fetchRuns(); fetchApps(); }, keywords: ['reload', 'update'] },

        // ── Settings ──
        { id: 'set-theme', label: `Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`, description: 'Toggle color theme', icon: theme === 'dark' ? Sun : Moon, category: 'settings', action: toggleTheme, keywords: ['theme', 'dark', 'light', 'mode'] },
    ], [setSidebarTab, setIsNewRunOpen, setIsSpacesModalOpen, fetchRuns, fetchApps, theme, toggleTheme]);

    // Filter commands
    const filtered = useMemo(() => {
        if (!query.trim()) return commands;
        return commands.filter(cmd =>
            fuzzyMatch(query, cmd.label) ||
            fuzzyMatch(query, cmd.description || '') ||
            (cmd.keywords || []).some(kw => fuzzyMatch(query, kw))
        );
    }, [query, commands]);

    // Group filtered results by category
    const grouped = useMemo(() => {
        const groups: { label: string; items: CommandItem[] }[] = [];
        const nav = filtered.filter(c => c.category === 'navigate');
        const act = filtered.filter(c => c.category === 'action');
        const set = filtered.filter(c => c.category === 'settings');
        if (nav.length) groups.push({ label: 'Navigate', items: nav });
        if (act.length) groups.push({ label: 'Actions', items: act });
        if (set.length) groups.push({ label: 'Settings', items: set });
        return groups;
    }, [filtered]);

    // Flat list for keyboard navigation
    const flatItems = useMemo(() => grouped.flatMap(g => g.items), [grouped]);

    // Reset selection when results change
    useEffect(() => {
        setSelectedIndex(0);
    }, [query]);

    // Open/close with ⌘K
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                setOpen(prev => !prev);
                setQuery('');
                setSelectedIndex(0);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, []);

    // Focus input when opened
    useEffect(() => {
        if (open) {
            requestAnimationFrame(() => inputRef.current?.focus());
        }
    }, [open]);

    // Execute selected command
    const executeCommand = useCallback((item: CommandItem) => {
        setOpen(false);
        setQuery('');
        item.action();
    }, []);

    // Keyboard navigation
    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setSelectedIndex(i => Math.min(i + 1, flatItems.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setSelectedIndex(i => Math.max(i - 1, 0));
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (flatItems[selectedIndex]) {
                executeCommand(flatItems[selectedIndex]);
            }
        } else if (e.key === 'Escape') {
            setOpen(false);
        }
    }, [flatItems, selectedIndex, executeCommand]);

    // Scroll selected item into view
    useEffect(() => {
        const el = listRef.current?.querySelector(`[data-index="${selectedIndex}"]`);
        el?.scrollIntoView({ block: 'nearest' });
    }, [selectedIndex]);

    if (!open) return null;

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 z-[100] bg-black/40 backdrop-blur-sm animate-fade-in"
                onClick={() => setOpen(false)}
            />

            {/* Palette */}
            <div className="fixed left-1/2 top-[20%] -translate-x-1/2 z-[101] w-full max-w-[560px] animate-scale-in">
                <div className="bg-popover border border-border rounded-2xl shadow-modal overflow-hidden">
                    {/* Search Input */}
                    <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
                        <Search className="w-4 h-4 text-muted-foreground shrink-0" />
                        <input
                            ref={inputRef}
                            value={query}
                            onChange={e => setQuery(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Search commands, navigate, take action..."
                            className="flex-1 bg-transparent border-none outline-none text-sm text-foreground placeholder:text-muted-foreground/60"
                            autoComplete="off"
                            spellCheck={false}
                        />
                        <Kbd className="opacity-60">esc</Kbd>
                    </div>

                    {/* Results */}
                    <div ref={listRef} className="max-h-[360px] overflow-y-auto py-2">
                        {grouped.length === 0 && (
                            <div className="px-4 py-8 text-center">
                                <p className="text-sm text-muted-foreground">No results found</p>
                                <p className="text-xs text-muted-foreground/60 mt-1">Try a different search term</p>
                            </div>
                        )}

                        {grouped.map((group) => {
                            const groupStartIndex = flatItems.indexOf(group.items[0]);
                            return (
                                <div key={group.label}>
                                    <div className="px-4 py-1.5">
                                        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/50">
                                            {group.label}
                                        </span>
                                    </div>
                                    {group.items.map((item, itemIdx) => {
                                        const globalIndex = groupStartIndex + itemIdx;
                                        const isSelected = globalIndex === selectedIndex;
                                        const Icon = item.icon;

                                        return (
                                            <button
                                                key={item.id}
                                                data-index={globalIndex}
                                                onClick={() => executeCommand(item)}
                                                onMouseEnter={() => setSelectedIndex(globalIndex)}
                                                className={cn(
                                                    "w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors",
                                                    isSelected
                                                        ? "bg-accent text-accent-foreground"
                                                        : "text-foreground hover:bg-accent/50"
                                                )}
                                            >
                                                <div className={cn(
                                                    "w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-colors",
                                                    isSelected ? "bg-primary/10 text-primary" : "bg-surface-2 text-muted-foreground"
                                                )}>
                                                    <Icon className="w-4 h-4" />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="text-sm font-medium truncate">{item.label}</div>
                                                    {item.description && (
                                                        <div className="text-xs text-muted-foreground truncate">{item.description}</div>
                                                    )}
                                                </div>
                                                {item.shortcut && (
                                                    <Kbd className="shrink-0">{item.shortcut}</Kbd>
                                                )}
                                                {isSelected && (
                                                    <ArrowRight className="w-3 h-3 text-muted-foreground shrink-0" />
                                                )}
                                            </button>
                                        );
                                    })}
                                </div>
                            );
                        })}
                    </div>

                    {/* Footer */}
                    <div className="px-4 py-2 border-t border-border flex items-center justify-between">
                        <div className="flex items-center gap-3 text-2xs text-muted-foreground/60">
                            <span className="flex items-center gap-1"><Kbd>↑↓</Kbd> navigate</span>
                            <span className="flex items-center gap-1"><Kbd>↵</Kbd> select</span>
                            <span className="flex items-center gap-1"><Kbd>esc</Kbd> close</span>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
};
