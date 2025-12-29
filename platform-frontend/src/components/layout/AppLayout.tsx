import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { WorkspacePanel } from '../workspace/WorkspacePanel';
import { GraphCanvas } from '../graph/GraphCanvas';
import { FlowWorkspace } from '../workspace/FlowWorkspace';
import { RunTimeline } from '@/features/replay/RunTimeline';
import { GripVertical } from 'lucide-react';
import { DocumentViewer } from '../rag/DocumentViewer';
import { useAppStore } from '@/store';

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

export const AppLayout: React.FC = () => {
    const { viewMode, sidebarTab, isAppViewMode } = useAppStore();
    const [leftWidth, setLeftWidth] = useState(400); // w-64 = 256px
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
    }, [leftWidth, rightWidth]);

    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isDraggingRef.current) return;

            const delta = e.clientX - startXRef.current;

            if (isDraggingRef.current === 'left') {
                const newWidth = Math.max(150, Math.min(400, startWidthRef.current + delta));
                setLeftWidth(newWidth);
            } else {
                // For right panel, dragging left increases width
                const newWidth = Math.max(250, Math.min(700, startWidthRef.current - delta));
                setRightWidth(newWidth);
            }
        };

        const handleMouseUp = () => {
            isDraggingRef.current = null;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        };

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);

        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };
    }, []);


    return (
        <div className="h-screen w-screen flex flex-col bg-background text-foreground overflow-hidden font-sans">
            <Header />

            <div ref={containerRef} className="flex-1 flex overflow-hidden">
                {/* Left Sidebar: Run Library - Hidden in fullscreen mode for Apps OR when in App View Mode OR on Settings page */}
                {!(isFullScreen && sidebarTab === 'apps') && !isAppViewMode && sidebarTab !== 'settings' && (
                    <>
                        <div
                            className="h-full border-r border-border bg-card/50 backdrop-blur-sm flex-shrink-0"
                            style={{ width: leftWidth }}
                        >
                            <Sidebar />
                        </div>

                        <ResizeHandle onMouseDown={handleMouseDown('left')} />
                    </>
                )}

                {/* Center Canvas or Document Viewer */}
                <div className="flex-1 relative bg-grid-dots overflow-hidden">
                    {sidebarTab === 'settings' ? (
                        <SettingsPage />
                    ) : sidebarTab === 'rag' ? (
                        <DocumentViewer />
                    ) : sidebarTab === 'explorer' ? (
                        <FlowWorkspace />
                    ) : sidebarTab === 'apps' ? (
                        <AppGrid isFullScreen={isFullScreen} onToggleFullScreen={() => setIsFullScreen(!isFullScreen)} />
                    ) : sidebarTab === 'mcp' ? (
                        <McpBrowser />
                    ) : (
                        <>
                            <GraphCanvas />
                            <RunTimeline />
                        </>
                    )}
                </div>

                {(sidebarTab === 'runs' || sidebarTab === 'rag' || sidebarTab === 'explorer' || sidebarTab === 'apps' || sidebarTab === 'mcp') && !isFullScreen && !isAppViewMode && (
                    <>
                        <ResizeHandle onMouseDown={handleMouseDown('right')} />

                        {/* Right Workspace Panel */}
                        <div
                            className="h-full border-l border-border bg-card/50 backdrop-blur-sm flex-shrink-0 flex flex-col"
                            style={{ width: rightWidth }}
                        >
                            {sidebarTab === 'apps' ? <AppInspector /> : sidebarTab === 'mcp' ? <McpInspector /> : <WorkspacePanel />}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};
