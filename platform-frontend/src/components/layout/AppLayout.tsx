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
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';

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
import { NewsArticleViewer } from '@/features/news/components/NewsArticleViewer';
import { NewsInspector } from '@/features/news/components/NewsInspector';

export const AppLayout: React.FC = () => {
    const {
        viewMode, sidebarTab, isAppViewMode, newsTabs, showNewsChatPanel,
        selectedNodeId, selectedAppCardId, selectedExplorerNodeId, activeDocumentId,
        selectedMcpServer, selectedLibraryComponent, clearSelection, showRagInsights
    } = useAppStore();

    const isInspectorOpen = React.useMemo(() => {
        if (sidebarTab === 'apps' && (selectedAppCardId || selectedLibraryComponent)) return true;
        if (sidebarTab === 'runs' && selectedNodeId) return true;
        if (sidebarTab === 'explorer' && selectedExplorerNodeId) return true;
        if (sidebarTab === 'rag' && showRagInsights) return true;
        if (sidebarTab === 'mcp' && selectedMcpServer) return true;
        if (sidebarTab === 'news' && showNewsChatPanel) return true;
        return false;
    }, [sidebarTab, selectedNodeId, selectedAppCardId, selectedExplorerNodeId, showRagInsights, selectedMcpServer, selectedLibraryComponent, showNewsChatPanel]);

    const hideSidebarSubPanel = isInspectorOpen;

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


    return (
        <div className="h-screen w-screen flex flex-col bg-background text-foreground overflow-hidden font-sans animate-gradient-bg">
            {/* Hide header when in App View Mode */}
            {!isAppViewMode && <Header />}

            <div ref={containerRef} className="flex-1 flex overflow-hidden p-3 gap-3">
                {/* Left Sidebar: Run Library - Hidden in fullscreen mode for Apps OR when in App View Mode OR when news chat is shown */}
                {!(isFullScreen && sidebarTab === 'apps') && !isAppViewMode && !(sidebarTab === 'news' && showNewsChatPanel) && (
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
                <div className="flex-1 flex flex-col min-w-0 glass rounded-2xl relative overflow-hidden shadow-2xl transition-all duration-300">
                    {/* Content Logic */}
                    {!isAppViewMode && (
                        sidebarTab === 'apps' ? (
                            <AppGrid isFullScreen={isFullScreen} onToggleFullScreen={() => setIsFullScreen(!isFullScreen)} />
                        ) : sidebarTab === 'mcp' ? (
                            <McpBrowser />
                        ) : sidebarTab === 'settings' ? (
                            <SettingsPage />
                        ) : sidebarTab === 'rag' ? (
                            <DocumentViewer />
                        ) : sidebarTab === 'remme' ? (
                            <RemMeProfileView />
                        ) : sidebarTab === 'explorer' ? (
                            <FlowWorkspace />
                        ) : sidebarTab === 'news' ? (
                            <NewsArticleViewer />
                        ) : (
                            <>
                                <GraphCanvas />
                                <RunTimeline />
                            </>
                        )
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
                                        sidebarTab === 'rag' ? <DocumentAssistant /> :
                                            <WorkspacePanel />}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};
