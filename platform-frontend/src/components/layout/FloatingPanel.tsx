import React, { useCallback, useRef, useEffect, useState } from 'react';
import {
    X, Minus, Pin, PinOff, GripHorizontal,
    PlayCircle, Database, Notebook, Brain, Network,
    LayoutGrid, Code2, Wand2, CalendarClock, Zap,
    Terminal, Newspaper, Shield, Settings, Mic, Users,
    FileText, FolderOpen, ScrollText
} from 'lucide-react';
import { useAppStore } from '@/store';
import type { FloatingPanel as FloatingPanelType, FloatingPanelType as PanelTypeId } from '@/store';
import { cn } from '@/lib/utils';

// ── Panel content imports ────────────────────────────────────────────────────

import { RagPanel } from '@/components/sidebar/RagPanel';
import { RemmePanel } from '@/components/sidebar/RemmePanel';
import { NotesPanel } from '@/components/sidebar/NotesPanel';
import { ExplorerPanel } from '@/components/sidebar/ExplorerPanel';
import { EchoPanel } from '@/components/sidebar/EchoPanel';
import { SettingsPanel } from '@/components/sidebar/SettingsPanel';
import { NewsPanel } from '@/components/sidebar/NewsPanel';
import { GraphPanel } from '@/components/sidebar/GraphPanel';
import { CanvasPanel } from '@/components/sidebar/CanvasPanel';
import { SchedulerPanel } from '@/components/sidebar/SchedulerPanel';
import { WorkspacePanel } from '@/components/workspace/WorkspacePanel';
import { AppsSidebar } from '@/features/apps/components/AppsSidebar';
import { StudioSidebar } from '@/features/studio/StudioSidebar';
import { SwarmSidebar } from '@/features/swarm/SwarmSidebar';

// ── Panel metadata ───────────────────────────────────────────────────────────

const PANEL_META: Record<PanelTypeId, { label: string; icon: any }> = {
    'runs': { label: 'Runs', icon: PlayCircle },
    'agent-detail': { label: 'Agent Detail', icon: ScrollText },
    'logs': { label: 'Logs', icon: Terminal },
    'settings': { label: 'Settings', icon: Settings },
    'rag': { label: 'RAG', icon: Database },
    'notes': { label: 'Notes', icon: Notebook },
    'remme': { label: 'Memory', icon: Brain },
    'graph': { label: 'Graph', icon: Network },
    'explorer': { label: 'Explorer', icon: FolderOpen },
    'echo': { label: 'Echo', icon: Mic },
    'canvas-panel': { label: 'Canvas', icon: LayoutGrid },
    'scheduler': { label: 'Scheduler', icon: CalendarClock },
    'skills': { label: 'Skills', icon: Zap },
    'news': { label: 'News', icon: Newspaper },
    'admin': { label: 'Admin', icon: Shield },
    'swarm': { label: 'Swarm', icon: Users },
    'apps-sidebar': { label: 'Apps', icon: LayoutGrid },
    'studio': { label: 'Forge', icon: Wand2 },
};

// ── Panel content renderer ───────────────────────────────────────────────────

const PanelContent: React.FC<{ type: PanelTypeId }> = ({ type }) => {
    switch (type) {
        case 'rag': return <RagPanel />;
        case 'notes': return <NotesPanel />;
        case 'remme': return <RemmePanel />;
        case 'graph': return <GraphPanel />;
        case 'explorer': return <ExplorerPanel />;
        case 'echo': return <EchoPanel />;
        case 'canvas-panel': return <CanvasPanel />;
        case 'scheduler': return <SchedulerPanel />;
        case 'settings': return <SettingsPanel />;
        case 'news': return <NewsPanel />;
        case 'swarm': return <SwarmSidebar />;
        case 'apps-sidebar': return <AppsSidebar />;
        case 'studio': return <StudioSidebar />;
        case 'agent-detail': return <WorkspacePanel />;
        case 'logs': return <WorkspacePanel />;
        case 'runs': return <RunsListPanel />;
        case 'admin':
        case 'skills':
            return (
                <div className="flex items-center justify-center h-full text-muted-foreground text-xs">
                    Open as full view from QuickNav
                </div>
            );
        default: return null;
    }
};

// ── Inline RunsList for floating panel ───────────────────────────────────────

const RunsListPanel: React.FC = () => {
    const runs = useAppStore(state => state.runs);
    const currentRun = useAppStore(state => state.currentRun);
    const setCurrentRun = useAppStore(state => state.setCurrentRun);
    const currentSpaceId = useAppStore(state => state.currentSpaceId);

    const filteredRuns = React.useMemo(() => {
        let list = runs;
        if (currentSpaceId) {
            list = list.filter((r) => r.space_id === currentSpaceId);
        } else {
            list = list.filter((r) => !r.space_id || r.space_id === '__global__');
        }
        return list.filter((r) => !r.id.startsWith('auto_'));
    }, [runs, currentSpaceId]);

    return (
        <div className="flex flex-col h-full">
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {filteredRuns.map((run) => {
                    const isStale = run.status === 'running' && (Date.now() - run.createdAt > 60 * 60 * 1000);
                    const displayStatus = isStale ? 'failed' : run.status;
                    const isActive = currentRun?.id === run.id;

                    return (
                        <button
                            key={run.id}
                            onClick={() => setCurrentRun(run.id)}
                            className={cn(
                                "w-full text-left p-2.5 rounded-lg border transition-all duration-150",
                                isActive
                                    ? "border-primary/30 bg-primary/5"
                                    : "border-transparent hover:bg-accent/50"
                            )}
                        >
                            <p className={cn(
                                "text-xs font-medium leading-relaxed line-clamp-2",
                                isActive ? "text-primary" :
                                    displayStatus === 'failed' ? "text-red-400" : "text-foreground"
                            )}>
                                {run.name}
                            </p>
                            <div className="flex items-center gap-2 mt-1">
                                <span className="text-2xs text-muted-foreground font-mono">
                                    {new Date(run.createdAt).toLocaleDateString()}
                                </span>
                                <span className={cn(
                                    "px-1.5 py-0.5 rounded-full text-[9px] uppercase font-bold tracking-tight",
                                    displayStatus === 'completed' && "bg-success-muted text-success",
                                    displayStatus === 'failed' && "bg-red-500/10 text-red-400/80",
                                    displayStatus === 'running' && "bg-warning-muted text-warning animate-pulse",
                                )}>
                                    {displayStatus}
                                </span>
                            </div>
                        </button>
                    );
                })}
            </div>
        </div>
    );
};

// ── FloatingPanel component ──────────────────────────────────────────────────

export const FloatingPanel: React.FC<{ panel: FloatingPanelType }> = ({ panel }) => {
    const { closeFloatingPanel, updateFloatingPanel, bringToFront } = useAppStore();
    const meta = PANEL_META[panel.type];
    const Icon = meta.icon;

    const panelRef = useRef<HTMLDivElement>(null);
    const [isDragging, setIsDragging] = useState(false);
    const dragStartRef = useRef({ x: 0, y: 0, panelX: 0, panelY: 0 });

    // Drag handling
    const handleDragStart = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        setIsDragging(true);
        bringToFront(panel.id);
        dragStartRef.current = {
            x: e.clientX,
            y: e.clientY,
            panelX: panel.position.x,
            panelY: panel.position.y,
        };
    }, [panel.id, panel.position, bringToFront]);

    useEffect(() => {
        if (!isDragging) return;

        const handleMove = (e: MouseEvent) => {
            const dx = e.clientX - dragStartRef.current.x;
            const dy = e.clientY - dragStartRef.current.y;
            updateFloatingPanel(panel.id, {
                position: {
                    x: Math.max(0, dragStartRef.current.panelX + dx),
                    y: Math.max(0, dragStartRef.current.panelY + dy),
                },
            });
        };

        const handleUp = () => setIsDragging(false);

        document.addEventListener('mousemove', handleMove);
        document.addEventListener('mouseup', handleUp);
        return () => {
            document.removeEventListener('mousemove', handleMove);
            document.removeEventListener('mouseup', handleUp);
        };
    }, [isDragging, panel.id, updateFloatingPanel]);

    // Resize handling
    const [isResizing, setIsResizing] = useState(false);
    const resizeStartRef = useRef({ x: 0, y: 0, w: 0, h: 0 });

    const handleResizeStart = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsResizing(true);
        resizeStartRef.current = {
            x: e.clientX,
            y: e.clientY,
            w: panel.size.width,
            h: panel.size.height,
        };
    }, [panel.size]);

    useEffect(() => {
        if (!isResizing) return;

        const handleMove = (e: MouseEvent) => {
            const dx = e.clientX - resizeStartRef.current.x;
            const dy = e.clientY - resizeStartRef.current.y;
            updateFloatingPanel(panel.id, {
                size: {
                    width: Math.max(280, resizeStartRef.current.w + dx),
                    height: Math.max(200, resizeStartRef.current.h + dy),
                },
            });
        };

        const handleUp = () => setIsResizing(false);

        document.addEventListener('mousemove', handleMove);
        document.addEventListener('mouseup', handleUp);
        return () => {
            document.removeEventListener('mousemove', handleMove);
            document.removeEventListener('mouseup', handleUp);
        };
    }, [isResizing, panel.id, updateFloatingPanel]);

    if (panel.isMinimized) {
        return (
            <div
                className="floating-panel flex items-center gap-2 px-3 py-1.5 cursor-pointer animate-panel-float-in"
                style={{
                    position: 'absolute',
                    left: panel.position.x,
                    top: panel.position.y,
                    zIndex: panel.zIndex,
                }}
                onClick={() => updateFloatingPanel(panel.id, { isMinimized: false })}
                onMouseDown={() => bringToFront(panel.id)}
            >
                <Icon className="w-3 h-3 text-muted-foreground" />
                <span className="text-2xs font-medium text-foreground">{meta.label}</span>
            </div>
        );
    }

    return (
        <div
            ref={panelRef}
            className={cn(
                "floating-panel flex flex-col overflow-hidden animate-panel-float-in",
                (isDragging || isResizing) && "select-none"
            )}
            style={{
                position: 'absolute',
                left: panel.position.x,
                top: panel.position.y,
                width: panel.size.width,
                height: panel.size.height,
                zIndex: panel.zIndex,
            }}
            onMouseDown={() => bringToFront(panel.id)}
        >
            {/* Header — drag handle */}
            <div
                className="flex items-center gap-2 px-3 py-2 border-b border-panel-border shrink-0 cursor-grab active:cursor-grabbing"
                onMouseDown={handleDragStart}
            >
                <GripHorizontal className="w-3 h-3 text-muted-foreground/40" />
                <Icon className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-xs font-semibold text-foreground flex-1 truncate">{meta.label}</span>

                {/* Pin toggle */}
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        updateFloatingPanel(panel.id, { isPinned: !panel.isPinned });
                    }}
                    className={cn(
                        "p-0.5 rounded transition-colors",
                        panel.isPinned ? "text-primary" : "text-muted-foreground/40 hover:text-muted-foreground"
                    )}
                >
                    {panel.isPinned ? <PinOff className="w-3 h-3" /> : <Pin className="w-3 h-3" />}
                </button>

                {/* Minimize */}
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        updateFloatingPanel(panel.id, { isMinimized: true });
                    }}
                    className="p-0.5 rounded text-muted-foreground/40 hover:text-muted-foreground transition-colors"
                >
                    <Minus className="w-3 h-3" />
                </button>

                {/* Close */}
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        closeFloatingPanel(panel.id);
                    }}
                    className="p-0.5 rounded text-muted-foreground/40 hover:text-foreground transition-colors"
                >
                    <X className="w-3 h-3" />
                </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-hidden">
                <PanelContent type={panel.type} />
            </div>

            {/* Resize handle — bottom-right corner */}
            <div
                className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize"
                onMouseDown={handleResizeStart}
            >
                <svg
                    className="absolute bottom-1 right-1 w-2 h-2 text-muted-foreground/30"
                    viewBox="0 0 6 6"
                    fill="currentColor"
                >
                    <circle cx="5" cy="1" r="0.7" />
                    <circle cx="5" cy="5" r="0.7" />
                    <circle cx="1" cy="5" r="0.7" />
                </svg>
            </div>
        </div>
    );
};
