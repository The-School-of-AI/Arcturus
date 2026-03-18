import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { WorkspacePanel } from '../workspace/WorkspacePanel';
import { GraphCanvas } from '../graph/GraphCanvas';
import { FlowWorkspace } from '../workspace/FlowWorkspace';
import { RunTimeline } from '@/features/replay/RunTimeline';
import { DocumentViewer } from '../rag/DocumentViewer';
import { DocumentAssistant } from '../rag/DocumentAssistant';
import { NotesEditor } from '../notes/NotesEditor';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { InboxPanel } from '../inbox/InboxPanel';
import CanvasHost from '@/features/canvas/CanvasHost';
import useVoice from '@/hooks/useVoice';

import { AppGrid } from '@/features/apps/components/AppGrid';
import { AppInspector } from '@/features/apps/components/AppInspector';
import { SettingsPage } from '../settings/SettingsPage';
import { RemMeProfileView } from '../remme/RemmeProfileView';
import { KnowledgeGraphExplorer } from '../graph/KnowledgeGraphExplorer';
import { ElectronBrowserView } from '@/features/news/components/ElectronBrowserView';
import { NewsInspector } from '@/features/news/components/NewsInspector';
import { IdeLayout } from '@/features/ide/components/IdeLayout';
import { SchedulerDashboard } from '@/features/scheduler/components/SchedulerDashboard';
import { MissionControl } from '@/features/console/components/MissionControl';
import { SkillsDashboard } from '@/features/skills/components/SkillsDashboard';
import { ForgeDashboard } from '@/features/forge/components/ForgeDashboard';
import { AdminDashboard } from '@/features/admin/AdminDashboard';
import { SwarmGraphView } from '@/features/swarm/SwarmGraphView';
import { AgentPeekPanel } from '@/features/swarm/AgentPeekPanel';
import { useSwarmStore } from '@/features/swarm/useSwarmStore';

// ── Resize Handle ────────────────────────────────────────────────────────────

interface ResizeHandleProps {
    onMouseDown: (e: React.MouseEvent) => void;
}

const ResizeHandle: React.FC<ResizeHandleProps> = ({ onMouseDown }) => (
    <div
        className="relative w-px bg-border hover:bg-primary/40 active:bg-primary cursor-col-resize transition-colors duration-150"
        onMouseDown={onMouseDown}
    >
        <div className="absolute inset-y-0 -left-1.5 -right-1.5 z-10" />
    </div>
);

// ── Main Layout ──────────────────────────────────────────────────────────────

export const AppLayout: React.FC = () => {
    useVoice();

    const {
        sidebarTab, isAppViewMode, showNewsChatPanel,
        selectedNodeId, selectedAppCardId, selectedExplorerNodeId,
        notesActiveDocumentId,
        selectedLibraryComponent, clearSelection, showRagInsights,
        isZenMode, isInboxOpen, setIsInboxOpen,
        isSidebarSubPanelOpen, isSidebarExpanded,
        startEventStream, stopEventStream, currentRun,
        activeSurfaceId, selectedCanvasWidgetId
    } = useAppStore();

    // SSE connection — always active
    useEffect(() => {
        startEventStream();
        return () => stopEventStream();
    }, [startEventStream, stopEventStream]);

    const selectedAgentId = useSwarmStore(s => s.selectedAgentId);

    // Inspector visibility logic
    const isInspectorOpen = React.useMemo(() => {
        if (sidebarTab === 'apps' && selectedAppCardId) return true;
        if (sidebarTab === 'runs' && selectedNodeId) return true;
        if (sidebarTab === 'explorer' && selectedExplorerNodeId) return true;
        if (sidebarTab === 'rag' && showRagInsights) return true;
        if (sidebarTab === 'news' && showNewsChatPanel) return true;
        if (sidebarTab === 'echo' && currentRun) return true;
        if (sidebarTab === 'swarm' && !!selectedAgentId) return true;
        return false;
    }, [sidebarTab, selectedNodeId, selectedAppCardId, selectedExplorerNodeId, showRagInsights, selectedLibraryComponent, showNewsChatPanel, currentRun, selectedAgentId, selectedCanvasWidgetId]);

    // Sidebar sub-panel visibility
    const hideSidebarSubPanel = (isInspectorOpen && sidebarTab !== 'echo' && sidebarTab !== 'canvas') || sidebarTab === 'ide' || sidebarTab === 'console' || sidebarTab === 'skills' || sidebarTab === 'studio' || sidebarTab === 'admin' || !isSidebarSubPanelOpen;

    // Panel sizing — leftWidth is the total width of rail + sub-panel combined.
    // With expanded rail (200px) + sub-panel, we need ~520px default.
    // With collapsed rail (52px) + sub-panel, sub-panel gets ~468px — spacious.
    const [leftWidth, setLeftWidth] = useState(520);
    const [rightWidth, setRightWidth] = useState(450);
    const [isFullScreen, setIsFullScreen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);
    const isDraggingRef = useRef<'left' | 'right' | null>(null);
    const startXRef = useRef(0);
    const startWidthRef = useRef(0);

    const handleMouseDown = useCallback((side: 'left' | 'right') => (e: React.MouseEvent) => {
        e.preventDefault();
        isDraggingRef.current = side;
        startXRef.current = e.clientX;
        startWidthRef.current = side === 'left' ? leftWidth : rightWidth;
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        document.body.classList.add('is-resizing');
    }, [leftWidth, rightWidth]);

    // Escape to clear selection
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') clearSelection();
            // Cmd+. to toggle inspector
            if ((e.metaKey || e.ctrlKey) && e.key === '.') {
                e.preventDefault();
                clearSelection();
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [clearSelection]);

    // Drag resize handling
    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isDraggingRef.current) return;
            const delta = e.clientX - startXRef.current;
            if (isDraggingRef.current === 'left') {
                setLeftWidth(Math.max(200, Math.min(700, startWidthRef.current + delta)));
            } else {
                setRightWidth(Math.max(250, Math.min(800, startWidthRef.current - delta)));
            }
        };

        const handleMouseUp = () => {
            isDraggingRef.current = null;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            document.body.classList.remove('is-resizing');
        };

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };
    }, []);

    // RAG indexing status check
    useEffect(() => {
        const checkRagStatus = async () => {
            try {
                const { api, API_BASE } = await import('@/lib/api');
                const res = await api.get(`${API_BASE}/rag/indexing_status`);
                if (res.data.active) {
                    useAppStore.getState().startRagPolling();
                }
            } catch (e) {
                console.error("Failed initial RAG status check", e);
            }
        };
        checkRagStatus();
    }, []);

    // Track previous tab for content transitions
    const [prevTab, setPrevTab] = React.useState(sidebarTab);
    const [contentKey, setContentKey] = React.useState(0);
    React.useEffect(() => {
        if (sidebarTab !== prevTab) {
            setPrevTab(sidebarTab);
            setContentKey(k => k + 1);
        }
    }, [sidebarTab, prevTab]);

    // Calculate sidebar rail width based on expanded state
    const sidebarRailWidth = isSidebarExpanded ? 200 : 52;

    return (
        <div className="h-screen w-screen flex flex-col bg-background text-foreground overflow-hidden">
            {!isAppViewMode && <Header />}

            {/* Inbox Overlay */}
            {isInboxOpen && (
                <InboxPanel onClose={() => setIsInboxOpen(false)} />
            )}

            <div ref={containerRef} className="flex-1 flex overflow-hidden relative z-20 gap-0">
                {/* Left Sidebar */}
                {!(isFullScreen && sidebarTab === 'apps') && !isAppViewMode && !(sidebarTab === 'news' && showNewsChatPanel) && !isZenMode && (
                    <>
                        <div
                            className="h-full bg-sidebar flex-shrink-0 overflow-hidden flex flex-col transition-all duration-300 ease-out"
                            style={{ width: hideSidebarSubPanel ? sidebarRailWidth : leftWidth }}
                        >
                            <Sidebar hideSubPanel={hideSidebarSubPanel} />
                        </div>

                        {!hideSidebarSubPanel && <ResizeHandle onMouseDown={handleMouseDown('left')} />}
                    </>
                )}

                {/* Center Content */}
                <div className="flex-1 flex flex-col min-w-0 bg-background relative overflow-hidden">
                    {!isAppViewMode && (
                        <>
                            {/* Persistent App Grid */}
                            <div className={cn("w-full h-full", sidebarTab === 'apps' ? "block" : "hidden")}>
                                <AppGrid isFullScreen={isFullScreen} onToggleFullScreen={() => setIsFullScreen(!isFullScreen)} />
                            </div>

                            {/* Persistent News Browser */}
                            <div className={cn("w-full h-full", sidebarTab === 'news' ? "block" : "hidden")}>
                                <ElectronBrowserView />
                            </div>

                            {/* Dynamic Views — with content transition */}
                            {sidebarTab !== 'apps' && sidebarTab !== 'news' && (
                                <div key={contentKey} className="w-full h-full animate-content-in">
                                    {sidebarTab === 'settings' ? (
                                        <SettingsPage />
                                    ) : sidebarTab === 'rag' ? (
                                        <DocumentViewer />
                                    ) : sidebarTab === 'notes' ? (
                                        notesActiveDocumentId && /\.(pdf|png|jpg|jpeg|gif|webp|docx?|json)$/i.test(notesActiveDocumentId)
                                            ? <DocumentViewer context="notes" />
                                            : <NotesEditor />
                                    ) : sidebarTab === 'remme' ? (
                                        <RemMeProfileView />
                                    ) : sidebarTab === 'graph' ? (
                                        <KnowledgeGraphExplorer />
                                    ) : sidebarTab === 'explorer' ? (
                                        <FlowWorkspace />
                                    ) : sidebarTab === 'ide' ? (
                                        <IdeLayout />
                                    ) : sidebarTab === 'scheduler' ? (
                                        <SchedulerDashboard />
                                    ) : sidebarTab === 'skills' ? (
                                        <SkillsDashboard />
                                    ) : sidebarTab === 'studio' ? (
                                        <ForgeDashboard />
                                    ) : sidebarTab === 'console' ? (
                                        <MissionControl />
                                    ) : sidebarTab === 'admin' ? (
                                        <AdminDashboard />
                                    ) : sidebarTab === 'echo' ? (
                                        <>
                                            <GraphCanvas />
                                            <RunTimeline />
                                        </>
                                    ) : sidebarTab === 'canvas' ? (
                                        <CanvasHost surfaceId={activeSurfaceId} />
                                    ) : sidebarTab === 'swarm' ? (
                                        <SwarmGraphView />
                                    ) : (
                                        <>
                                            <GraphCanvas />
                                            <RunTimeline />
                                        </>
                                    )}
                                </div>
                            )}
                        </>
                    )}

                    {/* App runtime view */}
                    {isAppViewMode && (
                        <div className="absolute inset-0 z-50 bg-background flex items-center justify-center">
                            <div className="w-full h-full p-4">
                                <AppGrid isFullScreen={true} onToggleFullScreen={() => { }} />
                            </div>
                        </div>
                    )}
                </div>

                {/* Right Inspector Panel — slides in */}
                {isInspectorOpen && !isFullScreen && !isAppViewMode && (
                    <>
                        <ResizeHandle onMouseDown={handleMouseDown('right')} />
                        <div
                            className="h-full bg-card border-l border-border flex-shrink-0 flex flex-col overflow-hidden animate-panel-in-right"
                            style={{ width: rightWidth }}
                        >
                            {sidebarTab === 'apps' ? <AppInspector /> :
                                sidebarTab === 'news' ? <NewsInspector /> :
                                    sidebarTab === 'swarm' ? <AgentPeekPanel /> :
                                        (sidebarTab === 'rag' || sidebarTab === 'notes') ? <DocumentAssistant context={sidebarTab as 'rag' | 'notes'} /> :
                                            <WorkspacePanel />}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};
