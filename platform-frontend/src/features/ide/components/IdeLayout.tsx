import React from 'react';
import { Group as PanelGroup, Panel, Separator as PanelResizeHandle } from 'react-resizable-panels';
import { useIdeStore, type IdeSidebarTab } from '../store/ideStore';
import { cn } from '@/lib/utils';
import { FileCode, Search, GitBranch, ListTodo, PanelLeft, PanelBottom, PanelRight, FlaskConical, Timer, Pause, Play } from 'lucide-react';
import { useAppStore } from '@/store';
import axios from 'axios';
import { API_BASE } from '@/lib/api';

// Components
import { EditorArea } from './EditorArea';
import { TerminalPanel } from './TerminalPanel';
import { IdeAgentPanel } from './IdeAgentPanel';

// Sidebars
import { PlanSidebar } from './Sidebars/PlanSidebar';
import { ExplorerSidebar } from './Sidebars/ExplorerSidebar';
import { SearchSidebar } from './Sidebars/SearchSidebar';
import { GitSidebar } from './Sidebars/GitSidebar';
import { TestsSidebar } from './Sidebars/TestsSidebar';

const IdeSidebar = () => {
    const { activeSidebarTab, setActiveSidebarTab } = useIdeStore();

    const tabs: { id: IdeSidebarTab; icon: React.ElementType; label: string }[] = [
        { id: 'plan', icon: ListTodo, label: 'Plan' },
        { id: 'explorer', icon: FileCode, label: 'Explorer' },
        { id: 'tests', icon: FlaskConical, label: 'Tests' },
        { id: 'search', icon: Search, label: 'Search' },
        { id: 'git', icon: GitBranch, label: 'Git' },
    ];

    const renderSidebar = () => {
        switch (activeSidebarTab) {
            case 'plan': return <PlanSidebar />;
            case 'explorer': return <ExplorerSidebar />;
            case 'tests': return <TestsSidebar />;
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
                            "flex items-center justify-center gap-1.5 px-1 py-1.5 rounded-xs transition-all flex-1 text-[11px] font-medium select-none",
                            activeSidebarTab === tab.id
                                ? "bg-accent text-accent-foreground shadow-sm ring-1 ring-border/50"
                                : "text-muted-foreground hover:bg-muted hover:text-foreground alpha-60"
                        )}
                        title={tab.label}
                    >
                        <tab.icon className="w-2.5 h-2.5" />
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

// Timer display component for status bar
const ArcturusTimerDisplay = () => {
    const { arcturusTimer, pauseArcturusTimer, resumeArcturusTimer } = useIdeStore();

    if (arcturusTimer.countdown === null && !arcturusTimer.isPaused) {
        return null;
    }

    return (
        <div className="flex items-center gap-1.5 px-2 py-0.5  bg-primary/10 border border-primary/20">
            <Timer className="w-3 h-3 text-primary" />
            {arcturusTimer.isPaused ? (
                <>
                    <span className="text-amber-400">Paused</span>
                    <button
                        onClick={resumeArcturusTimer}
                        className="p-0.5 hover:bg-white/10  transition-colors"
                        title="Resume auto-commit timer"
                    >
                        <Play className="w-2.5 h-2.5 text-green-400" />
                    </button>
                </>
            ) : (
                <>
                    <span className="text-primary font-mono">{arcturusTimer.countdown}s</span>
                    <button
                        onClick={pauseArcturusTimer}
                        className="p-0.5 hover:bg-white/10 rounded transition-colors"
                        title="Pause auto-commit"
                    >
                        <Pause className="w-2.5 h-2.5 text-amber-400" />
                    </button>
                </>
            )}
        </div>
    );
};

// Headless controller to manage Arcturus logic
const ArcturusController = () => {
    const { explorerRootPath, ideOpenDocuments, markIdeDocumentSaved } = useAppStore();
    const { arcturusTimer, tickArcturusTimer, advanceArcturusTier, setTestFiles, startArcturusTimer } = useIdeStore();
    const [isCommitting, setIsCommitting] = React.useState(false);

    // Timer Tick
    React.useEffect(() => {
        const interval = setInterval(() => {
            tickArcturusTimer();
        }, 1000);
        return () => clearInterval(interval);
    }, [tickArcturusTimer]);

    // Fetch Test Manifest & Git Init
    React.useEffect(() => {
        if (!explorerRootPath) return;

        const initArcturus = async () => {
            try {
                // Check status first to see if repo exists
                let needsInit = false;
                try {
                    const res = await axios.get(`${API_BASE}/git/status`, { params: { path: explorerRootPath } });
                    // API returns 200 with "not a git repo" if not initialized
                    if (res.data?.branch === "not a git repo") {
                        needsInit = true;
                    }
                } catch (e: any) {
                    // or if request actually failed
                    needsInit = true;
                }

                if (needsInit) {
                    console.log("[Arcturus] Initializing repository...");
                    await axios.post(`${API_BASE}/git/arcturus/init`, { path: explorerRootPath });
                    // Signal to GitSidebar to refresh
                    window.dispatchEvent(new Event('arcturus:git-init'));
                    fetchManifest();
                }
            } catch (e) {
                console.error("[Arcturus] Failed to init", e);
            }
        };

        const fetchManifest = async () => {
            try {
                const res = await axios.get(`${API_BASE}/tests/manifest`, {
                    params: { path: explorerRootPath }
                });
                if (res.data?.manifest) {
                    setTestFiles(Object.keys(res.data.manifest));
                }
            } catch (e) {
                // Ignore errors if testing backend not ready
            }
        };

        const checkPendingChanges = async () => {
            try {
                const statusRes = await axios.get(`${API_BASE}/git/status`, { params: { path: explorerRootPath } });
                if (!statusRes.data.clean && arcturusTimer.countdown === null && !arcturusTimer.isPaused) {
                    console.log("[Arcturus] Pending changes detected, starting timer.");
                    startArcturusTimer();
                }
            } catch (e) {
                console.error("[Arcturus] Failed to check status for timer", e);
            }
        };

        const init = async () => {
            await initArcturus();
            await fetchManifest();
            await checkPendingChanges();
        };

        init();

        // Poll every 10s
        const interval = setInterval(() => {
            fetchManifest();
            // Also check status periodically to ensure we don't miss external changes
            axios.get(`${API_BASE}/git/status`, { params: { path: explorerRootPath } })
                .then(res => {
                    const { countdown, isPaused } = useIdeStore.getState().arcturusTimer;
                    if (!res.data.clean && countdown === null && !isPaused) {
                        console.log("[Arcturus] Pending changes detected (poll), starting timer.");
                        useIdeStore.getState().startArcturusTimer();
                    }
                }).catch(() => { });
        }, 10000);
        return () => clearInterval(interval);
    }, [explorerRootPath, setTestFiles, arcturusTimer.countdown, startArcturusTimer]);

    // Auto-Commit Trigger
    React.useEffect(() => {
        const performAutoCommit = async () => {
            if (arcturusTimer.countdown === 0 && !isCommitting && explorerRootPath) {
                setIsCommitting(true);
                try {
                    console.log("[Arcturus] Timer expired. Auto-committing...");
                    // 1. Save all dirty files
                    const dirtyDocs = ideOpenDocuments.filter(doc => doc.isDirty);
                    await Promise.all(dirtyDocs.map(async (doc) => {
                        if (doc.content) {
                            await window.electronAPI.invoke('fs:writeFile', {
                                path: doc.id,
                                content: doc.content
                            });
                            markIdeDocumentSaved(doc.id);
                        }
                    }));

                    // 2. Commit to arcturus branch
                    // We rely on the backend to stage all changes (including new files)
                    await axios.post(`${API_BASE}/git/arcturus/commit`, {
                        path: explorerRootPath,
                    });

                    // 3. Advance tier (backoff)
                    advanceArcturusTier();

                    // 4. Trigger Intelligent Test Generation
                    // We fire this for every saved file. The backend uses AST hashing to determine if actual generation is needed.
                    // We run this in background (don't await strictly for the UI to unblock)
                    dirtyDocs.forEach(doc => {
                        // Extract relative path
                        let relativePath = doc.id;
                        if (relativePath.startsWith(explorerRootPath)) {
                            relativePath = relativePath.substring(explorerRootPath.length);
                            if (relativePath.startsWith('/')) relativePath = relativePath.substring(1);
                        }

                        // Only check python files for now
                        if (relativePath.endsWith('.py')) {
                            console.log(`[Arcturus] Triggering smart test check for: ${relativePath}`);
                            axios.post(`${API_BASE}/tests/generate`, {
                                path: explorerRootPath,
                                file_path: relativePath,
                                force: false // Respect semantic hashing
                            }).then(res => {
                                if (res.data?.success && res.data?.message) {
                                    console.log(`[Arcturus] Tests updated for ${relativePath}:`, res.data.message);
                                }
                            }).catch(e => {
                                console.error(`[Arcturus] Test generation failed for ${relativePath}`, e);
                            });
                        }
                    });

                } catch (e) {
                    console.error("Auto-commit failed", e);
                } finally {
                    setIsCommitting(false);
                    // Clear timer logic is handled by advanceArcturusTier (sets countdown to null)
                }
            }
        };

        performAutoCommit();
    }, [arcturusTimer.countdown, isCommitting, explorerRootPath, ideOpenDocuments, markIdeDocumentSaved, advanceArcturusTier]);

    return null;
};

export const IdeLayout: React.FC = () => {
    const { isLeftPanelVisible, isRightPanelVisible, isBottomPanelVisible, arcturusTimer } = useIdeStore();
    const [layoutKey, setLayoutKey] = React.useState(0);

    const resetLayout = () => {
        useIdeStore.getState().setActiveSidebarTab('explorer');
        // Force re-mount of PanelGroup to apply defaultSizes
        setLayoutKey(prev => prev + 1);
    };

    return (
        <div className="h-full w-full bg-transparent flex flex-col overflow-hidden">
            <ArcturusController />
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
                        <span>arcturus</span>
                    </div>

                    {/* Arcturus Timer */}
                    <ArcturusTimerDisplay />
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
