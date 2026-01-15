import React from 'react';
import { Group as PanelGroup, Panel, Separator as PanelResizeHandle } from 'react-resizable-panels';
import { useIdeStore, type IdeSidebarTab } from '../store/ideStore';
import { cn } from '@/lib/utils';
import { FileCode, Search, GitBranch, ListTodo, PanelLeft, PanelBottom, PanelRight } from 'lucide-react';
import { useAppStore } from '@/store';

// Components
import { EditorArea } from './EditorArea';
import { TerminalPanel } from './TerminalPanel';
import { IdeAgentPanel } from './IdeAgentPanel';

// Sidebars
import { PlanSidebar } from './Sidebars/PlanSidebar';
import { ExplorerSidebar } from './Sidebars/ExplorerSidebar';
import { SearchSidebar } from './Sidebars/SearchSidebar';
import { GitSidebar } from './Sidebars/GitSidebar';

const IdeSidebar = () => {
    const { activeSidebarTab, setActiveSidebarTab } = useIdeStore();

    const tabs: { id: IdeSidebarTab; icon: React.ElementType; label: string }[] = [
        { id: 'plan', icon: ListTodo, label: 'Plan' },
        { id: 'explorer', icon: FileCode, label: 'Explorer' },
        { id: 'search', icon: Search, label: 'Search' },
        { id: 'git', icon: GitBranch, label: 'Git' },
    ];

    const renderSidebar = () => {
        switch (activeSidebarTab) {
            case 'plan': return <PlanSidebar />;
            case 'explorer': return <ExplorerSidebar />;
            case 'search': return <SearchSidebar />;
            case 'git': return <GitSidebar />;
            default: return null;
        }
    };

    return (
        <div className="h-full flex flex-col bg-muted/10 border-r border-border/50">
            {/* Horizontal Tool Switcher - The "Tab" Concept */}
            <div className="flex items-center px-1 py-1 gap-1 border-b border-border/50 bg-background/50 backdrop-blur-sm">
                {tabs.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveSidebarTab(tab.id)}
                        className={cn(
                            "flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md transition-all flex-1 text-[11px] font-medium select-none",
                            activeSidebarTab === tab.id
                                ? "bg-accent text-accent-foreground shadow-sm ring-1 ring-border/50"
                                : "text-muted-foreground hover:bg-muted hover:text-foreground alpha-60"
                        )}
                        title={tab.label}
                    >
                        <tab.icon className="w-3.5 h-3.5" />
                        <span>{tab.label}</span>
                    </button>
                ))}
            </div>

            <div className="flex-1 overflow-hidden">
                {renderSidebar()}
            </div>
        </div>
    );
};

export const IdeLayout: React.FC = () => {
    const { isLeftPanelVisible, isRightPanelVisible, isBottomPanelVisible } = useIdeStore();
    const [layoutKey, setLayoutKey] = React.useState(0);

    const resetLayout = () => {
        useIdeStore.getState().setActiveSidebarTab('explorer');
        // Force re-mount of PanelGroup to apply defaultSizes
        setLayoutKey(prev => prev + 1);
    };

    return (
        <div className="h-full w-full bg-transparent flex flex-col overflow-hidden">
            {/* Key forces re-mount on reset */}
            <PanelGroup key={layoutKey} orientation="horizontal">

                {/* LEFT PANEL: TOOLS */}
                {isLeftPanelVisible && (
                    <>
                        {/* @ts-ignore */}
                        <Panel defaultSize={20} minSize={15} order={1} className="flex flex-col">
                            <IdeSidebar />
                        </Panel>
                        <PanelResizeHandle className="w-px bg-border/50 hover:bg-primary/50 transition-colors" />
                    </>
                )}

                {/* CENTER PANEL: EDITOR + TERMINAL */}
                {/* @ts-ignore */}
                <Panel defaultSize={isLeftPanelVisible && isRightPanelVisible ? 55 : 80} minSize={30} order={2} className="flex flex-col">
                    <PanelGroup orientation="vertical">
                        {/* EDITOR AREA */}
                        <Panel defaultSize={70} minSize={30}>
                            <EditorArea />
                        </Panel>

                        {isBottomPanelVisible && (
                            <>
                                <PanelResizeHandle className="h-px bg-border/50 hover:bg-primary/50 transition-colors" />
                                { /* TERMINAL AREA */}
                                <Panel defaultSize={30} minSize={10}>
                                    <TerminalPanel />
                                </Panel>
                            </>
                        )}
                    </PanelGroup>
                </Panel>

                {/* RIGHT PANEL: INSIGHTS (IdeAgentPanel) */}
                {isRightPanelVisible && (
                    <>
                        <PanelResizeHandle className="w-px bg-border/50 hover:bg-primary/50 transition-colors" />
                        {/* @ts-ignore */}
                        <Panel defaultSize={25} minSize={20} order={3}>
                            <div className="h-full border-l border-border/50 bg-background/50 backdrop-blur-md overflow-hidden">
                                <IdeAgentPanel />
                            </div>
                        </Panel>
                    </>
                )}
            </PanelGroup>

            {/* Status Bar (Global Bottom) */}
            <div className="h-6 bg-primary/5 border-t border-border/50 flex items-center px-3 text-[10px] text-muted-foreground gap-4 select-none justify-between">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-1.5 hover:text-foreground cursor-pointer transition-colors">
                        <GitBranch className="w-3 h-3" />
                        <span>main*</span>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <div className="flex items-center bg-transparent rounded p-0.5 gap-px">
                        <button
                            onClick={() => useIdeStore.getState().toggleLeftPanel()}
                            className={cn("p-1 rounded hover:bg-white/10 transition-colors", isLeftPanelVisible ? "text-primary bg-white/5" : "text-muted-foreground/50")}
                            title="Toggle Left Panel"
                        >
                            <PanelLeft className="w-3.5 h-3.5" />
                        </button>
                        <button
                            onClick={() => useIdeStore.getState().toggleBottomPanel()}
                            className={cn("p-1 rounded hover:bg-white/10 transition-colors", isBottomPanelVisible ? "text-primary bg-white/5" : "text-muted-foreground/50")}
                            title="Toggle Terminal"
                        >
                            <PanelBottom className="w-3.5 h-3.5" />
                        </button>
                        <button
                            onClick={() => useIdeStore.getState().toggleRightPanel()}
                            className={cn("p-1 rounded hover:bg-white/10 transition-colors", isRightPanelVisible ? "text-primary bg-white/5" : "text-muted-foreground/50")}
                            title="Toggle Right Panel"
                        >
                            <PanelRight className="w-3.5 h-3.5" />
                        </button>
                    </div>

                    <div className="w-px h-3 bg-border/50 mx-1" />

                    <button
                        onClick={resetLayout}
                        className="px-2 py-0.5 rounded hover:bg-white/10 transition-colors text-muted-foreground hover:text-foreground"
                        title="Reset Layout Sizes"
                    >
                        Reset
                    </button>
                </div>

                <div className="flex items-center gap-4">
                    <span>Ln 12, Col 45</span>
                    <span>UTF-8</span>
                    <span>TypeScript React</span>
                </div>
            </div>
        </div>
    );
};
