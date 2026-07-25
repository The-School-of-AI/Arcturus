import React from 'react';
import {
    PlayCircle, Database, Notebook, Brain, Network,
    LayoutGrid, Code2, Wand2, CalendarClock, Zap,
    Terminal, Newspaper, Shield, Settings, Mic, Users, Plus
} from 'lucide-react';
import { useAppStore } from '@/store';
import type { FloatingPanelType } from '@/store';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Kbd } from '@/components/ui/kbd';
import { ModeBar } from './ModeBar';

// ── Navigation Items ─────────────────────────────────────────────────────────

type NavAction = { type: 'panel'; panelType: FloatingPanelType } | { type: 'fullview'; view: string };

interface QuickNavItem {
    id: string;
    label: string;
    icon: any;
    shortcut?: string;
    action: NavAction;
}

interface QuickNavGroup {
    items: QuickNavItem[];
}

const NAV_GROUPS: QuickNavGroup[] = [
    {
        items: [
            { id: 'echo', label: 'Echo', icon: Mic, shortcut: '1', action: { type: 'fullview', view: 'echo' } },
            { id: 'runs', label: 'Runs', icon: PlayCircle, shortcut: '2', action: { type: 'panel', panelType: 'runs' } },
            { id: 'rag', label: 'RAG', icon: Database, shortcut: '3', action: { type: 'fullview', view: 'rag' } },
            { id: 'notes', label: 'Notes', icon: Notebook, shortcut: '4', action: { type: 'fullview', view: 'notes' } },
            { id: 'remme', label: 'Memory', icon: Brain, shortcut: '5', action: { type: 'panel', panelType: 'remme' } },
            { id: 'graph', label: 'Graph', icon: Network, action: { type: 'fullview', view: 'graph' } },
        ],
    },
    {
        items: [
            { id: 'apps', label: 'Apps', icon: LayoutGrid, shortcut: '6', action: { type: 'fullview', view: 'apps' } },
            { id: 'canvas', label: 'Canvas', icon: LayoutGrid, shortcut: '7', action: { type: 'fullview', view: 'canvas' } },
            { id: 'ide', label: 'IDE', icon: Code2, shortcut: '8', action: { type: 'fullview', view: 'ide' } },
            { id: 'studio', label: 'Forge', icon: Wand2, action: { type: 'fullview', view: 'studio' } },
        ],
    },
    {
        items: [
            { id: 'scheduler', label: 'Scheduler', icon: CalendarClock, action: { type: 'fullview', view: 'scheduler' } },
            { id: 'skills', label: 'Skills', icon: Zap, action: { type: 'fullview', view: 'skills' } },
            { id: 'console', label: 'Console', icon: Terminal, action: { type: 'fullview', view: 'console' } },
            { id: 'news', label: 'News', icon: Newspaper, action: { type: 'fullview', view: 'news' } },
        ],
    },
    {
        items: [
            { id: 'swarm', label: 'Swarm', icon: Users, action: { type: 'fullview', view: 'swarm' } },
            { id: 'admin', label: 'Admin', icon: Shield, action: { type: 'fullview', view: 'admin' } },
            { id: 'settings', label: 'Settings', icon: Settings, action: { type: 'fullview', view: 'settings' } },
        ],
    },
];

// ── Full-view tabs that take over the entire canvas ──────────────────────────
const CANVAS_NATIVE_VIEWS = new Set(['runs', 'echo']);

export const QuickNav: React.FC = () => {
    const setSidebarTab = useAppStore(state => state.setSidebarTab);
    const sidebarTab = useAppStore(state => state.sidebarTab);
    const activeFullView = useAppStore(state => state.activeFullView);
    const setActiveFullView = useAppStore(state => state.setActiveFullView);
    const toggleFloatingPanel = useAppStore(state => state.toggleFloatingPanel);
    const floatingPanels = useAppStore(state => state.floatingPanels);
    const setIsNewRunOpen = useAppStore(state => state.setIsNewRunOpen);

    const handleNavClick = (item: QuickNavItem) => {
        if (item.action.type === 'panel') {
            // Toggle floating panel
            toggleFloatingPanel(item.action.panelType);
            // Also set sidebarTab for state compatibility
            setSidebarTab(item.id as any);
            // Clear full view if one is active
            if (activeFullView) setActiveFullView(null);
        } else {
            // Full-view: check if it's canvas-native or takes over
            if (CANVAS_NATIVE_VIEWS.has(item.action.view)) {
                setSidebarTab(item.action.view as any);
                if (activeFullView) setActiveFullView(null);
            } else {
                setSidebarTab(item.action.view as any);
                setActiveFullView(item.action.view);
            }
        }
    };

    const isItemActive = (item: QuickNavItem): boolean => {
        if (item.action.type === 'panel') {
            return floatingPanels.some(p => p.type === item.action.panelType && !p.isMinimized);
        }
        if (activeFullView === item.action.view) return true;
        if (!activeFullView && sidebarTab === item.id) return true;
        return false;
    };

    // Keyboard shortcuts
    React.useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (!(e.metaKey || e.ctrlKey)) return;
            const allItems = NAV_GROUPS.flatMap(g => g.items);
            const shortcutItem = allItems.find(i => i.shortcut === e.key);
            if (shortcutItem) {
                e.preventDefault();
                handleNavClick(shortcutItem);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [activeFullView, sidebarTab, floatingPanels]);

    return (
        <div className="fixed bottom-3 left-1/2 -translate-x-1/2 z-[80] flex items-center gap-3 animate-dock-rise">
            {/* Mode Bar — left of dock */}
            <ModeBar />

            {/* Main Dock */}
            <div className="quicknav-dock flex items-center gap-0.5 px-2 py-1.5 rounded-2xl">
                {NAV_GROUPS.map((group, groupIdx) => (
                    <React.Fragment key={groupIdx}>
                        {groupIdx > 0 && (
                            <div className="w-px h-5 bg-border/30 mx-0.5" />
                        )}
                        {group.items.map((item) => {
                            const Icon = item.icon;
                            const isActive = isItemActive(item);

                            return (
                                <Tooltip key={item.id} delayDuration={0}>
                                    <TooltipTrigger asChild>
                                        <button
                                            onClick={() => handleNavClick(item)}
                                            className={cn(
                                                "relative flex items-center justify-center w-8 h-8 rounded-xl transition-all duration-150",
                                                isActive
                                                    ? "bg-primary/10 text-primary"
                                                    : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                                            )}
                                        >
                                            <Icon className="w-4 h-4" />
                                            {/* Active dot indicator */}
                                            {isActive && (
                                                <span className="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-primary" />
                                            )}
                                        </button>
                                    </TooltipTrigger>
                                    <TooltipContent side="top" className="flex items-center gap-2">
                                        <span>{item.label}</span>
                                        {item.shortcut && <Kbd>{item.shortcut}</Kbd>}
                                    </TooltipContent>
                                </Tooltip>
                            );
                        })}
                    </React.Fragment>
                ))}

                <div className="w-px h-5 bg-border/30 mx-0.5" />

                {/* Quick New Run button */}
                <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                        <button
                            onClick={() => {
                                setSidebarTab('runs');
                                if (activeFullView) setActiveFullView(null);
                                setTimeout(() => setIsNewRunOpen(true), 100);
                            }}
                            className="flex items-center justify-center w-8 h-8 rounded-xl text-muted-foreground hover:text-primary hover:bg-primary/10 transition-all duration-150"
                        >
                            <Plus className="w-4 h-4" />
                        </button>
                    </TooltipTrigger>
                    <TooltipContent side="top">New Agent Run</TooltipContent>
                </Tooltip>
            </div>
        </div>
    );
};
