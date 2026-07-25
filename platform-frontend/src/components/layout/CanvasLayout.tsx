import React, { useEffect } from 'react';
import { StatusStrip } from './StatusStrip';
import { QuickNav } from './QuickNav';
import { FloatingPanel } from './FloatingPanel';
import { GraphCanvas } from '../graph/GraphCanvas';
import { RunTimeline } from '@/features/replay/RunTimeline';
import { DocumentViewer } from '../rag/DocumentViewer';
import { NotesEditor } from '../notes/NotesEditor';
import { useAppStore } from '@/store';
import type { UIMode } from '@/store';
import { cn } from '@/lib/utils';
import { InboxPanel } from '../inbox/InboxPanel';
import CanvasHost from '@/features/canvas/CanvasHost';
import useVoice from '@/hooks/useVoice';
import { useUIMode } from '@/hooks/useUIMode';
import { CanvasContextMenu } from '../command/CanvasContextMenu';

import { AppGrid } from '@/features/apps/components/AppGrid';
import { SettingsPage } from '../settings/SettingsPage';
import { RemMeProfileView } from '../remme/RemmeProfileView';
import { KnowledgeGraphExplorer } from '../graph/KnowledgeGraphExplorer';
import { ElectronBrowserView } from '@/features/news/components/ElectronBrowserView';
import { IdeLayout } from '@/features/ide/components/IdeLayout';
import { SchedulerDashboard } from '@/features/scheduler/components/SchedulerDashboard';
import { MissionControl } from '@/features/console/components/MissionControl';
import { SkillsDashboard } from '@/features/skills/components/SkillsDashboard';
import { ForgeDashboard } from '@/features/forge/components/ForgeDashboard';
import { AdminDashboard } from '@/features/admin/AdminDashboard';
import { SwarmGraphView } from '@/features/swarm/SwarmGraphView';
import { FlowWorkspace } from '../workspace/FlowWorkspace';
import { StatsModal } from '@/components/stats/StatsModal';
import { SpacesModal } from '@/components/sidebar/SpacesModal';
import { AuthModal } from '@/components/auth/AuthModal';

// ── Views that take over the canvas entirely ─────────────────────────────────

const FULL_VIEWS: Record<string, React.FC<any>> = {
    settings: SettingsPage,
    rag: DocumentViewer,
    remme: RemMeProfileView,
    graph: KnowledgeGraphExplorer,
    ide: IdeLayout,
    scheduler: SchedulerDashboard,
    skills: SkillsDashboard,
    studio: ForgeDashboard,
    console: MissionControl,
    admin: AdminDashboard,
    explorer: FlowWorkspace,
};

// Mode tint class mapping
const MODE_TINT: Record<UIMode, string> = {
    explore: 'mode-tint-explore',
    execute: 'mode-tint-execute',
    focus: 'mode-tint-focus',
    debug: 'mode-tint-debug',
};

// ── Main Layout ──────────────────────────────────────────────────────────────

export const CanvasLayout: React.FC = () => {
    useVoice();
    useUIMode(); // Auto mode detection (explore↔execute)

    const {
        sidebarTab, isAppViewMode,
        notesActiveDocumentId,
        isInboxOpen, setIsInboxOpen,
        startEventStream, stopEventStream,
        activeSurfaceId,
        uiMode,
        activeFullView, setActiveFullView,
        floatingPanels,
        isQuickNavVisible,
        isSpacesModalOpen, setIsSpacesModalOpen,
        isAuthModalOpen, setIsAuthModalOpen,
    } = useAppStore();

    // SSE connection — always active
    useEffect(() => {
        startEventStream();
        return () => stopEventStream();
    }, [startEventStream, stopEventStream]);

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

    // Track content transitions for full views
    const [contentKey, setContentKey] = React.useState(0);
    const [prevView, setPrevView] = React.useState(activeFullView);
    React.useEffect(() => {
        if (activeFullView !== prevView) {
            setPrevView(activeFullView);
            setContentKey(k => k + 1);
        }
    }, [activeFullView, prevView]);

    // Escape to return to canvas from full view
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && activeFullView) {
                setActiveFullView(null);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [activeFullView, setActiveFullView]);

    // Determine what to render in the center
    const renderCanvas = !activeFullView;
    const isNotesMediaFile = notesActiveDocumentId && /\.(pdf|png|jpg|jpeg|gif|webp|docx?|json)$/i.test(notesActiveDocumentId);

    return (
        <div className="h-screen w-screen flex flex-col bg-background text-foreground overflow-hidden">
            {!isAppViewMode && <StatusStrip />}

            {/* Inbox Overlay */}
            {isInboxOpen && (
                <InboxPanel onClose={() => setIsInboxOpen(false)} />
            )}

            <div className="flex-1 relative overflow-hidden">
                {/* ── Canvas Layer (always rendered, hidden when full view active) ── */}
                <CanvasContextMenu>
                <div className={cn(
                    "absolute inset-0 transition-opacity duration-300",
                    renderCanvas ? "opacity-100" : "opacity-0 pointer-events-none"
                )}>
                    {/* Mode tint overlay */}
                    <div className={cn("absolute inset-0 z-0 transition-colors duration-500", MODE_TINT[uiMode])} />

                    {/* Canvas background */}
                    <div className="absolute inset-0 z-0 canvas-bg" />

                    {/* Vignette overlay */}
                    <div className="absolute inset-0 z-[1] canvas-vignette" />

                    {/* Graph Canvas */}
                    <div className="absolute inset-0 z-[2]">
                        {sidebarTab === 'swarm' ? (
                            <SwarmGraphView />
                        ) : sidebarTab === 'canvas' && !activeFullView ? (
                            <CanvasHost surfaceId={activeSurfaceId} />
                        ) : (
                            <>
                                <GraphCanvas />
                                <RunTimeline />
                            </>
                        )}
                    </div>

                    {/* Floating Panels */}
                    <div className="absolute inset-0 z-[3] pointer-events-none">
                        <div className="relative w-full h-full pointer-events-none">
                            {floatingPanels.map(panel => (
                                <div key={panel.id} className="pointer-events-auto">
                                    <FloatingPanel panel={panel} />
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
                </CanvasContextMenu>

                {/* ── Full-View Layer (slides over canvas) ── */}
                {activeFullView && (
                    <div key={contentKey} className="absolute inset-0 z-[10] bg-background animate-content-in">
                        {/* Special cases first */}
                        {activeFullView === 'notes' ? (
                            isNotesMediaFile
                                ? <DocumentViewer context="notes" />
                                : <NotesEditor />
                        ) : activeFullView === 'apps' ? (
                            <AppGrid isFullScreen={false} onToggleFullScreen={() => { }} />
                        ) : activeFullView === 'news' ? (
                            <ElectronBrowserView />
                        ) : activeFullView === 'canvas' ? (
                            <CanvasHost surfaceId={activeSurfaceId} />
                        ) : FULL_VIEWS[activeFullView] ? (
                            React.createElement(FULL_VIEWS[activeFullView])
                        ) : (
                            // Fallback — render graph
                            <>
                                <GraphCanvas />
                                <RunTimeline />
                            </>
                        )}

                        {/* Back to canvas hint */}
                        <button
                            onClick={() => setActiveFullView(null)}
                            className="fixed top-10 left-4 z-50 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-1/80 border border-border/40 backdrop-blur-sm text-xs text-muted-foreground hover:text-foreground transition-all hover:bg-surface-2"
                        >
                            <span className="text-[10px]">←</span>
                            <span>Canvas</span>
                        </button>
                    </div>
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

            {/* QuickNav — floating dock at bottom */}
            {!isAppViewMode && isQuickNavVisible && <QuickNav />}

            {/* Modals */}
            <StatsModal isOpen={false} onClose={() => { }} />
            <SpacesModal isOpen={isSpacesModalOpen} onClose={() => setIsSpacesModalOpen(false)} />
            <AuthModal isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />
        </div>
    );
};
