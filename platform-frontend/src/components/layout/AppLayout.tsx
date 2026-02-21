import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { WorkspacePanel } from '../workspace/WorkspacePanel';
import { GraphCanvas } from '../graph/GraphCanvas';
import { FlowWorkspace } from '../workspace/FlowWorkspace';
import { RunTimeline } from '@/features/replay/RunTimeline';
import { GripVertical } from 'lucide-react';
import { DocumentViewer } from '../rag/DocumentViewer';
import { DocumentAssistant } from '../rag/DocumentAssistant';
import { NotesEditor } from '../notes/NotesEditor';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { Meteors } from '../ui/meteors';
import { InboxPanel } from '../inbox/InboxPanel';
import CanvasHost from '@/features/canvas/CanvasHost';

interface ResizeHandleProps {
    onMouseDown: (e: React.MouseEvent) => void;
}

const ResizeHandle: React.FC<ResizeHandleProps> = ({ onMouseDown }) => (
    <div
        className="w-1 cursor-col-resize group relative flex items-center justify-center hover:bg-primary/30 active:bg-primary/50 transition-colors"
        onMouseDown={onMouseDown}
    >
        <div className="absolute z-10 flex items-center justify-center w-4 h-8 rounded bg-muted border border-border opacity-0 group-hover:opacity-100 transition-opacity">
            <GripVertical className="w-3 h-3 text-muted-foreground" />
        </div>
    </div>
);

import { AppGrid } from '@/features/apps/components/AppGrid';
import { AppInspector } from '@/features/apps/components/AppInspector';
import { McpBrowser } from '../mcp/McpBrowser';
import { McpInspector } from '../mcp/McpInspector';
import { SettingsPage } from '../settings/SettingsPage';
import { RemMeProfileView } from '../remme/RemmeProfileView';
import { NewsList } from '@/features/news/components/NewsList';
import { ElectronBrowserView } from '@/features/news/components/ElectronBrowserView';
import { NewsInspector } from '@/features/news/components/NewsInspector';
import { IdeLayout } from '@/features/ide/components/IdeLayout';
import { SchedulerDashboard } from '@/features/scheduler/components/SchedulerDashboard';
import { MissionControl } from '@/features/console/components/MissionControl';
import { SkillsDashboard } from '@/features/skills/components/SkillsDashboard';

export const AppLayout: React.FC = () => {
    const {
        viewMode, sidebarTab, isAppViewMode, newsTabs, showNewsChatPanel,
        selectedNodeId, selectedAppCardId, selectedExplorerNodeId,
        ragActiveDocumentId, notesActiveDocumentId, ideActiveDocumentId,
        selectedMcpServer, selectedLibraryComponent, clearSelection, showRagInsights,
        isZenMode, isInboxOpen, setIsInboxOpen,
        isSidebarSubPanelOpen
    } = useAppStore();

    // Moved isInspectorOpen definition down to include new tabs context

    const isInspectorOpen = React.useMemo(() => {
        if (sidebarTab === 'apps' && selectedAppCardId) return true;
        if (sidebarTab === 'runs' && selectedNodeId) return true;
        if (sidebarTab === 'explorer' && selectedExplorerNodeId) return true;
        if (sidebarTab === 'rag' && showRagInsights) return true;
        if (sidebarTab === 'mcp' && selectedMcpServer) return true;
        if (sidebarTab === 'news' && showNewsChatPanel) return true;
        return false;
    }, [sidebarTab, selectedNodeId, selectedAppCardId, selectedExplorerNodeId, showRagInsights, selectedMcpServer, selectedLibraryComponent, showNewsChatPanel]);

    // Scheduler and Console take up full width, no sidebar subpanel needed
    const hideSidebarSubPanel = isInspectorOpen || sidebarTab === 'ide' || sidebarTab === 'scheduler' || sidebarTab === 'console' || sidebarTab === 'skills' || !isSidebarSubPanelOpen;

    const [leftWidth, setLeftWidth] = useState(400);
    const [rightWidth, setRightWidth] = useState(450); // original was 450px
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

        // Add a class to body to indicate resizing state if needed
        document.body.classList.add('is-resizing');
    }, [leftWidth, rightWidth]);

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                // MCP should be persistent as per user request
                if (sidebarTab !== 'mcp') {
                    clearSelection();
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [clearSelection]);

    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isDraggingRef.current) return;

            const delta = e.clientX - startXRef.current;

            if (isDraggingRef.current === 'left') {
                const newWidth = Math.max(150, Math.min(600, startWidthRef.current + delta));
                setLeftWidth(newWidth);
            } else {
                // For right panel, dragging left increases width
                const newWidth = Math.max(250, Math.min(800, startWidthRef.current - delta));
                setRightWidth(newWidth);
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

    // Initial RAG indexing status check
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


    return (
        <div className="h-screen w-screen flex flex-col bg-background text-foreground overflow-hidden font-sans animate-gradient-bg relative">
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <Meteors number={35} />
            </div>


            {/* Hide header when in App View Mode */}
            {!isAppViewMode && <Header />}

            {/* Inbox Overlay */}
            {isInboxOpen && (
                <InboxPanel onClose={() => setIsInboxOpen(false)} />
            )}

            <div ref={containerRef} className="flex-1 flex overflow-hidden p-3 gap-3 relative z-20">
                {/* Left Sidebar: Run Library - Hidden in fullscreen mode for Apps OR when in App View Mode OR when news chat is shown OR Zen Mode */}
                {!(isFullScreen && sidebarTab === 'apps') && !isAppViewMode && !(sidebarTab === 'news' && showNewsChatPanel) && !isZenMode && (
                    <>
                        <div
                            className={cn(
                                "h-full glass-panel rounded-2xl flex-shrink-0 overflow-hidden flex flex-col shadow-2xl transition-all duration-300 ease-out",
                                hideSidebarSubPanel ? "w-16" : ""
                            )}
                            style={{ width: hideSidebarSubPanel ? 64 : leftWidth }}
                        >
                            <Sidebar hideSubPanel={hideSidebarSubPanel} />
                        </div>

                        {!hideSidebarSubPanel && <ResizeHandle onMouseDown={handleMouseDown('left')} />}
                    </>
                )}

                {/* Center Canvas or Document Viewer - Main visual area */}
                <div className="flex-1 flex flex-col min-w-0 glass-panel rounded-2xl relative overflow-hidden shadow-2xl transition-all duration-300">
                    {/* Content Logic */}
                    {/* Content Logic */}
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

                            {/* Transient Views */}
                            {sidebarTab !== 'apps' && sidebarTab !== 'news' && (
                                sidebarTab === 'mcp' ? (
                                    <McpBrowser />
                                ) : sidebarTab === 'settings' ? (
                                    <SettingsPage />
                                ) : sidebarTab === 'rag' ? (
                                    <DocumentViewer />
                                ) : sidebarTab === 'notes' ? (
                                    /* If it's a binary file, show DocumentViewer, else show Editor */
                                    notesActiveDocumentId && /\.(pdf|png|jpg|jpeg|gif|webp|docx?|json)$/i.test(notesActiveDocumentId)
                                        ? <DocumentViewer context="notes" />
                                        : <NotesEditor />
                                ) : sidebarTab === 'remme' ? (
                                    <RemMeProfileView />
                                ) : sidebarTab === 'explorer' ? (
                                    <FlowWorkspace />
                                ) : sidebarTab === 'ide' ? (
                                    <IdeLayout />
                                ) : sidebarTab === 'scheduler' ? (
                                    <SchedulerDashboard />
                                ) : sidebarTab === 'skills' ? (
                                    <SkillsDashboard />
                                ) : sidebarTab === 'console' ? (
                                    <MissionControl />
                                ) : sidebarTab === 'canvas' ? (
                                    <CanvasHost surfaceId="ops-command-v1" />
                                ) : (
                                    <>
                                        <GraphCanvas />
                                        <RunTimeline />
                                    </>
                                )
                            )}
                        </>
                    )}

                    {/* APP RUNTIME VIEW (When "View App" is clicked) */}
                    {isAppViewMode && (
                        <div className="absolute inset-0 z-50 bg-background/95 backdrop-blur-xl flex items-center justify-center">
                            <div className="w-full h-full p-4">
                                <AppGrid isFullScreen={true} onToggleFullScreen={() => { }} />
                            </div>
                        </div>
                    )}
                </div>

                {/* Right panel - only show when something is selected or chat is active */}
                {isInspectorOpen && !isFullScreen && !isAppViewMode && (
                    <>
                        <ResizeHandle onMouseDown={handleMouseDown('right')} />

                        {/* Right Workspace Panel - Floating Glass */}
                        <div
                            className="h-full glass-panel rounded-2xl flex-shrink-0 flex flex-col overflow-hidden shadow-2xl transition-all duration-300 ease-out"
                            style={{ width: rightWidth }}
                        >
                            {sidebarTab === 'apps' ? <AppInspector /> :
                                sidebarTab === 'mcp' ? <McpInspector /> :
                                    sidebarTab === 'news' ? <NewsInspector /> :
                                        (sidebarTab === 'rag' || sidebarTab === 'notes') ? <DocumentAssistant context={sidebarTab as 'rag' | 'notes'} /> :
                                            <WorkspacePanel />}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};
